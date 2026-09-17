"""Evidence-based routes and narrow inline facts, without modifying historical results."""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def verdict(status, reason, **evidence):
    assert status in {'pass', 'fail', 'pending', 'not_applicable', 'error'}
    return {'status': status, 'reason': reason, 'evidence': evidence}


def check_trial(trial, case):
    route = trial.get('expectedRoute', case.get('route', 'unknown'))
    tools = [x if isinstance(x, str) else x.get('name', x.get('tool', ''))
             for x in trial.get('trace', {}).get('tools', trial.get('tools', []))]
    widgets, rejected = trial.get('widgets', []), trial.get('rejected', [])
    shown = tools.count('show_widget')
    changes = trial.get('workspaceChanges', [])
    changed = trial.get('changedFiles', []) or [entry['path'] for entry in changes if entry.get('beforeSha256') != entry.get('afterSha256')]
    files = {**trial.get('fileHashes', {}), **{entry['path']: entry.get('afterSha256') for entry in changes}}
    for artifact in trial.get('artifacts', []):
        if isinstance(artifact, dict):
            files[artifact.get('name', artifact.get('path', ''))] = artifact.get('sha256')
    expected_files = case.get('expectedFiles', []) or {'R04': ['sales.svg'], 'N01': ['clamp.mjs'], 'N04': ['index.html']}.get(case.get('id'), [])
    final = trial.get('final', '')
    status = trial.get('status', trial.get('turnEnd', ''))
    result = {
        'route': verdict('pending', 'No sufficient delivery evidence yet.'),
        'acceptance': verdict('not_applicable', 'This case does not require an inline widget.'),
        'content': verdict('not_applicable', 'Ordinary-task correctness is outside this route check; historical results remain unchanged.'),
    }
    if status in ['blocked', 'error', 'failed', 'timeout', 'timed_out', 'cancelled', 'canceled', 'running'] or trial.get('timedOut'):
        result['route'] = verdict('pending', 'Trial did not complete; do not score a setup/transport block as a product routing failure.', trialStatus=status)
        return result
    if route in ['widget', 'optional']:
        known_content = trial.get('checks', {}).get('content', {})
        result['content'] = known_content if known_content.get('status') == 'fail' else verdict('pending', 'Content and visual quality need case oracles and human review; acceptance is not correctness.')
        if not widgets:
            if route == 'optional' and final.strip() and not shown:
                result['route'] = verdict('pass', 'Text is an allowed delivery route; its quality is not graded here.')
            else:
                result['route'] = verdict('fail' if shown or final.strip() else 'pending', 'No accepted inline visual was delivered.', showWidgetCalls=shown)
            if shown:
                result['acceptance'] = verdict('fail' if rejected else 'pending', 'No accepted widget receipt is available.', rejected=rejected)
            return result
        allowed = case.get('allowedKinds', ['svg', 'html'])
        wrong = [w.get('kind') for w in widgets if w.get('kind') not in allowed]
        result['route'] = verdict('fail' if wrong else 'pass', 'Source kind is outside the case contract.' if wrong else 'An allowed inline visual was delivered.', kinds=[w.get('kind') for w in widgets], allowedKinds=allowed)
        first = min((w.get('callSeq', float('inf')) for w in widgets), default=float('inf'))
        earlier = [r for r in rejected if r.get('callSeq', -1) < first]
        receipts = all(isinstance(w.get('resultSeq'), int) for w in widgets)
        result['acceptance'] = verdict('fail' if earlier else 'pass' if receipts else 'pending', 'First submission rejected; later acceptance does not erase it.' if earlier else 'Collected receipt proves Host acceptance only.' if receipts else 'No accepted result sequence recorded.', acceptedCount=len(widgets), earlierRejections=earlier)
        if case.get('browser', {}).get('scenario') == 'binary' or case.get('id') == 'I01':
            text = re.sub(r'[*_`]', '', final)
            bad = re.search(r'(?:8|八)\s*(?:个|個)?\s*元素[^。！？\n]{0,65}(?:最多|至多|最坏|最壞)[^。！？\n]{0,25}(?:3|三)\s*(?:次|轮|輪)', text)
            if not bad:
                bad = re.search(r'(?:worst.case|at most)[^.\n]{0,35}3\s*(?:comparisons|steps)[^.\n]{0,50}8\s*(?:items|elements)', text, re.I)
            if bad:
                result['content'] = verdict('fail', 'Eight-element binary search can require four comparisons; the three-comparison worst-case claim is false.', quote=bad.group(), oracle='floor(log2(8)) + 1 = 4')
        return result
    if shown or widgets:
        result['route'] = verdict('fail', 'This delivery route must not invoke show_widget.', showWidgetCalls=shown, acceptedWidgets=len(widgets))
        return result
    if route in ['text', 'code']:
        if changed:
            result['route'] = verdict('fail', 'Reply-only task changed workspace files.', changedFiles=changed)
        elif not final.strip():
            result['route'] = verdict('pending', 'No final reply; zero widget calls alone is insufficient.')
        elif route == 'code' and not re.search(r'```[^\n]*\n\S', final):
            result['route'] = verdict('pending', 'A reply exists, but code delivery was not identifiable automatically.')
        else:
            result['route'] = verdict('pass', 'Requested reply form delivered without widget or workspace edits; semantic correctness is not evaluated.', form=route, tools=tools)
    elif route in ['file', 'project']:
        missing = [name for name in expected_files if not files.get(name)]
        writes = any(re.search(r'(?:write|edit|patch|bash|shell|exec)', name) for name in tools)
        if not expected_files:
            result['route'] = verdict('pending', 'No expectedFiles contract; absence of show_widget is insufficient.')
        elif missing:
            result['route'] = verdict('fail' if final.strip() else 'pending', 'Required file-delivery evidence is missing.', missingFiles=missing)
        elif not writes or not all(name in changed for name in expected_files):
            result['route'] = verdict('pending', 'Files exist, but writes and recorded changes to all required files are not established.', changedFiles=changed, tools=tools)
        else:
            result['route'] = verdict('pass', 'Required files changed and have content hashes plus a writing-tool trace; content correctness is not graded.', fileHashes={name: files[name] for name in expected_files})
    elif route == 'plugin':
        required = case.get('routeEvidence', {}).get('requiredTools', ['cordis_inspect_list', 'cordis_inspect_query'])
        missing = [name for name in required if name not in tools]
        result['route'] = verdict('pending', 'Cordis workflow evidence is incomplete.' if missing else 'API inspection is evidenced; plugin installation/persistence and real UI behavior require the configured Web environment.', missingTools=missing, tools=tools)
    else:
        result['route'] = verdict('pending', 'No checker for this route.', expectedRoute=route)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    select = parser.add_mutually_exclusive_group(required=True)
    select.add_argument('--trial', type=Path)
    select.add_argument('--legacy-run')
    parser.add_argument('--cases', type=Path, help='Override the frozen round cases; defaults to the round snapshot, then root cases.')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    trial = json.loads(args.trial.read_text()) if args.trial else next(r for r in json.loads((ROOT / 'dsh-results.json').read_text())['runs'] if r['id'] == args.legacy_run)
    case_id = trial.get('caseId', trial.get('case'))
    frozen = args.trial.resolve().parent.parent / 'cases.json' if args.trial else None
    cases_path = args.cases or (frozen if frozen and frozen.exists() else ROOT / 'cases.json')
    cases_bytes = cases_path.read_bytes()
    case = next((c for c in json.loads(cases_bytes)['cases'] if c['id'] == case_id), None)
    if case is None and args.legacy_run:
        scenario = {'I01': 'binary', 'I02': 'heat', 'F01': 'sales'}.get(case_id)
        case = {'id': case_id, 'route': 'widget' if scenario else trial.get('expectedRoute', 'unknown'), 'browser': {'scenario': scenario}}
    if case is None:
        raise ValueError(f'Case contract not found: {case_id}')
    result = {'schemaVersion': 2, 'trialId': trial['id'], 'caseId': case_id,
              'scope': 'route evidence and narrow inline facts, not ordinary-task correctness',
              'checkerSha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'casesSha256': hashlib.sha256(cases_bytes).hexdigest(), 'casesPath': os.path.relpath(cases_path.resolve(), ROOT),
              'checks': check_trial(trial, case)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'id': trial['id'], 'output': str(args.output), 'checks': {k: v['status'] for k, v in result['checks'].items()}}, ensure_ascii=False))


if __name__ == '__main__':
    main()
