"""Small checker calibration: known bad evidence must not become a pass."""
import hashlib
import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = Path(os.environ['DSH_EVAL_REPO']) if os.environ.get('DSH_EVAL_REPO') else None
NODE = os.environ.get('DSH_EVAL_NODE') or 'node'
spec = importlib.util.spec_from_file_location('checks', ROOT / 'check-dsh.py')
checks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checks)


class CollectorChecks(unittest.TestCase):
    def test_final_exports_only_visible_text_blocks(self):
        script = "import assert from 'node:assert/strict';import {visibleAssistantText,visibleAssistantReply} from " + json.dumps(str(ROOT / 'collect-dsh.mjs')) + ";" + """
        assert.equal(visibleAssistantText([{type:'reasoning',text:'private fixture'},
          {type:'text',text:'Visible one'},{type:'tool_use',text:'not a reply'},
          {type:'text',text:'Visible two'}]), 'Visible one\\nVisible two');
        assert.equal(visibleAssistantText([{type:'reasoning',text:'private fixture'}]), '');
        assert.equal(visibleAssistantText(undefined), '');
        assert.equal(visibleAssistantReply([
          {data:{message:{content:[{type:'text',text:'Before widget'}]}}},
          {data:{message:{content:[{type:'reasoning',text:'private fixture'}]}}},
          {data:{message:{content:[{type:'text',text:'After widget'}]}}}
        ]), 'Before widget\\n\\nAfter widget');
        """
        subprocess.run([NODE, '--input-type=module', '-e', script], check=True, capture_output=True, timeout=15)


class RouteChecks(unittest.TestCase):
    def test_absence_and_unfinished_are_not_success(self):
        self.assertEqual(checks.check_trial({'tools': [], 'final': ''}, {'route': 'text'})['route']['status'], 'pending')
        self.assertEqual(checks.check_trial({'status': 'blocked'}, {'route': 'plugin'})['route']['status'], 'pending')
        self.assertEqual(checks.check_trial({'tools': [], 'final': 'Done'}, {'route': 'file', 'expectedFiles': ['a.html']})['route']['status'], 'fail')

    def test_right_route_requires_delivery_evidence(self):
        base = {'tools': ['write'], 'final': 'Saved', 'changedFiles': ['a.html'], 'fileHashes': {'a.html': 'sha'}}
        case = {'route': 'file', 'expectedFiles': ['a.html']}
        self.assertEqual(checks.check_trial(base, case)['route']['status'], 'pass')
        self.assertEqual(checks.check_trial({**base, 'tools': ['show_widget']}, case)['route']['status'], 'fail')
        self.assertEqual(checks.check_trial({**base, 'changedFiles': []}, case)['route']['status'], 'pending')

    def test_acceptance_is_not_factual_correctness(self):
        trial = {'widgets': [{'kind': 'html', 'callSeq': 2, 'resultSeq': 3}], 'tools': ['show_widget'], 'final': '8个元素最多3次就能找到。'}
        result = checks.check_trial(trial, {'route': 'widget', 'browser': {'scenario': 'binary'}})
        self.assertEqual(result['acceptance']['status'], 'pass')
        self.assertEqual(result['content']['status'], 'fail')
        trial['final'] = '请点击下一步。'
        self.assertEqual(checks.check_trial(trial, {'route': 'widget'})['content']['status'], 'pending')


