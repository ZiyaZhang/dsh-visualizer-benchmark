/** Browser evidence from unmodified generated source; no Host or model follow-up claims. */
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import {createRequire} from 'node:module';
import {fileURLToPath, pathToFileURL} from 'node:url';

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const DEFAULT_REPO = process.env.DSH_EVAL_REPO;
const hash = value => crypto.createHash('sha256').update(value).digest('hex');
const check = (status, reason, evidence = {}) => ({status, reason, evidence});
const args = Object.fromEntries(process.argv.slice(2).reduce((rows, value, index, list) => {
  if (value.startsWith('--')) rows.push([value.slice(2), list[index + 1]]);
  return rows;
}, []));
if ((!args.trial && !args['legacy-run']) || !args.output) {
  console.error('Usage: node render-check.mjs (--trial trial.json | --legacy-run ID) --output DIR [--repo WEB_REPO] [--base-url URL] [--cases cases.json] [--widget-index N]');
  process.exit(2);
}
if (!args.repo && !DEFAULT_REPO) {
  console.error('Set DSH_EVAL_REPO to the installed DSH Web checkout, or pass --repo WEB_REPO.');
  process.exit(2);
}
const widgetIndex = Number(args['widget-index'] ?? 0);
if (!Number.isInteger(widgetIndex) || widgetIndex < 0) {
  console.error('--widget-index must be a nonnegative integer (0 selects the first accepted component).');
  process.exit(2);
}
const out = path.resolve(args.output);
await fs.mkdir(out, {recursive: true});
const trialPath = args.trial && path.resolve(args.trial);
const trial = trialPath ? JSON.parse(await fs.readFile(trialPath, 'utf8')) : JSON.parse(await fs.readFile(path.join(ROOT, 'dsh-results.json'), 'utf8')).runs.find(r => r.id === args['legacy-run']);
if (!trial) throw new Error('Trial not found');
const frozenCases = trialPath && path.resolve(path.dirname(trialPath), '../cases.json');
const casesPath = args.cases || (frozenCases && await fs.stat(frozenCases).then(s=>s.isFile()).catch(()=>false) ? frozenCases : path.join(ROOT, 'cases.json'));
const casesBytes = await fs.readFile(casesPath);
const cases = JSON.parse(casesBytes).cases;
const legacy = {I01: 'binary', I02: 'heat', F01: 'sales', N04: 'quantity'};
const caseId = trial.caseId || trial.case;
const task = cases.find(c => c.id === caseId) || {id: caseId, browser: {scenario: legacy[caseId]}};
const scenario = task.browser?.scenario || legacy[caseId] || (task.route === 'optional' ? 'static' : undefined);
const widget = trial.widgets?.[widgetIndex]; // Default keeps the first accepted source as first-render evidence.
const visual = widget || (widgetIndex === 0 ? trial.artifacts?.find(a => a.preview) : undefined);
const result = {
  schemaVersion: 2, trialId: trial.id, caseId, scenario, widgetIndex, callSeq: widget?.callSeq ?? null, resultSeq: widget?.resultSeq ?? null, casesPath: path.relative(ROOT,path.resolve(casesPath)), casesSha256: hash(casesBytes), collectedAt: new Date().toISOString(),
  scope: 'Isolated original srcdoc preview. No real WidgetCard, Host Remote, repair admission, or subsequent model response is exercised.',
  checks: {
    render: check('pending', 'Browser has not run.'), interaction: check('pending', 'Scenario has not run.'),
    localMessages: check('pending', 'Local actions have not run.'), followupPayload: check('not_applicable', 'No explicit follow-up requested by this scenario.'),
    hostFollowup: check('not_applicable', 'This preview never contacts the Host; validate real conversation delivery separately.'),
    layout: check('pending', 'Screenshots and overflow flags support human review, not an automatic design score.'),
    content: check('pending', 'Browser evidence is not a full content or factual grade.'),
  }, screenshots: [], states: [], messages: [], console: [], pageErrors: [], failedRequests: [], flags: [],
};
const write = async () => {
  await fs.writeFile(path.join(out, 'browser-checks.json'), JSON.stringify(result, null, 2) + '\n');
  console.log(JSON.stringify({trialId: trial.id, output: path.join(out, 'browser-checks.json'), checks: Object.fromEntries(Object.entries(result.checks).map(([k, v]) => [k, v.status]))}));
};
if (!visual) {
  const applicable = ['widget', 'optional'].includes(trial.expectedRoute || task.route);
  result.checks.render = check(applicable ? 'pending' : 'not_applicable', 'No accepted visual preview is available. Do not count absence as a rendering pass.');
  result.checks.interaction = check('not_applicable', 'No component to operate.');
  result.checks.localMessages = check('not_applicable', 'No component to operate.');
  result.checks.layout = check('not_applicable', 'No component to inspect.');
  await write();
  process.exit(0);
}

