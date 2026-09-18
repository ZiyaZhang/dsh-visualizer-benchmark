"""Local review of fresh trials and explicitly retained human-reviewed examples."""
import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent
DEFAULT_STATE = ROOT.parent / '.artifacts/visualizer/annotations-v2.json'
LEGACY_STATE = DEFAULT_STATE.with_name('annotations.json')
LOCK = Lock()
DIMENSIONS = ('understanding', 'layout', 'operability', 'focus')


def read_json(path, fallback):
    return json.loads(path.read_text()) if path.exists() else fallback


def read_reviews(path):
    data = read_json(path, {'schemaVersion': 2, 'reviews': {}, 'revisions': []})
    if data.get('schemaVersion') != 2:
        raise ValueError('四维标注文件版本不兼容；旧 annotations.json 保持不变')
    # Preserve a published label verbatim; newer local edits take precedence.
    example = read_json(ROOT / 'results/reviewed-example/observation.json', {})
    if example:
        review = example['review']
        data['reviews'].setdefault(review['trialId'], review)
    return data


def public_file(relative):
    if not isinstance(relative, str) or not relative:
        return None
    target = (ROOT / relative.lstrip('/')).resolve()
    return target if target.is_relative_to(ROOT) and target.is_file() else None


def artifact_hash(trial):
    """Bind annotations to the entire answer, not only its first accepted widget."""
    digest = hashlib.sha256()
    def add(label, value):
        raw = value if isinstance(value, bytes) else str(value).encode('utf-8')
        digest.update(label.encode('utf-8') + b'\0' + str(len(raw)).encode() + b'\0' + raw)
    add('prompt', trial['prompt'])
    add('final', trial.get('final', ''))
    add('rendererSha256', trial.get('rendererSha256') or '')
    for filename in ('rubric.md', 'label.html', 'vendor/marked-16.4.2.js'):
        add('review-presentation-' + filename, (ROOT / filename).read_bytes())
    for index, widget in enumerate(trial.get('widgets', [])):
        add(f'widget-{index}', json.dumps({key: widget.get(key) for key in ('title', 'kind', 'callSeq', 'resultSeq', 'replace')}, sort_keys=True, ensure_ascii=False))
        for kind in ('source', 'preview'):
            path = public_file(widget.get(kind))
            add(f'widget-{index}-{kind}', path.read_bytes() if path else 'MISSING:' + str(widget.get(kind)))
    return digest.hexdigest()


def check(status, reason):
    return {'status': status, 'reason': reason}


def merge_checks(original, incoming):
    """Keep established failures and distinguish them from later uninspected checks."""
    combined = dict(original)
    rank = {'pending': 0, 'not_applicable': 1, 'pass': 2, 'error': 3, 'fail': 4}
    for key, value in incoming.items():
        if not isinstance(value, dict) or 'status' not in value:
            continue
        prior = combined.get(key)
        if not isinstance(prior, dict) or prior == value:
            combined[key] = value
            continue
        preferred = value if rank.get(value['status'], 0) > rank.get(prior.get('status'), 0) else prior
        evidence = prior.get('records', [{k: v for k, v in prior.items() if k != 'records'}])
        extra = {k: v for k, v in value.items() if k != 'records'}
        combined[key] = {**preferred, 'records': evidence + ([extra] if extra not in evidence else [])}
    return combined


def route_name(value):
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return value.get('must') or value.get('kind') or value.get('mode') or 'optional'
    return 'unknown'


