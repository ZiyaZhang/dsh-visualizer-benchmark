"""Report observed counts and artifact-bound human ratings without a weighted score."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path

import serve


def summarize(stage, annotation_path):
    data = serve.catalog()
    if data['catalogErrors']:
        raise ValueError('; '.join(data['catalogErrors']))
    selected = next((s for s in data['stages'] if s['id'] == stage), None)
    if selected is None:
        raise ValueError('Unknown stage: ' + stage)
    ids = set(selected['trialIds'])
    trials = [t for t in data['trials'] if t['id'] in ids]
    annotations = serve.read_json(annotation_path, {'schemaVersion': 2, 'reviews': {}})
    if annotations.get('schemaVersion') != 2:
        raise ValueError('Expected v2 annotations; historical preference is not dimensional scoring')
    reviews = annotations.get('reviews', {})
    gates = {}
    for trial in trials:
        for name, check in trial['checks'].items():
            if isinstance(check, dict):
                gates.setdefault(name, Counter())[check.get('status', 'pending')] += 1
    quality = [t for t in trials if t['qualityEligible']]
    dimensions = {d: Counter() for d in serve.DIMENSIONS}
    reviewed, pending, stale = [], [], []
    rows = []
    for trial in trials:
        review = reviews.get(trial['id'])
        human_status = 'not_applicable' if not trial['qualityEligible'] else 'unreviewed'
        if review and review.get('artifactHash') != trial['artifactHash']:
            stale.append(trial['id'])
            human_status = 'stale'
        elif review and trial['qualityEligible']:
            # Revalidate fields as well as hash; invalid labels cannot enter the report.
            payload = {k: review[k] for k in ('trialId', 'artifactHash', 'status', 'ratings',
                       'naReasons', 'correctness', 'completion', 'notes', 'pendingReason')}
            serve.validate_review(payload, data)
            human_status = review['status']
            if human_status == 'complete':
                reviewed.append(trial['id'])
                for dimension in dimensions:
                    dimensions[dimension][str(review['ratings'][dimension])] += 1
            else:
                pending.append(trial['id'])
        rows.append({'trialId': trial['id'], 'caseId': trial['caseId'], 'arm': trial['arm'],
                     'status': trial['status'], 'humanStatus': human_status,
                     'checks': {k: v.get('status', 'pending') for k, v in trial['checks'].items() if isinstance(v, dict)}})
    return {'schemaVersion': 2, 'generatedAt': datetime.now(timezone.utc).isoformat(), 'stage': stage, 'description': selected['description'],
            'planned': len(trials), 'trialStatuses': dict(Counter(t['status'] for t in trials)),
            'gates': {k: dict(v) for k, v in gates.items()},
            'human': {'eligible': len(quality), 'completed': len(reviewed), 'needsReview': len(pending),
                      'unreviewed': len(quality) - len(reviewed) - len(pending) - len(stale),
                      'stale': stale, 'dimensions': {k: dict(v) for k, v in dimensions.items()}},
            'trials': rows,
            'limitations': ['No weighted overall score.', 'Pending, error and not_applicable are not passes.',
                            'Historical calibration is not a fresh prompt comparison.',
                            'Preview messages do not verify real Web follow-up or repair.']}


def markdown(report):
    human = report['human']
    lines = [f"# {report['stage']}", '', report['description'], '',
             f"生成时快照：{report.get('generatedAt', '未记录')}。实时人工进度以本机打标页为准。", '',
             f"计划 {report['planned']} 份；状态：{json.dumps(report['trialStatuses'], ensure_ascii=False)}。", '',
             f"内联人工评分：{human['completed']} / {human['eligible']} 完成，"
             f"{human['needsReview']} 待核，{human['unreviewed']} 未评，{len(human['stale'])} 份内容已变。", '',
             '| 检查 | 通过 | 失败 | 待核 | 检查/环境错误 | 不适用 |',
             '| --- | ---: | ---: | ---: | ---: | ---: |']
    for name, counts in report['gates'].items():
        lines.append('| ' + name + ' | ' + ' | '.join(str(counts.get(k, 0)) for k in ('pass', 'fail', 'pending', 'error', 'not_applicable')) + ' |')
    lines += ['', '| 人工维度 | 0 | 1 | 2 | N/A |', '| --- | ---: | ---: | ---: | ---: |']
    for name, counts in human['dimensions'].items():
        lines.append('| ' + name + ' | ' + ' | '.join(str(counts.get(k, 0)) for k in ('0', '1', '2', 'n/a')) + ' |')
    lines += ['', '零条评分表示尚无人工评分，不表示质量为零。检查分母按适用项解释；完整逐次状态见 summary.json。', '',
              '本报告不自动选择赢家。选择记录需要说明改善了哪些失败、有哪些退步、哪些证据仍不足。', '']
    return '\n'.join(lines)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', default='calibration')
    parser.add_argument('--annotations', type=Path, default=serve.DEFAULT_STATE)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    report = summarize(args.stage, args.annotations)
    if args.output:
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / 'summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        (args.output / 'summary.md').write_text(markdown(report))
    print(markdown(report))