async function readAsset(value) {
  if (!value) throw new Error('No asset path recorded');
  const candidates = path.isAbsolute(value) ? [value] : [trialPath && path.resolve(path.dirname(trialPath), value), path.resolve(ROOT, value)].filter(Boolean);
  for (const name of candidates) { try { return await fs.readFile(name, 'utf8'); } catch (error) { if (error.code !== 'ENOENT') throw error; } }
  if (args['base-url']) {
    const url = new URL(value, args['base-url']);
    if (!['127.0.0.1', 'localhost', '[::1]'].includes(url.hostname)) throw new Error('Asset fallback must use an explicit local benchmark server');
    const response = await fetch(url, {signal: AbortSignal.timeout(10000)});
    if (!response.ok) throw new Error(`Asset request failed: ${response.status}`);
    return response.text();
  }
  throw new Error(`Asset unavailable: ${value}`);
}
const light = {'--dsh-widget-color-scheme':'light','--dsw-alias-bg-base':'#ffffff','--dsw-alias-bg-layer-1':'#ffffff','--dsw-alias-bg-layer-2':'#f4f5f7','--dsw-alias-label-primary':'#1f2329','--dsw-alias-label-secondary':'#606875','--dsw-alias-label-tertiary':'#9299a3','--dsw-alias-label-primary-inverted':'#ffffff','--dsw-alias-border-l1':'#e5e7eb','--dsw-alias-border-l2':'#d1d5db','--dsw-alias-brand-primary':'#4d6bfe','--dsw-alias-button-primary-fill':'#4d6bfe','--dsw-alias-interactive-bg-hover':'#eef1ff','--dsw-alias-interactive-bg-active':'#e0e7ff','--dsw-alias-state-error-primary':'#c43535'};
const dark = {...light,'--dsh-widget-color-scheme':'dark','--dsw-alias-bg-base':'#1c2128','--dsw-alias-bg-layer-1':'#1c2128','--dsw-alias-bg-layer-2':'#292f38','--dsw-alias-label-primary':'#e5e7eb','--dsw-alias-label-secondary':'#abb4c0','--dsw-alias-label-tertiary':'#929ba8','--dsw-alias-border-l1':'#373e48','--dsw-alias-border-l2':'#4b5563'};
class Inconclusive extends Error {}
class OracleFailure extends Error {}
let browser;
try {
  const source = await readAsset(visual.source);
  const preview = await readAsset(visual.preview);
  const repo = path.resolve(args.repo || DEFAULT_REPO);
  const rendererFile = path.join(repo, 'packages/visualizer/ui-visualizer/src/client/srcdoc.ts');
  const renderer = await import(pathToFileURL(rendererFile));
  result.sourceSha256 = hash(source);
  result.previewSha256 = hash(preview);
  result.rendererSha256 = trial.rendererSha256 ?? null;
  result.rendererHashKind = trial.rendererHashKind ?? (trial.rendererSha256 ? 'recorded trial renderer source hash' : 'not frozen in this trial');
  result.checkerRuntimeRendererSha256 = hash(await fs.readFile(rendererFile));
  result.themeMethod = widget?.kind === 'svg' ? 'Original light preview; dark SVG is rebuilt from unchanged source using checkerRuntimeRendererSha256.' : 'Original preview bytes; theme variables are updated through the shipped iframe message bridge.';
  result.checkerSha256 = hash(await fs.readFile(fileURLToPath(import.meta.url)));
  if (visual.sha256 && visual.sha256 !== result.sourceSha256) throw new Error('Recorded source hash does not match the source file');
  result.kind = visual.kind || 'artifact';
  result.sandbox = widget?.kind === 'svg' ? '' : 'allow-scripts';
  const require = createRequire(path.join(repo, 'apps/web/package.json'));
  const {chromium} = require('playwright');
  result.playwrightVersion = require('playwright/package.json').version;
  result.networkRequests = [];
  browser = await chromium.launch({headless: true});
  result.browserVersion = browser.version();
  const context = await browser.newContext({viewport: {width: 736, height: 1000}, locale: 'zh-CN', timezoneId: 'UTC', reducedMotion: 'reduce'});
  const page = await context.newPage();
  page.setDefaultTimeout(2500);
  page.on('console', message => result.console.push({type: message.type(), text: message.text().slice(0, 2000)}));
  page.on('pageerror', error => result.pageErrors.push(error.message));
  page.on('request', request => { if(/^https?:/.test(request.url()))result.networkRequests.push({url:request.url().replace(/\?.*$/,''),resourceType:request.resourceType()}); });
  page.on('requestfailed', request => result.failedRequests.push({url: request.url().replace(/\?.*$/, ''), resourceType: request.resourceType(), error: request.failure()?.errorText}));
  async function load(width, appearance) {
    const tokens = appearance === 'dark' ? dark : light;
    const document = widget?.kind === 'svg' && appearance === 'dark' ? renderer.buildStaticSrcDoc(source, tokens, true) : preview;
    await page.setViewportSize({width, height: 1000});
    await page.setContent('<!doctype html><html><meta charset="utf-8"><body style="margin:0"><main></main></body></html>');
    await page.evaluate(({document, sandbox, tokens}) => {
      document = 'data:text/html;charset=utf-8,' + encodeURIComponent(document);
      window.__evidence = [];
      const frame = window.document.createElement('iframe');
      frame.id = 'benchmark-frame';
      frame.title = 'Generated component under test';
      frame.setAttribute('sandbox', sandbox);
      frame.style.cssText = 'display:block;border:0;width:100%;height:320px';
      window.document.body.style.background = tokens['--dsw-alias-bg-base'];
      window.addEventListener('message', event => {
        if (event.source !== frame.contentWindow || event.data?.source !== 'dsh-widget') return;
        window.__evidence.push({type: event.data.type, channel: event.data.channel, payload: event.data.payload, at: performance.now()});
        if (event.data.type === 'ready') frame.contentWindow.postMessage({source: 'dsh-widget', type: 'theme', payload: {tokens}}, '*');
        if (event.data.type === 'resize' && Number.isFinite(event.data.payload?.height)) frame.style.height = Math.min(8192, Math.max(1, event.data.payload.height)) + 'px';
      });
      window.document.querySelector('main').append(frame);
      frame.src = document;
    }, {document, sandbox: result.sandbox, tokens});
    const element = await page.$('#benchmark-frame');
    const frame = await element.contentFrame();
    await frame.waitForURL(/^data:text\/html/, {waitUntil: 'load', timeout: 12000});
    if (widget?.kind === 'html') await page.waitForFunction(() => window.__evidence.some(e => ['rendered', 'error', 'resource_error'].includes(e.type)), null, {timeout: 12000}).catch(() => {});
    else {
      const height = await frame.evaluate(() => Math.ceil(document.body.scrollHeight));
      await element.evaluate((node, height) => { node.style.height = Math.min(8192, Math.max(1, height)) + 'px'; }, height);
    }
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    return frame;
  }
  const messages = () => page.evaluate(() => window.__evidence);
  const sends = async () => (await messages()).filter(m => m.type === 'send_prompt');
  async function state(frame, name, width = 736, appearance = 'light', screenshot = false) {
    const evidence = await frame.evaluate(() => {
      const body = document.body;
      const visible = element => { const style = getComputedStyle(element); return style.display !== 'none' && style.visibility !== 'hidden' && element.getBoundingClientRect().width > 0 && element.getBoundingClientRect().height > 0; };
      const temperature = [...body.querySelectorAll('*')].filter(visible).map(e => (e.textContent || '').trim()).filter(t => /^-?\d+(?:\.\d+)?\s*(?:°\s*C|℃)$/.test(t)).map(t => Number.parseFloat(t));
      const text = body.innerText + '\n' + [...body.querySelectorAll('svg text')].filter(visible).map(e => e.textContent).join(' ');
      const numericReadouts = [...body.querySelectorAll('[role="status"],output,[role="spinbutton"],input[type="number"]')].filter(visible).map(e=>(e.getAttribute('aria-valuenow') || e.value || e.textContent || '').trim()).filter(t=>/^-?\d+(?:\.\d+)?$/.test(t)).map(Number);
      return {text, temperature, numericReadouts, bodyWidth: body.scrollWidth, viewportWidth: innerWidth, bodyHeight: body.scrollHeight,
        visibleGraphics: [...body.querySelectorAll('svg,canvas,img')].filter(visible).length,
        accessibleNames: [...body.querySelectorAll('[aria-label]')].filter(visible).map(e => e.getAttribute('aria-label'))};
    });
    evidence.messages = await messages();
    evidence.name = name; evidence.width = width; evidence.appearance = appearance;
    evidence.accessibility = await frame.locator('body').ariaSnapshot();
    if (evidence.bodyWidth > evidence.viewportWidth + 2) result.flags.push({type: 'horizontal-overflow', state: name, width, appearance, scrollWidth: evidence.bodyWidth});
    result.states.push(evidence);
    if (screenshot) {
      const filename = `${name}-${width}-${appearance}.png`;
      await page.screenshot({path: path.join(out, filename), fullPage: true});
      result.screenshots.push({path: filename, state: name, width, appearance});
    }
    return evidence;
  }
  async function button(frame, name) {
    const locator = frame.getByRole('button', {name});
    if (await locator.count() !== 1) throw new Inconclusive(`Expected one accessible button matching ${name}; found ${await locator.count()}.`);
    if (!await locator.isEnabled()) throw new OracleFailure(`Button ${name} is disabled before the requested action.`);
    await locator.click();
    await frame.evaluate(() => new Promise(resolve => requestAnimationFrame(resolve)));
    return locator;
  }
  function requireTruth(value, reason) { if (!value) throw new OracleFailure(reason); }
  function numericLabel(text, label) {
    const specific = text.match(new RegExp(`(?:^|\\n)${label}[（(][^）)\\n]*[）)]\\s*[:：=]?\\s*(-?\\d+|—|–|-)`, 'i'));
    const annotated = [...text.matchAll(new RegExp(`(?:^|\\n)${label}[^\\d=\\n]{1,20}\\n\\s*(-?\\d+|—|–|-)`, 'ig'))].at(-1);
    const match = specific || annotated || [...text.matchAll(new RegExp(`(?:^|\\n)${label}\\s*[:：=]?\\s*(-?\\d+|—|–|-)`, 'ig'))].at(-1);
    return match ? /^-?\d+$/.test(match[1]) ? Number(match[1]) : null : undefined;
  }
  function binaryRead(evidence) { return Object.fromEntries(['low','mid','high'].map(k => [k, numericLabel(evidence.text, k)])); }
  function heatRead(evidence, expected) {
    let values = evidence.temperature;
    const pairs = [...evidence.text.matchAll(/(?:^|\n)(?:节点|T)\s*(\d+)[^\n]*\n(?:固定\s*\n)?\s*(-?\d+(?:\.\d+)?)/g)].map(match=>({index:Number(match[1]),value:Number(match[2])}));
    const numbered = pairs.length===5 && [0,1].includes(pairs[0].index) && pairs.every((entry,i)=>entry.index===pairs[0].index+i);
    if(numbered) { values=pairs.map(entry=>entry.value); evidence.temperatureReadoutSource='visible numbered-node readouts'; evidence.temperatureOracleValues=values; }
    const accessible = evidence.accessibleNames.map(name=>[...name.matchAll(/(-?\d+(?:\.\d+)?)\s*(?:°\s*C|℃|摄氏度)/g)].map(match=>Number(match[1]))).find(values=>values.length===5);
    if(accessible) {
      evidence.temperatureAccessibleValues=accessible;
      if(numbered && accessible.some((value,i)=>Math.abs(value-values[i])>.011)) result.flags.push({type:'accessible-temperature-difference',state:evidence.name,visible:values,accessible});
    }
    if (values.length < 5) throw new Inconclusive('Five precise visible temperature readouts could not be identified; accessible summaries may be rounded and cannot replace visible-state evidence.');
    requireTruth(values.some((_, i) => expected.every((n, j) => Math.abs(values[i+j] - n) < 0.011)), `Expected synchronous temperatures ${expected.join(', ')}; visible readouts: ${values.join(', ')}.`);
  }
  async function namedChoice(frame, expression) {
    for (const role of ['button', 'radio', 'option', 'tab', 'checkbox']) {
      const candidate = frame.getByRole(role, {name:expression});
      if (await candidate.count() === 1) {
        if (role === 'option') await candidate.locator('xpath=ancestor::select').selectOption({label:(await candidate.innerText()).trim()});
        else await candidate.click();
        return candidate;
      }
    }
    const text = frame.getByText(expression);
    if (await text.count() !== 1) throw new Inconclusive(`Cannot identify a unique visible choice matching ${expression}.`);
    await text.click();
    return text;
  }
  function readNumber(evidence, label) {
    const matches = [...evidence.text.matchAll(new RegExp(`(?:${label})(?:[（(][^）)\\n]*[）)])?[^\\d\\n]{0,15}\\s*(-?\\d+(?:\\.\\d+)?)`, 'ig'))].map(m=>Number(m[1]));
    const unique = [...new Set(matches)];
    if (unique.length !== 1) throw new Inconclusive(`Cannot identify one numeric readout for ${label}; found ${unique.join(', ')}.`);
    return unique[0];
  }
  async function sliderPercent(frame, percentage) {
    const slider = frame.getByRole('slider');
    if (await slider.count() !== 1) throw new Inconclusive('Expected one accessible range control.');
    const range = await slider.evaluate(element=>({min:Number(element.min||0), max:Number(element.max||100), step:Number(element.step||1)}));
    const count = Math.round((range.max-range.min)*percentage/100/range.step);
    if (!Number.isFinite(count) || count > 1000 || range.step <= 0) throw new Inconclusive('Range cannot be operated with a bounded keyboard sequence.');
    await slider.press('Home');
    for(let i=0;i<count;i++)await slider.press('ArrowRight');
  }
  let frame = await load(736, 'light');
  const initial = await state(frame, 'initial', 736, 'light', true);
  const startupErrors = initial.messages.filter(m => ['error', 'resource_error'].includes(m.type));
  const visible = initial.text.trim() || initial.visibleGraphics;
  result.checks.render = startupErrors.length ? check('fail', 'Browser reported an initial runtime/resource error.', {errors: startupErrors})
    : !visible ? check('fail', 'Document loaded without visible text or graphics.', {state: 'initial'})
    : widget?.kind === 'html' && !initial.messages.some(m => m.type === 'rendered') ? check('pending', 'HTML document appeared, but startup signal was not observed.', {state:'initial'})
    : check('pass', 'Document bootstrapped without a captured initial error and has visible content. This does not establish meaning, factual correctness, or functioning controls.', {state:'initial'});
  let localCount = null;
  try {
    if (scenario === 'binary') {
      const before = binaryRead(initial);
      if (before.low === undefined || before.high === undefined) throw new Inconclusive('Readable low/high state could not be identified.');
      requireTruth(before.low === 0 && before.high === 7, 'Initial interval is not [0,7].');
      await button(frame, /下一步|单步|Next|Step/i);
      const one = await state(frame, 'step-1'); const a = binaryRead(one);
      if (a.mid === undefined) throw new Inconclusive('Visible midpoint could not be identified after step 1.');
      requireTruth(a.mid === 3, `First midpoint should be 3, found ${a.mid}.`);
      await button(frame, /下一步|单步|Next|Step/i);
      const two = await state(frame, 'step-2', 736, 'light', true); const b = binaryRead(two);
      if (b.mid === undefined) throw new Inconclusive('Visible midpoint could not be identified after step 2.');
      requireTruth(b.mid === 5 && b.low === 4 && b.high === 7, 'Second comparison should use interval [4,7] and midpoint 5.');
      requireTruth(/命中|找到|found/i.test(two.text), 'No found-state message after the second comparison.');
      await button(frame, /重置|重新开始|Reset/i);
      const reset = binaryRead(await state(frame, 'reset'));
      requireTruth(JSON.stringify(reset) === JSON.stringify(before), 'Reset did not restore the initial displayed search state.');
      localCount = (await sends()).length;
    } else if (scenario === 'heat') {
      heatRead(initial, [100,0,0,0,0]);
      await button(frame, /单步|下一步|Step|Next/i); heatRead(await state(frame, 'step-1'), [100,25,0,0,0]);
      await button(frame, /单步|下一步|Step|Next/i); heatRead(await state(frame, 'step-2',736,'light',true), [100,37.5,6.25,0,0]);
      await button(frame, /重置|重新开始|Reset/i); heatRead(await state(frame, 'reset'), [100,0,0,0,0]);
      localCount = (await sends()).length;
    } else if (scenario === 'sales') {
      const option = frame.getByRole('listbox').getByRole('option',{name:/西部/});
      const grouped = frame.getByRole('group',{name:/选择地区|地区选择|select.*region|region.*selection/i}).getByRole('button',{name:/西部/});
      const ordinary = frame.getByRole('button',{name:/西部/});
      const isOption = await option.count()===1;
      const selectedControl = isOption ? option : await grouped.count()===1 ? grouped : ordinary;
      if(await selectedControl.count()!==1)throw new Inconclusive('Cannot identify one semantic region choice; inspect duplicated or nonsemantic controls.');
      await selectedControl.click();
      const selected = await state(frame, 'selected-west',736,'light',true);
      const selectedAttribute = await selectedControl.getAttribute(isOption?'aria-selected':'aria-pressed');
      if(isOption) requireTruth(selectedAttribute==='true','The selected listbox option must expose aria-selected=true.');
      else if (selectedAttribute !== 'true' && !/(?:已选|所选|选中)[^\n]{0,30}西部/.test(selected.text)) throw new Inconclusive('Selection appearance cannot be verified semantically; inspect selected-state screenshot.');
      localCount = (await sends()).length;
      await button(frame, /解释.*(?:所选|选中|地区)|Explain/i);
      const sent = await sends();
      const payloadText = sent[0]?.payload?.text || '';
      const amounts = [...payloadText.matchAll(/(?<![\d.eE+-])([+-]?\d+(?:\.\d+)?)\s*万元/g)].map(match => Number(match[1]));
      result.checks.followupPayload = check(sent.length === 1 && /西部/.test(payloadText) && amounts.includes(50) ? 'pass' : 'fail', 'Preview checks the emitted payload only; Host admission and model continuation remain separate.', {count:sent.length, payloads:sent.map(m=>m.payload?.text), amountsInTenThousandYuan:amounts});
      result.checks.hostFollowup = check('pending', 'Run this action in the real DSH conversation to verify Remote admission and the model response.');
      await state(frame,'explain-sent');
    } else if (scenario === 'quantity') {
      const number = evidence => { const dedicated = [...new Set(evidence.numericReadouts)]; if(dedicated.length===1)return dedicated[0]; const lines = evidence.text.split('\n').map(s=>s.trim()).filter(s=>/^\d+$/.test(s)); if(lines.length!==1)throw new Inconclusive('Quantity cannot be uniquely identified from visible readouts.'); return Number(lines[0]); };
      requireTruth(number(initial) === 2, 'Initial quantity should be 2.');
      for(let i=0;i<3;i++)await button(frame,/增加|加一|Increase|Increment/i);
      requireTruth(number(await state(frame,'maximum',736,'light',true)) === 5, 'Maximum quantity should be 5.');
      requireTruth(!await frame.getByRole('button',{name:/增加|加一|Increase|Increment/i}).isEnabled(),'Increase must be disabled at 5.');
      for(let i=0;i<5;i++)await button(frame,/减少|减一|Decrease|Decrement/i);
      requireTruth(number(await state(frame,'minimum')) === 0, 'Minimum quantity should be 0.');
      requireTruth(!await frame.getByRole('button',{name:/减少|减一|Decrease|Decrement/i}).isEnabled(),'Decrease must be disabled at 0.');
      localCount = (await sends()).length;
    } else if (scenario === 'cache') {
      for(const [percentage,cost] of [[0,1],[50,.55],[100,.1]]) {
        await sliderPercent(frame,percentage);
        const evidence = await state(frame,`hit-${percentage}`,736,'light',percentage===50);
        requireTruth(Math.abs(readNumber(evidence,'总成本|成本总计|总费用|total cost')-cost)<.0001, `Expected cost ${cost} at ${percentage}% cache hits.`);
        const hit = readNumber(evidence,'(?<!未)命中(?:输入)?(?:数量|token数|token|Token数|Token)?|cache hits');
        const miss = readNumber(evidence,'未命中(?:输入)?(?:数量|token数|token|Token数|Token)?|cache misses');
        requireTruth(hit===percentage*10 && miss===1000-percentage*10, 'Hit/miss token readouts do not match 1000 total tokens.');
      }
      localCount = (await sends()).length;
    } else if (scenario === 'backoff') {
      let finalState = initial;
      const observed = []; const waits = [];
      for(let i=1;i<=8;i++) {
        const step = frame.getByRole('button',{name:/单步|下一步|Step|Next/i});
        if(await step.count()!==1)throw new Inconclusive('Cannot identify one step control.');
        if(!await step.isEnabled())break;
        await button(frame,/单步|下一步|Step|Next/i);
        const next = await state(frame,`step-${i}`,736,'light',i===3);
        observed.push(next.text);
        try { waits.push(readNumber(next,'下一次等待|下次等待|下一等待|next wait')); } catch(error) { if(!(error instanceof Inconclusive))throw error; }
        if(next.text===finalState.text)break;
        finalState=next;
      }
      if(observed.length<2)throw new Inconclusive('Not enough distinct visible retry states to check the sequence.');
      const combined=observed.join('\n').replace(/\s+/g,' ');
      const attempts=[[/第?\s*1\s*次[^。]{0,30}(?:失败|failed)/i,'first attempt failure'],[/第?\s*2\s*次[^。]{0,30}(?:失败|failed)/i,'second attempt failure'],[/第?\s*3\s*次[^。]{0,30}(?:成功|success)/i,'third attempt success']];
      for(const [expression,label] of attempts)if(!expression.test(combined))throw new Inconclusive(`Could not identify ${label} in visible history.`);
      if(!waits.length)throw new Inconclusive('Intermediate wait readouts could not be identified.');
      requireTruth(waits.indexOf(1)>=0 && waits.indexOf(2)>waits.indexOf(1),`Expected waiting 1 then 2 seconds; observed ${waits.join(', ')}.`);
      requireTruth(readNumber(finalState,'累计等待(?:时间)?|总等待(?:时间)?|total wait')===3,'Total retry wait must be 3 seconds.');
      const noWait=/(?:下一次等待|下次等待|下一等待|next wait)[^\d\n]{0,15}\s*(?:—|–|无|无需|none)/i.test(finalState.text);
      if(!noWait)requireTruth(readNumber(finalState,'下一次等待|下次等待|下一等待|next wait')===0,'A successful terminal state must not schedule another wait.');
      const after=(await sends()).length;
      await button(frame,/重置|重新开始|Reset/i);
      const reset=await state(frame,'reset');
      requireTruth(reset.text===initial.text,'Reset did not restore the initial visible retry state.');
      localCount=(await sends()).length;
      requireTruth(after===0,'Retry steps must stay local.');
      requireTruth(!result.networkRequests.some(r=>['fetch','xhr'].includes(r.resourceType)), 'Retry demonstration attempted a real network request.');
    } else if (scenario === 'filter') {
      const apply=frame.getByRole('button',{name:/^应用$|^Apply$/i});
      if(await apply.count()!==1)throw new Inconclusive('Cannot identify the apply button.');
      requireTruth(!await apply.isEnabled(),'Apply must be disabled for an empty owner.');
      const owner=frame.getByRole('textbox',{name:/负责人|Owner/i});
      if(await owner.count()!==1)throw new Inconclusive('Cannot identify a labelled owner textbox.');
      await owner.fill('李明');
      await namedChoice(frame,/^已完成$|^Completed$/i);
      await button(frame,/^应用$|^Apply$/i);
      const complete=await state(frame,'applied-completed',736,'light',true);
      const summary=complete.text.match(/(?:摘要|已应用|当前筛选|筛选结果|已选择|Summary|Applied)[\s\S]{0,180}/i)?.[0];
      if(!summary)throw new Inconclusive('An applied summary cannot be distinguished from the input values.');
      requireTruth(summary.includes('李明')&&/已完成|Completed/i.test(summary),'Applied summary must show the selected state and owner.');
      await namedChoice(frame,/^进行中$|^In progress$/i);
      await button(frame,/^应用$|^Apply$/i);
      const ongoing=await state(frame,'applied-ongoing');
      const updated=ongoing.text.match(/(?:摘要|已应用|当前筛选|筛选结果|已选择|Summary|Applied)[\s\S]{0,180}/i)?.[0];
      if(!updated)throw new Inconclusive('Updated applied summary cannot be identified.');
      requireTruth(updated.includes('李明')&&/进行中|In progress/i.test(updated),'Second application must reflect the new current state.');
      localCount=(await sends()).length;
    } else if (scenario === 'errors') {
      const payloads=[]; let unexpected=0;
      for(const [day,rate] of [[4,'2.8'],[2,'0.5']]) {
        const before=(await sends()).length;
        await namedChoice(frame,new RegExp(`^(?:第\\s*${day}\\s*(?:天|日)|Day\\s*${day})(?:\\s|[·:：]|$).*`,'i'));
        await state(frame,`selected-day-${day}`,736,'light',day===4);
        unexpected+=(await sends()).length-before;
        await button(frame,/分析.*(?:所选|选中|日期)|Analyze/i);
        const current=await sends();
        const emitted=current.slice(before);
        payloads.push({day,rate,messages:emitted.map(m=>m.payload?.text)});
      }
      localCount=unexpected;
      const okay=payloads.every(p=>p.messages.length===1&&new RegExp(`(?:第\\s*${p.day}\\s*(?:天|日)|Day\\s*${p.day})`,'i').test(p.messages[0])&&p.messages[0].includes(p.rate+'%'));
      result.checks.followupPayload=check(okay?'pass':'fail','Each explicit analysis action must emit exactly one payload for the current selected day and rate.',{payloads});
      result.checks.hostFollowup=check('pending','Real Host admission and model interpretation are not exercised in the preview.');
    } else if (scenario === 'static') {
      const expected = task.browser?.expectedText || [];
      const text = initial.text + '\n' + initial.accessibleNames.join('\n');
      const normal = value=>value.replaceAll('−','-');
      const missing = expected.filter(label => !normal(text).includes(normal(label)));
      result.checks.visibleLabels = check(!expected.length ? 'not_applicable' : missing.length ? 'pending' : 'pass', !expected.length ? 'No literal label oracle specified.' : missing.length ? 'Labels may be drawn rather than machine-readable; human inspection required.' : 'All requested literal labels are present in visible text or accessible names.', {expectedText:expected,missing});
      result.checks.content = check('pending', missing.length ? 'Some required labels were not machine-readable; inspect canvas/graphics and screenshots before grading.' : 'Required labels were observed; values, proportions and meaning still need content review.', {expectedText: expected, missing});
      result.checks.interaction = check('not_applicable','No automatic action sequence specified for this static inspection.');
    } else throw new Inconclusive(`Scenario ${scenario || '(missing)'} needs a case-specific action/readout adapter; screenshots alone do not pass interaction.`);
    if (scenario !== 'static') result.checks.interaction = check('pass', 'Requested implemented action sequence matched its visible-state oracle.', {states:result.states.map(s=>s.name)});
  } catch(error) {
    result.checks.interaction = check(error instanceof OracleFailure ? 'fail' : error instanceof Inconclusive ? 'pending' : 'error', error.message, {states:result.states.map(s=>s.name)});
  }
  if (localCount !== null) result.checks.localMessages = check(localCount === 0 ? 'pass' : 'fail', 'Local-only action sequence must emit zero model follow-ups.', {sendPromptCount:localCount});
  else if (scenario === 'static') result.checks.localMessages = check('not_applicable','No local action sequence was requested.');
  result.messages = await messages();
  const lateErrors = result.messages.filter(m=>['error','resource_error'].includes(m.type));
  if (lateErrors.length && result.checks.interaction.status === 'pass') result.checks.interaction = check('fail','An error occurred during the action sequence.',{errors:lateErrors});
  for(const [width,appearance] of [[360,'light'],[736,'dark'],[360,'dark']]) {
    frame = await load(width,appearance);
    await state(frame,'initial',width,appearance,true);
  }
  result.checks.layout = check('pending','Four initial viewport/theme screenshots recorded; overflow is a review flag, not a standalone product verdict.',{screenshots:result.screenshots.map(s=>s.path),flags:result.flags});
} catch(error) {
  result.checks.render = check('error',`Checker/environment failure: ${error.message}`);
} finally {
  await browser?.close();
  await write();
}