def normalize_trial(raw, case, round_id='history', historical=False):
    trial = dict(raw)
    trial['localTrialId'] = str(raw['id'])
    trial['id'] = round_id + '/' + trial['localTrialId']
    trial['roundId'] = round_id
    trial['caseId'] = raw.get('caseId') or raw.get('case') or case.get('id', '')
    trial['prompt'] = raw.get('prompt', case.get('prompt', ''))
    trial['oracle'] = case.get('oracle', case.get('facts', []))
    trial['caseTitle'] = case.get('title') or {'I01': '二分查找', 'I02': '热传导', 'F01': '地区选择与追问'}.get(trial['caseId'], trial['caseId'])
    trial['expectedRoute'] = raw.get('expectedRoute', case.get('route', 'unknown'))
    trial['widgets'] = [dict(widget) for widget in raw.get('widgets') or []]
    trial['final'] = raw.get('final') or ''
    trial['arm'] = raw.get('arm') or raw.get('variant') or 'unknown'
    trial['historical'] = historical
    trial['modelLabel'] = raw.get('modelLabel') or raw.get('model') or 'DeepSeek-V41-Flash'
    trial['effort'] = raw.get('effort') or 'high'
    route = route_name(trial['expectedRoute'])
    trial['qualityEligible'] = case.get('qualityReview', route in ('widget', 'inline', 'html', 'svg', 'required') or (bool(trial['widgets']) and route not in ('text', 'code', 'file', 'project', 'tool', 'plugin', 'none', 'forbidden')))
    trial['qualityExpected'] = trial['qualityEligible']
    if route in ('optional', 'either') and not trial['widgets']:
        trial['qualityEligible'] = False
    trial['interactionRequired'] = case.get('interactionRequired')
    if historical:
        browser = raw.get('browserChecks') or {}
        trial['status'] = 'timed_out' if raw.get('timedOut') else ('completed' if raw.get('exitCode') == 0 else 'error')
        trial['trace'] = {'tools': raw.get('tools', []), 'referencesRead': raw.get('referencesRead', []), 'rejected': raw.get('rejected', [])}
        trial['checks'] = {'route': check('pass' if raw.get('routePassed') is True else 'fail' if raw.get('routePassed') is False else 'pending', '历史轨迹中的路由检查；不代表人工质量评分。')}
        if trial['qualityEligible']:
            rejected = raw.get('rejected') or []
            trial['checks']['acceptance'] = check('fail' if rejected else 'pass' if trial['widgets'] else 'pending', f"接受 {len(trial['widgets'])} 份组件，拒绝 {len(rejected)} 次调用；完整拒绝原因见轨迹。")
            for name, field in [('render', 'initialRender'), ('interaction', 'transitions')]:
                value = browser.get(field, browser.get('passed'))
                trial['checks'][name] = check('pass' if value is True else 'fail' if value is False else 'pending', '；'.join(browser.get('notes', [])) or '尚无逐项浏览器检查记录。')
            if browser.get('contentIssue'):
                trial['checks']['content'] = check('fail', str(browser['contentIssue']))
            trial['evidenceNotes'] = browser.get('notes', [])
            trial['evidenceViewport'] = browser.get('viewport')
            trial['evidenceAppearance'] = browser.get('appearance')
    else:
        trial['status'] = raw.get('status', 'planned')
        trial['trace'] = raw.get('trace') or {'tools': [], 'referencesRead': []}
        trial['checks'] = raw.get('checks') or {'route': check('pending', '尚未运行。')}
        if raw.get('historicalBrowserChecks'):
            trial['evidenceNotes'] = raw['historicalBrowserChecks'].get('notes', [])
            trial['evidenceViewport'] = raw['historicalBrowserChecks'].get('viewport')
            trial['evidenceAppearance'] = raw['historicalBrowserChecks'].get('appearance')
    if not trial['widgets'] and trial['status'] in ('planned', 'running', 'error', 'timed_out'):
        trial['qualityEligible'] = False
    for widget in trial['widgets']:
        widget['sourceAvailable'] = public_file(widget.get('source')) is not None
        widget['previewAvailable'] = public_file(widget.get('preview')) is not None
    trial['artifactHash'] = artifact_hash(trial)
    return trial