FIXTURES = {
    'quantity': '''<button id="minus" aria-label="减少 1">−</button><output role="status" id="quantity">2</output><button id="plus" aria-label="增加 1">+</button><div>0</div><div>1</div><div>2</div><div>3</div><div>4</div><div>5</div><script>let q=2;function render(){document.getElementById('quantity').textContent=q;document.getElementById('minus').disabled=q===0;document.getElementById('plus').disabled=q===(BAD?6:5)}document.getElementById('minus').onclick=()=>{q--;render()};document.getElementById('plus').onclick=()=>{q++;render()};render()</script>''',
    'heat': '''<h2>节点温度（°C）</h2><div role="img" id="rod"></div><button id="next">单步</button><button id="reset">重置</button><script>let n=0;function render(){const v=[[100,0,0,0,0],[100,25,0,0,0],[100,37.5,BAD?7.25:6.25,0,0]][n];const rod=document.getElementById('rod');rod.innerHTML=v.map((t,i)=>'<div>节点'+(i+1)+' · x='+i+'<div>'+t.toFixed(2)+'</div></div>').join('');rod.setAttribute('aria-label',v.map((t,i)=>'T'+(i+1)+' '+t.toFixed(1)+' 摄氏度').join('，'))}document.getElementById('next').onclick=()=>{n=Math.min(n+1,2);render()};document.getElementById('reset').onclick=()=>{n=0;render()};render()</script>''',
    'binary': '''<div>low<div id="low">0</div></div><div>mid 刚比较<div id="mid">—</div></div><div>high<div>7</div></div><div id="found"></div><button id="next">下一步</button><button id="reset">重置</button><script>let n=0;function render(){document.getElementById('low').textContent=n?4:0;document.getElementById('mid').textContent=n===0?'—':n===1?(BAD?4:3):5;document.getElementById('found').textContent=n===2?'命中下标5':'';document.getElementById('next').disabled=n===2}document.getElementById('next').onclick=()=>{n++;render()};document.getElementById('reset').onclick=()=>{n=0;render()};render()</script>''',
    'cache': '''<label>命中率<input id="s" type="range" min="0" max="100" step="50" value="0"></label><p>总成本 <output id="cost"></output></p><p>命中 <output id="hit"></output></p><p>未命中 <output id="miss"></output></p><script>const s=document.getElementById('s');function render(){const p=+s.value;document.getElementById('hit').textContent=p*10;document.getElementById('miss').textContent=1000-p*10;document.getElementById('cost').textContent=(1-.9*p/100)+(BAD?.02:0)}s.addEventListener('input',render);render()</script>''',
    'backoff': '''<p>累计等待 <output id="sum">0</output></p><p>下一次等待 <output id="wait">0</output></p><div id="history"></div><button id="next">下一步</button><button id="reset">重置</button><script>let n=0;const next=document.getElementById('next');function render(){document.getElementById('sum').textContent=[0,0,1,3][n];document.getElementById('wait').textContent=[0,1,BAD?9:2,0][n];document.getElementById('history').textContent=['第1次失败','第2次失败','第3次成功'].slice(0,n).join('；');next.disabled=n===3}next.onclick=()=>{n++;render()};document.getElementById('reset').onclick=()=>{n=0;render()};render()</script>''',
    'filter': '''<label><input type="radio" name="state" value="进行中" checked>进行中</label><label><input type="radio" name="state" value="已完成">已完成</label><label>负责人<input id="owner"></label><button id="apply" disabled>应用</button><div id="summary"></div><script>const owner=document.getElementById('owner'),apply=document.getElementById('apply');owner.oninput=()=>apply.disabled=!owner.value;apply.onclick=()=>document.getElementById('summary').textContent='已应用：'+(BAD?'进行中':document.querySelector('input[name=state]:checked').value)+' '+owner.value</script>''',
    'errors': '''<button id="day4">第4天</button><button id="day2">第2天</button><p id="selected">未选择</p><button id="ask">分析所选日期</button><script>let day=0;document.getElementById('day4').onclick=()=>{day=4;document.getElementById('selected').textContent='已选第4天'};document.getElementById('day2').onclick=()=>{day=2;document.getElementById('selected').textContent='已选第2天'};document.getElementById('ask').onclick=()=>window.dshWidget.sendPrompt('请分析第'+(BAD?4:day)+'天，错误率'+(BAD||day===4?'2.8':'0.5')+'%')</script>''',
}


@unittest.skipUnless(REPO is not None and (REPO / 'apps/web/node_modules/playwright').exists(), 'Set DSH_EVAL_REPO to a DSH Web checkout with Playwright installed for browser checker calibration.')
class BrowserChecks(unittest.TestCase):
    def test_known_good_and_bad_states(self):
        with tempfile.TemporaryDirectory(prefix='visualizer-grader-') as directory:
            base = Path(directory)
            for scenario, template in FIXTURES.items():
                for bad in [False, True]:
                    with self.subTest(scenario=scenario, bad=bad):
                        run = base / (scenario + ('-bad' if bad else '-good'))
                        run.mkdir()
                        source = template.replace('BAD', 'true' if bad else 'false')
                        (run / 'source.html').write_text(source)
                        trial = {'schemaVersion': 2, 'id': run.name, 'caseId': scenario, 'expectedRoute': 'widget', 'widgets': [{'kind': 'html', 'source': 'source.html', 'preview': 'preview.html', 'sha256': hashlib.sha256(source.encode()).hexdigest()}]}
                        (run / 'trial.json').write_text(json.dumps(trial))
                        (run / 'cases.json').write_text(json.dumps({'cases': [{'id': scenario, 'route': 'widget', 'browser': {'scenario': scenario}}]}))
                        script = "import fs from 'node:fs';import {buildInteractiveSrcDoc} from " + json.dumps(str(REPO / 'packages/visualizer/ui-visualizer/src/client/srcdoc.ts')) + ";fs.writeFileSync(process.argv[2],buildInteractiveSrcDoc(fs.readFileSync(process.argv[1],'utf8'),{}));"
                        subprocess.run([NODE, '--input-type=module', '-e', script, str(run / 'source.html'), str(run / 'preview.html')], check=True, capture_output=True, timeout=15)
                        command = [NODE, str(ROOT / 'render-check.mjs'), '--trial', str(run / 'trial.json'), '--cases', str(run / 'cases.json'), '--output', str(run), '--repo', str(REPO)]
                        subprocess.run(command, check=True, capture_output=True, timeout=45)
                        result = json.loads((run / 'browser-checks.json').read_text())
                        key = 'followupPayload' if scenario == 'errors' else 'interaction'
                        self.assertEqual(result['checks'][key]['status'], 'fail' if bad else 'pass', result['checks'][key])
                        self.assertEqual(result['checks']['content']['status'], 'pending')
                        # A dark foreground with a light hover token produced false visual failures.
                        light = result['themeTokens']['light']
                        dark = result['themeTokens']['dark']
                        self.assertNotEqual(light['--dsw-alias-interactive-bg-hover'], dark['--dsw-alias-interactive-bg-hover'])
                        self.assertNotEqual(light['--dsw-alias-label-primary'], dark['--dsw-alias-label-primary'])
                        self.assertTrue(all(value for value in dark.values()))


if __name__ == '__main__':
    unittest.main()
