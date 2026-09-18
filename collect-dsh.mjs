/** Collect frozen trials from durable Sessions; preserve each first attempt.
 * Hash-bound evidence and separate missing/failed denominators follow the MIT-licensed
 * Dudu-0223/dsh-benchmarks/file-references evaluator (25f7ec5c).
 */
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath, pathToFileURL} from 'node:url';

const ROOT=path.dirname(fileURLToPath(import.meta.url));
const DEFAULT_PRIVATE=path.resolve(ROOT,'../.artifacts/visualizer/runs');
const tokens={'--dsw-alias-bg-base':'#ffffff','--dsw-alias-bg-layer-1':'#ffffff','--dsw-alias-bg-layer-2':'#f4f5f7','--dsw-alias-border-l1':'#e5e7eb','--dsw-alias-border-l2':'#d1d5db','--dsw-alias-label-primary':'#1f2329','--dsw-alias-label-secondary':'#606875','--dsw-alias-label-tertiary':'#9299a3','--dsw-alias-label-primary-inverted':'#ffffff','--dsw-alias-brand-primary':'#4d6bfe','--dsw-alias-button-primary-fill':'#4d6bfe','--dsw-alias-interactive-bg-hover':'#eef1ff','--dsw-alias-interactive-bg-active':'#e0e7ff','--dsw-alias-state-error-primary':'#c43535'};
const sha=value=>crypto.createHash('sha256').update(value).digest('hex');
const json=p=>JSON.parse(fs.readFileSync(p,'utf8'));
const walk=p=>fs.existsSync(p)?fs.readdirSync(p,{withFileTypes:true}).flatMap(e=>e.isDirectory()?walk(path.join(p,e.name)):e.isFile()?[path.join(p,e.name)]:[]):[];
function writeJson(file,value){fs.mkdirSync(path.dirname(file),{recursive:true});fs.writeFileSync(file+'.tmp',JSON.stringify(value,null,2)+'\n');fs.renameSync(file+'.tmp',file);}
function parse(value){if(typeof value!=='string')return value??{};try{return JSON.parse(value)}catch{return {unparsed:true}}}
function textParts(value){
  if(!value)return [];
  if(Array.isArray(value))return value.flatMap(textParts);
  if(typeof value!=='object')return [];
  return [...(typeof value.text==='string'?[value.text]:[]),...textParts(value.content)];
}
export function visibleAssistantText(content){
  return (Array.isArray(content)?content:[]).filter(part=>part?.type==='text'&&typeof part.text==='string').map(part=>part.text).join('\n');
}
export function visibleAssistantReply(messages){
  return messages.map(message=>visibleAssistantText(message.data.message?.content)).filter(Boolean).join('\n\n');
}
function failed(value){return Boolean(value&&typeof value==='object'&&(value.isError===true||Object.values(value).some(x=>Array.isArray(x)?x.some(failed):x&&typeof x==='object'&&failed(x))));}
function readRows(file){
  const rows=[],errors=[];
  if(!file||!fs.existsSync(file))return {rows,errors};
  fs.readFileSync(file,'utf8').split('\n').forEach((line,index)=>{if(!line.trim())return;try{rows.push(JSON.parse(line))}catch{errors.push(`Invalid JSON on line ${index+1}`)}});
  return {rows,errors};
}
function redact(text, privateRoot, repo){
  let result=String(text??'');
  for(const value of [process.env.DEEPSEEK_API_KEY,process.env.ANTHROPIC_AUTH_TOKEN])if(value)result=result.split(value).join('[redacted credential]');
  for(const value of [privateRoot,repo])if(value)result=result.split(value).join('[private path]');
  return result.replace(/\bsk-[A-Za-z0-9_-]{16,}/g,'[redacted credential]')
    .replace(/\/(?:Users|home)\/[^\s<>"'`)\]]+/g,'[private path]')
    .replace(/(Authorization\s*:\s*Bearer\s+)\S+/gi,'$1[redacted credential]');
}
function nestedCall(call){
  let name=call.data.name,args=parse(call.data.arguments),wrapped=false;
  if(['tools.execute','tools/execute','execute'].includes(name)&&args&&typeof args==='object'){
    const target=args.tool_name??args.tool??args.name;
    if(typeof target==='string'){
      name=target;args=parse(args.arguments??args.parameters??args.args??args.input);wrapped=true;
    }
  }
  return {...call,effectiveName:name,args,wrapped};
}
function defaultTrial(manifest,item,task){return {
  schemaVersion:2,id:item.id,roundId:manifest.id,caseId:item.caseId,arm:item.arm,repeat:item.repeat,
  status:item.status,prompt:task.prompt,expectedRoute:task.route,widgets:[],final:'',
  checks:{route:{status:'pending',reason:'Trial has not completed'},acceptance:{status:'pending',reason:'Awaiting the deterministic checks and human review'}},
  trace:{tools:[],referencesRead:[]},usage:{},elapsedSeconds:null,sourceHead:manifest.sourceHead,
  rendererSha256:manifest.rendererSha256??null,
};}
function routeCheck(task, calls,widgets,finished){
  if(!finished)return {status:'pending',reason:'Generation did not complete; the route is not scored as a pass'};
  const actual=calls.filter(c=>c.effectiveName==='show_widget');
  const expected=typeof task.route==='object'?task.route.expectation??task.route.kind:task.route;
  const need=['inline','widget','required'].includes(expected);
  const optional=['optional','inline-optional','allow-inline'].includes(expected);
  if(!need&&!optional)return {status:actual.length?'fail':'pending',reason:actual.length?'Unexpected show_widget attempt for this task':'No inline widget attempt; verify the requested delivery form with check-dsh.py'};
  if(!actual.length)return {status:need?'fail':'pass',reason:need?'Expected an inline visual, but show_widget was not called':'An ordinary answer is permitted'};
  if(!widgets.length)return {status:'fail',reason:'show_widget was attempted but no source was accepted'};
  const allowed=task.allowedKinds??['svg','html'];
  const bad=widgets.some(w=>!allowed.includes(w.kind));
  return {status:bad?'fail':'pass',reason:bad?'Accepted source uses a disallowed output kind':'Accepted inline output uses an allowed form'};
}

async function collect(roundId,privateRoot){
  const publicDir=path.join(ROOT,'results',roundId),privateDir=path.join(privateRoot,roundId);
  const manifest=json(path.join(publicDir,'manifest.json'));
  if(manifest.collectorSha256!==sha(fs.readFileSync(fileURLToPath(import.meta.url))))throw Error('Collector changed after this round was frozen; preserve its existing results and use a new round');
  const config=json(path.join(privateDir,'round.json'));
  for(const field of ['id','arm','model','reasoningEffort','sourceHead','runtimeHashes','casesSha256','rubricSha256','cases','timeoutSeconds','runnerSha256','collectorSha256']){
    if(JSON.stringify(manifest[field])!==JSON.stringify(config.manifest[field]))throw Error('Public round differs from frozen inputs: '+field);
  }
  const identities=items=>items.map(({status,...identity})=>identity);
  if(JSON.stringify(identities(manifest.trials))!==JSON.stringify(identities(config.manifest.trials)))throw Error('Planned trial identities changed after freezing');
  if(manifest.casesSha256!==sha(fs.readFileSync(path.join(privateDir,'inputs/cases.json'))))throw Error('Frozen cases changed');
  if([path.join(ROOT,'rubric.md'),path.join(privateDir,'inputs/rubric.md'),path.join(publicDir,'rubric.md')].some(file=>sha(fs.readFileSync(file))!==manifest.rubricSha256))throw Error('Rubric changed after freezing; use a new round with the new scoring rules');
  const repo=config.repo;
  let renderer=null,rendererError=null;
  if(manifest.visualizerAvailable){
    try{
      const relevant=Object.entries(manifest.runtimeHashes).filter(([p])=>p.includes('ui-visualizer/src/client/')||p.endsWith('/lib/types/client.js'));
      if(relevant.some(([p,d])=>!fs.existsSync(path.join(repo,p))||sha(fs.readFileSync(path.join(repo,p)))!==d))throw Error('Renderer or library catalogue changed after the round was frozen');
      renderer=await import(pathToFileURL(path.join(repo,'packages/visualizer/ui-visualizer/src/client/srcdoc.ts')).href);
    }catch(error){rendererError=redact(error.message,privateRoot,repo)}
  }
  let collected=0;
  for(const item of manifest.trials){
    const task=manifest.cases.find(c=>c.id===item.caseId);
    if(!task)throw Error(`Missing frozen case ${item.caseId}`);
    const slot=path.join(privateDir,'trials',item.id),dest=path.join(publicDir,item.id),trialPath=path.join(dest,'trial.json');
    const previous=fs.existsSync(trialPath)?json(trialPath):null;
    const trial=defaultTrial(manifest,item,task);
    const executionFile=path.join(slot,'execution.json');
    if(!fs.existsSync(executionFile)){
      if(fs.existsSync(slot)){trial.status='interrupted';trial.error='Private attempt exists without a completed execution record; preserve this attempt and use a new round to retry';item.status=trial.status;}
      writeJson(trialPath,trial);continue;
    }
    const execution=json(executionFile);
    trial.status=execution.status;
    trial.elapsedSeconds=execution.elapsedSeconds??null;
    if(execution.reason)trial.error=redact(execution.reason,privateRoot,repo);
    const stream=readRows(path.join(slot,'events.jsonl'));
    const sessionId=stream.rows.find(e=>e.type==='session')?.sessionId;
    const logs=walk(path.join(slot,'home/sessions')).filter(p=>p.endsWith('/session.v3.jsonl'));
    const log=logs.find(p=>sessionId&&path.basename(path.dirname(p))===sessionId)??(logs.length===1?logs[0]:null);
    const durable=readRows(log),rows=durable.rows;
    const parseErrors=[...stream.errors.map(e=>'stdout: '+e),...durable.errors.map(e=>'Session: '+e)];
    if(!log&&trial.status==='completed'){trial.status='error';trial.error='No unambiguous durable Session log; generation is not counted as complete';}
    if(parseErrors.length){trial.status='error';trial.error='Malformed retained log';trial.parseErrors=parseErrors;}
    const calls=rows.filter(e=>e.type==='tool/call').map(nestedCall);
    const results=rows.filter(e=>e.type==='tool/result');
    const resultFor=c=>results.find(r=>r.data?.message?.source?.callId===c.data.callId||r.data?.message?.content?.some(x=>x.toolCallId===c.data.callId));
    trial.trace.tools=calls.map(c=>({name:c.effectiveName,loggedName:c.data.name,callSeq:c.seq,callId:c.data.callId,
      argumentsSha256:sha(typeof c.data.arguments==='string'?c.data.arguments:JSON.stringify(c.data.arguments??{})),
      wrapped:c.wrapped,resultSeq:resultFor(c)?.seq??null,error:resultFor(c)?failed(resultFor(c).data):null}));
    trial.trace.referencesRead=calls.filter(c=>c.effectiveName==='read').flatMap(c=>{
      const file=c.args.file_path??c.args.path??c.args.filePath;
      if(typeof file!=='string'||!(file.includes('/references/')||file.startsWith('references/')))return [];
      const relative='references/'+file.split(/(?:^|\/)references\//).at(-1);
      const frozenRelative='packages/visualizer/tool-visualizer/assets/'+relative;
      return [{path:relative,callSeq:c.seq,resultSeq:resultFor(c)?.seq??null,success:Boolean(resultFor(c)&&!failed(resultFor(c).data)),
        sha256:path.isAbsolute(file)&&path.resolve(file)===path.resolve(repo,frozenRelative)?manifest.runtimeHashes[frozenRelative]??null:null,
        resultSha256:resultFor(c)?sha(JSON.stringify(resultFor(c).data)):null}];
    });
    trial.trace.skillLoads=calls.filter(c=>c.effectiveName==='skill').map(c=>({name:c.args.name,callSeq:c.seq,resultSeq:resultFor(c)?.seq??null,success:Boolean(resultFor(c)&&!failed(resultFor(c).data)),resultSha256:resultFor(c)?sha(JSON.stringify(resultFor(c).data)):null}));
    trial.rejected=[];
    const widgetCalls=calls.filter(c=>c.effectiveName==='show_widget');
    for(const c of widgetCalls){
      // A wrapper and its durable inner event can represent the same execution.
      if(c.wrapped&&widgetCalls.some(other=>!other.wrapped&&other.data.callId===c.data.callId))continue;
      const result=resultFor(c),source=c.args.widget_code;
      const rejection=!result||failed(result.data)||typeof source!=='string';
      const index=trial.widgets.length+trial.rejected.length+1;
      const stem=`widget-${index}`;
      let sourcePath=null,previewPath=null,publicationError=null;
      const sourceSha=typeof source==='string'?sha(source):null;
      if(typeof source==='string'){
        // Publish byte-identical generated source only when it has no known secret/private path.
        if(redact(source,privateRoot,repo)!==source)publicationError='Original source withheld because it contains a credential or private host path; raw source remains in the private Session';
        else{
          sourcePath=path.posix.join('results',roundId,item.id,stem+'.source.html');
          fs.mkdirSync(dest,{recursive:true});fs.writeFileSync(path.join(ROOT,sourcePath),source);
        }
      }
      const kind=result?.data?.meta?.kind??(typeof source==='string'&&source.trimStart().startsWith('<svg')?'svg':'html');
      if(rejection){trial.rejected.push({callSeq:c.seq,resultSeq:result?.seq??null,replace:c.args.replace??null,source:sourcePath,sha256:sourceSha,
        error:redact(result?textParts(result.data.message?.content).join('\n'):'No matching tool result',privateRoot,repo),publicationError});continue;}
      if(sourcePath&&renderer){
        const doc=kind==='svg'?renderer.buildStaticSrcDoc(source,tokens,true):renderer.buildInteractiveSrcDoc(source,tokens);
        previewPath=path.posix.join('results',roundId,item.id,stem+'.html');fs.writeFileSync(path.join(ROOT,previewPath),doc);
      }
      trial.widgets.push({title:redact(c.args.title,privateRoot,repo),kind,callSeq:c.seq,resultSeq:result.seq,
        replace:c.args.replace??null,source:sourcePath,preview:previewPath,sha256:sourceSha,bytes:Buffer.byteLength(source),
        ...(publicationError?{publicationError}:{}),...(!renderer?{previewError:rendererError??'No Visualizer renderer was frozen'}:{})});
    }
    const assistants=rows.filter(r=>r.type==='assistant/message');
    for(const message of assistants)for(const[k,v]of Object.entries(message.data.usage??{}))if(typeof v==='number')trial.usage[k]=(trial.usage[k]??0)+v;
    trial.final=redact(visibleAssistantReply(assistants),privateRoot,repo);
    trial.finalSha256=sha(visibleAssistantReply(assistants));
    const header=rows.find(e=>e.type==='request/header')?.data.header;
    trial.requestModel=header?.config?.model??null;
    trial.reasoningEffort=header?.config?.reasoningEffort??null;
    trial.toolSchemasSha256=header?sha(JSON.stringify(header.tools??[])):null;
    trial.trace.systemMessages=rows.filter(e=>e.type==='system/message').map(e=>({seq:e.seq,sha256:sha(JSON.stringify(e.data))}));
    trial.trace.requestHeaders=rows.filter(e=>e.type==='request/header').map(e=>({seq:e.seq,sha256:sha(JSON.stringify(e.data.header)),model:e.data.header?.config?.model??null,reasoningEffort:e.data.header?.config?.reasoningEffort??null}));
    const turnReason=rows.filter(e=>e.type==='turn/end').at(-1)?.data.reason;
    trial.turnEnd=turnReason?.kind??null;
    const streamError=stream.rows.filter(e=>e.type==='error').at(-1);
    const failure=turnReason?.kind==='error'?turnReason.error:streamError;
    if(failure){
      trial.error=redact(failure.message??'Model or runtime request failed',privateRoot,repo);
      trial.errorCode=typeof failure.code==='string'?redact(failure.code,privateRoot,repo):null;
    }
    if(trial.status==='completed'&&trial.turnEnd!=='completed'){trial.status='error';trial.error='Process exited but the Session did not record a completed turn';}
    if(trial.status==='completed'&&(trial.requestModel!=='deepseek-flash'||trial.reasoningEffort!=='high')){trial.status='error';trial.error='Recorded model configuration does not match deepseek-flash / high';}
    trial.workspaceChanges=Object.keys({...execution.initialFiles,...execution.finalFiles}).filter(p=>execution.initialFiles?.[p]!==execution.finalFiles?.[p])
      .map(p=>({path:redact(p,privateRoot,repo),beforeSha256:execution.initialFiles?.[p]??null,afterSha256:execution.finalFiles?.[p]??null}));
    trial.checks.route=routeCheck(task,calls,trial.widgets,trial.status==='completed');
    if(['blocked','timeout','error','interrupted'].includes(trial.status))trial.checks.acceptance={status:'error',reason:trial.error??`Generation ${trial.status}`};
    else if(!['inline','widget','required','optional','inline-optional','allow-inline'].includes(typeof task.route==='string'?task.route:task.route?.kind))trial.checks.acceptance={status:'not_applicable',reason:'This case evaluates routing only'};
    else if(task.route==='optional'&&!trial.widgets.length)trial.checks.acceptance={status:'not_applicable',reason:'Optional inline output was not chosen'};
    trial.artifactSetSha256=sha(JSON.stringify({final:trial.finalSha256,widgets:trial.widgets.map(w=>({sha256:w.sha256,callSeq:w.callSeq,resultSeq:w.resultSeq}))}));
    if(previous?.artifactSetSha256===trial.artifactSetSha256){
      if(previous.checks?.acceptance)trial.checks.acceptance=previous.checks.acceptance;
      for(const key of ['browserChecks','annotations','humanReview'])if(previous[key]!==undefined)trial[key]=previous[key];
    }
    item.status=trial.status;
    writeJson(trialPath,trial);collected++;
  }
  writeJson(path.join(publicDir,'manifest.json'),manifest);
  console.log(JSON.stringify({round:roundId,collected,planned:manifest.trials.length,statuses:manifest.trials.reduce((a,t)=>(a[t.status]=(a[t.status]??0)+1,a),{})}));
}

// Explicit correction of an export bug, not a rerun of a frozen experiment.
// Keep the frozen collector hash and private original export as provenance.
function correctFinalExports(roundId,privateRoot){
  const publicDir=path.join(ROOT,'results',roundId),privateDir=path.join(privateRoot,roundId);
  const manifest=json(path.join(publicDir,'manifest.json'));
  if(manifest.trials.some(t=>['planned','running'].includes(t.status)))throw Error('Wait until generation has finished; the running collector would overwrite this correction');
  const config=json(path.join(privateDir,'round.json')),correctorSha=sha(fs.readFileSync(fileURLToPath(import.meta.url)));
  const prepared=[];
  for(const item of manifest.trials){
    if(item.status!=='completed')continue;
    const slot=path.join(privateDir,'trials',item.id),file=path.join(publicDir,item.id,'trial.json');
    const original=fs.readFileSync(file,'utf8'),trial=JSON.parse(original);
    const stream=readRows(path.join(slot,'events.jsonl'));
    const sessionId=stream.rows.find(e=>e.type==='session')?.sessionId;
    const logs=walk(path.join(slot,'home/sessions')).filter(p=>p.endsWith('/session.v3.jsonl'));
    const log=logs.find(p=>sessionId&&path.basename(path.dirname(p))===sessionId)??(logs.length===1?logs[0]:null);
    if(!log)throw Error('No unambiguous private Session: '+item.id);
    const durable=readRows(log),assistants=durable.rows.filter(r=>r.type==='assistant/message'),last=assistants.at(-1);
    if(stream.errors.length||durable.errors.length||!last)throw Error('Invalid source log: '+item.id);
    const content=last.data.message?.content,visible=visibleAssistantReply(assistants);
    const oldSha=sha(textParts(content).join('\n')),newSha=sha(visible);
    const priorCorrection=trial.extractionCorrection;
    if(trial.extractionCorrection){
      if(trial.finalSha256===newSha&&trial.final===redact(visible,privateRoot,config.repo)&&trial.extractionCorrection.assistantSeqs)continue;
      if(trial.finalSha256!==sha(visibleAssistantText(content))||trial.final!==redact(visibleAssistantText(content),privateRoot,config.repo))throw Error('Previously corrected export differs from source: '+item.id);
    }else{
      if(trial.finalSha256!==oldSha)throw Error('Original final digest differs from the frozen extraction: '+item.id);
      if(trial.final!==redact(textParts(content).join('\n'),privateRoot,config.repo))throw Error('Original final content was edited: '+item.id);
    }
    const sourceHeader=durable.rows.find(r=>r.type==='request/header');
    const recorded=trial.trace?.requestHeaders?.find(h=>h.seq===sourceHeader?.seq);
    if(!sourceHeader||recorded?.sha256!==sha(JSON.stringify(sourceHeader.data.header)))throw Error('Session identity mismatch: '+item.id);
    const previousFinalSha256=trial.finalSha256;
    trial.final=redact(visible,privateRoot,config.repo);
    trial.finalSha256=newSha;
    trial.artifactSetSha256=sha(JSON.stringify({final:newSha,widgets:trial.widgets.map(w=>({sha256:w.sha256,callSeq:w.callSeq,resultSeq:w.resultSeq}))}));
    trial.extractionCorrection={kind:'visible-assistant-text-only',correctedAt:new Date().toISOString(),
      frozenCollectorSha256:manifest.collectorSha256,correctorSha256:correctorSha,
      sourceSessionSha256:sha(fs.readFileSync(log)),assistantSeqs:assistants.filter(r=>visibleAssistantText(r.data.message?.content)).map(r=>r.seq),previousFinalSha256,
      ...(priorCorrection?{previousCorrection:priorCorrection}:{}),finalChanged:previousFinalSha256!==newSha,
      reason:'All visible assistant text blocks are included in chronological order. Non-display blocks remain in the private Session; generation and widget sources are unchanged.'};
    prepared.push({file,trial,original,backup:path.join(privateDir,'exports-before-visible-text-all',item.id+'.json')});
  }
  // Validate every source before changing any export; backups never enter the public repo.
  for(const entry of prepared){
    fs.mkdirSync(path.dirname(entry.backup),{recursive:true,mode:0o700});
    fs.writeFileSync(entry.backup,entry.original,{flag:'wx',mode:0o600});
    writeJson(entry.file,entry.trial);
  }
  console.log(JSON.stringify({round:roundId,correctedExports:prepared.length,changedFinals:prepared.filter(p=>p.trial.extractionCorrection.finalChanged).length,modelRequests:0}));
}

if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
  const options={};
  for(let i=2;i<process.argv.length;i++){
    const name=process.argv[i];
    if(name==='--correct-final-exports'){options[name]=true;continue;}
    if(!['--round','--private-root'].includes(name)||!process.argv[i+1])throw Error('Usage: node collect-dsh.mjs --round ID [--private-root DIR] [--correct-final-exports]');
    options[name]=process.argv[++i];
  }
  if(!options['--round']||!/^[A-Za-z0-9][A-Za-z0-9._-]*$/.test(options['--round']))throw Error('A safe --round ID is required');
  const privateRoot=path.resolve(options['--private-root']??DEFAULT_PRIVATE);
  if(options['--correct-final-exports'])correctFinalExports(options['--round'],privateRoot);
  else await collect(options['--round'],privateRoot);
}