def catalog():
    current_cases = read_json(ROOT / 'cases.json', {'cases': []})
    trials, stages, errors = [], [], []
    reviewed = read_json(ROOT / 'results/reviewed-example/observation.json', {})
    if reviewed:
        trial = normalize_trial(reviewed['trial'], reviewed['case'], reviewed['trial']['roundId'])
        trials.append(trial)
        stages.append({'id': 'reviewed-example', 'title': '保留的人工标注样本',
                       'trialIds': [trial['id']],
                       'description': '仅一份历史人工记录，不是 A/B 结论。原正确性标注与正文最坏次数存在冲突，需人工复核。'})
    for manifest_path in sorted((ROOT / 'results').glob('*/manifest.json')):
        try:
            manifest = read_json(manifest_path, {})
            round_id = str(manifest.get('roundId') or manifest.get('id') or manifest_path.parent.name)
            snapshot = read_json(manifest_path.parent / 'cases.json', current_cases)
            cases = {case['id']: case for case in snapshot.get('cases', [])}
            ids = []
            for item in manifest.get('trials', []):
                planned = {'id': item} if isinstance(item, str) else item
                trial_id = str(planned.get('id') or planned.get('trialId'))
                candidate = manifest_path.parent / trial_id / 'trial.json'
                if not candidate.resolve().is_relative_to(manifest_path.parent.resolve()):
                    raise ValueError('trial 路径超出本轮目录')
                raw = read_json(candidate, {**planned, 'id': trial_id, 'status': 'planned'})
                raw.setdefault('id', trial_id)
                case_id = raw.get('caseId') or planned.get('caseId') or raw.get('case')
                raw.setdefault('caseId', case_id)
                for filename in ('checks.json', 'browser-checks.json'):
                    supplement = read_json(candidate.parent / filename, {})
                    raw['checks'] = merge_checks(raw.get('checks', {}), supplement.get('checks', {}))
                trial = normalize_trial(raw, cases.get(case_id, {}), round_id)
                trials.append(trial)
                ids.append(trial['id'])
            stages.append({'id': round_id, 'title': '实验：' + round_id, 'trialIds': ids,
                           'description': '来自冻结 manifest；未评结果仅供本地审核，不作为已验证结论。',
                           'comparisonId': manifest.get('comparisonId'), 'arm': manifest.get('arm')})
        except (ValueError, KeyError, TypeError, OSError) as error:
            errors.append(f'{manifest_path.parent.name}: {error}')
    # A shared review queue hides candidate labels in the ordinary scoring flow.
    # Full source records remain inspectable; this is not a claim of sealed blinding.
    comparisons = {s.get('comparisonId') for s in stages if s.get('comparisonId')}
    for comparison in sorted(comparisons):
        arms = [s for s in stages if s.get('comparisonId') == comparison and s.get('arm') in ('A', 'B')]
        if {s['arm'] for s in arms} != {'A', 'B'}:
            continue
        rounds = {s['id'] for s in arms}
        members = [t for t in trials if t['roundId'] in rounds and t['qualityExpected']]
        members.sort(key=lambda t: (t['caseId'], t.get('repeat', 1), hashlib.sha256((comparison + t['id']).encode()).hexdigest()))
        stages.insert(1, {'id': 'compare-' + comparison, 'title': '同题混排：' + comparison,
                          'trialIds': [t['id'] for t in members],
                          'description': '同题同次序号的两个候选按固定顺序混排，逐份评价；版本信息在评分后查看。路由对照另列，未生成项仍保留。'})
    if not stages:
        stages.append({'id': 'empty', 'title': '尚无本地运行', 'trialIds': [], 'description': '按 README 运行题集后再人工评审。'})
    return {
        'schemaVersion': 2, 'trials': trials, 'stages': stages, 'defaultStage': stages[0]['id'], 'catalogErrors': errors,
        'dimensions': list(DIMENSIONS), 'evidence': '已有检查来自脚本或代理核查，不是人工评分；未评不计为 0。',
        'taskCount': len(current_cases.get('cases', []))
    }


def validate_review(payload, data):
    expected = {'trialId', 'artifactHash', 'status', 'ratings', 'naReasons', 'correctness', 'completion', 'notes', 'pendingReason'}
    if set(payload) != expected:
        raise ValueError('评分字段不完整或含未知字段')
    trial = next((trial for trial in data['trials'] if trial['id'] == payload['trialId']), None)
    if trial is None:
        raise ValueError('未知运行记录')
    if not trial['qualityEligible']:
        raise ValueError('非内联任务只记录路由，不保存视觉质量评分')
    if payload['artifactHash'] != trial['artifactHash']:
        raise ValueError('成品内容已变：请刷新并重新查看后再保存')
    if payload['status'] not in ('complete', 'needs_review'):
        raise ValueError('请选择完成评分或待核')
    ratings, reasons = payload['ratings'], payload['naReasons']
    if not isinstance(ratings, dict) or set(ratings) != set(DIMENSIONS) or not isinstance(reasons, dict) or set(reasons) - set(DIMENSIONS):
        raise ValueError('四维评分字段无效')
    for dimension, value in ratings.items():
        if value is not None and not (type(value) is int and value in (0, 1, 2)) and value != 'n/a':
            raise ValueError('评分只能为 0、1、2、N/A 或未评')
        if value == 'n/a' and not str(reasons.get(dimension, '')).strip():
            raise ValueError('N/A 必须说明原因')
        if payload['status'] == 'complete' and value is None:
            raise ValueError('请填完四维；无法判断可记待核，不能用 0 代替未评')
    for field in ('correctness', 'completion'):
        if payload[field] not in ('pass', 'fail', 'uncertain', 'not_reviewed'):
            raise ValueError('内容与完成情况的判断值无效')
        if payload['status'] == 'complete' and payload[field] == 'not_reviewed':
            raise ValueError('请确认内容正确性和任务完成情况；无法确定可明确选“尚无法判断”')
    for field in ('notes', 'pendingReason'):
        if not isinstance(payload[field], str) or len(payload[field]) > 4000:
            raise ValueError('备注或待核原因最多 4000 字')
    if any(not isinstance(value, str) or len(value) > 1000 for value in reasons.values()):
        raise ValueError('N/A 原因最多 1000 字')
    if payload['status'] == 'needs_review' and not payload['pendingReason'].strip():
        raise ValueError('请写明待核原因')
    return {**payload, 'savedAt': datetime.now(timezone.utc).isoformat(), 'reviewType': 'human', 'schemaVersion': 2}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, *_args):
        pass

    def guess_type(self, path):
        return 'text/plain; charset=utf-8' if str(path).endswith(('.source.html', '.md', '.py', '.mjs', '.yaml')) else super().guess_type(path)

    def send_json(self, data, status=200):
        body = (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_reviews(self):
        return read_reviews(self.server.state_path)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path in ('/api/catalog', '/api/results'):
            return self.send_json(catalog())
        if path in ('/api/annotations', '/api/annotations/export'):
            with LOCK:
                return self.send_json(self.read_reviews())
        if path == '/api/annotations/legacy':
            return self.send_json(read_json(LEGACY_STATE, {'schemaVersion': 1, 'reviews': {}}))
        target = (ROOT / unquote(path).lstrip('/')).resolve()
        if not target.is_relative_to(ROOT) or any(part.startswith('.') for part in target.relative_to(ROOT).parts):
            return self.send_error(404)
        if target.is_dir():
            target = target / 'index.html'
        if target.suffix not in {'.html', '.json', '.jpg', '.jpeg', '.png', '.css', '.js', '.md', '.txt', '.py', '.mjs', '.yaml'}:
            return self.send_error(404)
        return super().do_GET()

    def do_POST(self):
        if self.path != '/api/annotations':
            return self.send_error(404)
        allowed = {f'http://127.0.0.1:{self.server.server_port}', f'http://localhost:{self.server.server_port}'}
        if self.headers.get('Origin') not in allowed:
            return self.send_json({'error': '仅允许本地打标页保存'}, 403)
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 65536:
                raise ValueError('请求大小无效')
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError('请求必须是对象')
            review = validate_review(payload, catalog())
            with LOCK:
                saved = self.read_reviews()
                old = saved['reviews'].get(review['trialId'])
                if old:
                    saved.setdefault('revisions', []).append(old)
                saved['reviews'][review['trialId']] = review
                path = self.server.state_path
                path.parent.mkdir(parents=True, exist_ok=True)
                temp = path.with_suffix('.tmp')
                temp.write_text(json.dumps(saved, ensure_ascii=False, indent=2) + '\n')
                temp.chmod(0o600)
                os.replace(temp, path)
            self.send_json({'saved': True, 'review': review})
        except (ValueError, TypeError, KeyError, AttributeError) as error:
            self.send_json({'error': str(error)}, 400)


def make_server(port=3092, state_path=DEFAULT_STATE):
    state_path = Path(state_path).resolve()
    if state_path == LEGACY_STATE.resolve() or state_path.is_relative_to(ROOT):
        raise ValueError('新标注必须保存在网页目录外，且不能覆盖旧 annotations.json')
    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.state_path = state_path
    return server


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=3092)
    parser.add_argument('--state', type=Path, default=DEFAULT_STATE)
    args = parser.parse_args()
    server = make_server(args.port, args.state)
    print(f'Local review: http://127.0.0.1:{server.server_port}/label.html', flush=True)
    server.serve_forever()
