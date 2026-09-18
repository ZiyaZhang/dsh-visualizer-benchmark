"""Freeze and run a small Visualizer cohort; raw Sessions stay outside the public site.

The freeze/first-attempt pattern follows Dudu-0223/dsh-benchmarks/file-references
(run.py at 25f7ec5c, MIT). Historical runs are archived outside this shared suite.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
DEFAULT_PRIVATE = ROOT.parent / '.artifacts/visualizer/runs'
SAFE_ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]*$')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(path)


def git(repo, *args):
    return subprocess.check_output(['git', *args], cwd=repo, text=True).strip()


def node_binary():
    found = os.environ.get('DSH_EVAL_NODE') or shutil.which('node')
    if not found:
        raise ValueError('Node is unavailable; put the built product Node version on PATH or set DSH_EVAL_NODE')
    version = tuple(map(int, subprocess.check_output([found, '-p', 'process.versions.node'], text=True).strip().split('.')))
    if version < (22, 19, 0):
        raise ValueError('Node 22.19 or newer is required to load the shipped TypeScript renderer')
    return str(Path(found).resolve())


def snapshot_runtime(repo, destination):
    """Freeze actual executable model files and assets, not merely source revision."""
    host = repo / 'packages/visualizer/tool-visualizer'
    visualizer = (host / 'package.json').exists()
    paths = ['apps/cli/lib/bin.js', 'packages/bundle/headless/lib/index.js',
             'packages/bundle/headless/cordis.patch.yml']
    if visualizer:
        paths += ['packages/visualizer/tool-visualizer/lib/index.js',
                  'packages/visualizer/tool-visualizer/lib/types/model.js',
                  'packages/visualizer/tool-visualizer/lib/types/client.js',
                  'packages/visualizer/ui-visualizer/src/client/srcdoc.ts',
                  'packages/visualizer/ui-visualizer/src/client/protocol.ts']
        for folder in ['src', 'lib/types', 'assets']:
            paths += [str(p.relative_to(repo)) for p in (host / folder).rglob('*')
                      if p.is_file() and p.suffix in ('.js', '.ts', '.md')]
    missing = [p for p in paths if not (repo / p).is_file()]
    if missing:
        raise ValueError('Runtime is not built; missing: ' + ', '.join(missing))
    hashes = {}
    for relative in sorted(set(paths)):
        source = repo / relative
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        hashes[relative] = digest(source)
    return visualizer, hashes


def unchanged(repo, hashes):
    return all((repo / relative).is_file() and digest(repo / relative) == sha
               for relative, sha in hashes.items())


def public_trial(manifest, planned, case):
    return {'schemaVersion': 2, 'id': planned['id'], 'roundId': manifest['id'],
            'caseId': case['id'], 'arm': manifest['arm'], 'repeat': planned['repeat'],
            'status': planned['status'], 'prompt': case['prompt'], 'expectedRoute': case['route'],
            'widgets': [], 'final': '', 'checks': {
                'route': {'status': 'pending', 'reason': 'Trial has not completed'},
                'acceptance': {'status': 'pending', 'reason': 'No artifact has been graded'}},
            'trace': {'tools': [], 'referencesRead': []}, 'usage': {}, 'elapsedSeconds': None,
            'sourceHead': manifest['sourceHead'], 'rendererSha256': manifest.get('rendererSha256')}


def freeze(args, node):
    public = ROOT / 'results' / args.round
    private = args.private_root / args.round
    if public.exists() or private.exists():
        raise ValueError('Round already exists; use --resume for its unstarted trials, or choose a new round ID')
    if git(args.repo, 'status', '--porcelain'):
        raise ValueError('Product checkout is dirty; commit the intended candidate or use a clean checkout before freezing')
    cases_bytes = (ROOT / 'cases.json').read_bytes()
    rubric_bytes = (ROOT / 'rubric.md').read_bytes()
    catalog = json.loads(cases_bytes)
    selected = [c for c in catalog['cases'] if args.split == 'all' or c.get('split') == args.split]
    if args.case:
        unknown = set(args.case) - {c['id'] for c in selected}
        if unknown:
            raise ValueError('Cases absent from selected split: ' + ', '.join(sorted(unknown)))
        selected = [c for c in selected if c['id'] in args.case]
    if not selected:
        raise ValueError('No cases selected')
    for case in selected:
        if not SAFE_ID.fullmatch(case['id']):
            raise ValueError('Case IDs must be safe directory names')
    private.mkdir(mode=0o700, parents=True)
    (private / 'inputs').mkdir()
    (private / 'inputs/cases.json').write_bytes(cases_bytes)
    (private / 'inputs/rubric.md').write_bytes(rubric_bytes)
    visualizer, hashes = snapshot_runtime(args.repo, private / 'inputs/runtime')
    # Import only: checks module resolution and compiled exports without starting a model request.
    imports = ['packages/bundle/headless/lib/index.js']
    if visualizer:
        imports += ['packages/visualizer/tool-visualizer/lib/types/model.js']
    probe = subprocess.run([node, '--input-type=module', '-e',
        'for (const p of process.argv.slice(1)) await import(p)',
        *[(args.repo / p).as_uri() for p in imports]], capture_output=True, text=True)
    if probe.returncode:
        (private / 'readiness-error.txt').write_text(probe.stderr)
        raise ValueError('Compiled runtime imports failed; diagnostic retained privately in readiness-error.txt')
    trials = [{'id': f'{c["id"]}-{args.arm}-{r}', 'caseId': c['id'], 'arm': args.arm,
               'repeat': r, 'status': 'planned'}
              for r in range(1, args.repeats + 1) for c in selected]
    if args.limit is not None:
        trials = trials[:args.limit]
    renderer = 'packages/visualizer/ui-visualizer/src/client/srcdoc.ts'
    manifest = {'schemaVersion': 2, 'id': args.round, 'roundId': args.round, 'arm': args.arm,
        'comparisonId': args.comparison_id or args.round, 'createdAt': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'model': 'deepseek-flash', 'modelLabel': 'DeepSeek-V41-Flash', 'reasoningEffort': 'high',
        'sourceHead': git(args.repo, 'rev-parse', 'HEAD'),
        'sourceParents': git(args.repo, 'show', '-s', '--format=%P', 'HEAD').split(),
        'masterHead': subprocess.run(['git', 'rev-parse', 'refs/remotes/origin/master'], cwd=args.repo, capture_output=True, text=True).stdout.strip() or None,
        'sourceDirtyPaths': git(args.repo, 'status', '--porcelain').splitlines(),
        'profile': 'headless + shipped Host Visualizer' if visualizer else 'headless',
        'visualizerAvailable': visualizer, 'casesSha256': hashlib.sha256(cases_bytes).hexdigest(),
        'rubricSha256': hashlib.sha256(rubric_bytes).hexdigest(),
        'runtimeHashes': hashes, 'rendererSha256': hashes.get(renderer), 'split': args.split,
        'runnerSha256': digest(ROOT / 'run.py'), 'collectorSha256': digest(ROOT / 'collect-dsh.mjs'),
        'timeoutSeconds': args.timeout, 'cases': selected, 'trials': trials,
        'readiness': {'status': 'ready', 'checked': ['required files', 'compiled imports'],
                      'limitations': ['Headless does not compose the Cordis preset or Web follow-up delivery']}}
    write_json(private / 'round.json', {'repo': str(args.repo), 'node': node, 'manifest': manifest})
    write_json(public / 'manifest.json', manifest)
    (public / 'cases.json').write_bytes(cases_bytes)
    (public / 'rubric.md').write_bytes(rubric_bytes)
    for trial in trials:
        case = next(c for c in selected if c['id'] == trial['caseId'])
        write_json(public / trial['id'] / 'trial.json', public_trial(manifest, trial, case))
    return manifest, private, public


def terminate_group(process):
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait()


def file_hashes(workspace):
    return {str(p.relative_to(workspace)): digest(p) for p in workspace.rglob('*')
            if p.is_file() and not p.is_symlink()}


def execute(args, manifest, private, public, node):
    if git(args.repo, 'rev-parse', 'HEAD') != manifest['sourceHead'] or git(args.repo, 'status', '--porcelain'):
        raise ValueError('Product revision or working tree changed after planning; create a new round')
    if not unchanged(args.repo, manifest['runtimeHashes']):
        raise ValueError('Runtime files changed after planning; use a new round after rebuilding')
    # Node parses an explicitly supplied env-file. No shell config or credential discovery.
    env_args = ['--env-file=' + str(args.env_file)] if args.env_file else []
    process_env = dict(os.environ)
    if args.env_file:
        # An explicitly selected file owns provider credentials; proxy settings remain caller-owned.
        for key in ('DEEPSEEK_API_KEY', 'DEEPSEEK_BASE_URL'):
            process_env.pop(key, None)
    credential = subprocess.check_output([node, *env_args, '-p',
        'Boolean(process.env.DEEPSEEK_API_KEY)'], text=True, env=process_env).strip()
    if credential != 'true':
        raise ValueError('DEEPSEEK_API_KEY is absent; provide the environment or an explicit --env-file')
    for planned in manifest['trials']:
        if planned['status'] != 'planned':
            continue
        case = next(c for c in manifest['cases'] if c['id'] == planned['caseId'])
        slot = private / 'trials' / planned['id']
        if slot.exists():
            raise ValueError('An incomplete private trial already exists; preserve it and create a new round to retry')
        slot.mkdir(parents=True)
        trial_file = public / planned['id'] / 'trial.json'
        if case.get('preset') not in (None, 'headless', 'standard'):
            result = {'status': 'blocked', 'reason': 'This case requires the actual Cordis preset; headless does not compose it',
                      'exitCode': None, 'elapsedSeconds': 0}
            write_json(slot / 'execution.json', result)
            trial = public_trial(manifest, planned, case)
            trial.update(status='blocked', error=result['reason'])
            write_json(trial_file, trial)
            planned['status'] = 'blocked'
            write_json(public / 'manifest.json', manifest)
            continue
        if not unchanged(args.repo, manifest['runtimeHashes']):
            raise ValueError('Runtime changed during the cohort; remaining trials were not started')
        workspace = slot / 'workspace'
        workspace.mkdir()
        for name, content in case.get('files', {}).items():
            target = workspace / name
            if not target.resolve().is_relative_to(workspace.resolve()):
                raise ValueError('Fixture path escapes the isolated workspace')
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
        before = file_hashes(workspace)
        patch = [
            {'id': 'agent-default-model', 'config': {'provider': 'deepseek-official', 'model': 'deepseek-flash'}},
            {'id': 'llm-deepseek', 'config': {'reasoningEffort': 'high', 'thinking': 'enabled'}},
            {'id': 'skill-filesystem', 'config': {'includeDefaultRoots': False, 'customSkillDirs': []}},
            {'id': 'session-persistence-jsonl', 'config': {'root': str(slot / 'home/sessions'), 'compression': 'none'}}]
        if manifest['visualizerAvailable']:
            patch.append({'insert': [{'id': 'tool-visualizer', 'name': '@deepseek-ai/dsh-tool-visualizer'},
                                     {'id': 'tool-visualizer-model', 'name': '@deepseek-ai/dsh-tool-visualizer/model'}]})
        write_json(slot / 'patch.yml', patch)
        env = dict(process_env)
        env.update(DSH_HOME=str(slot / 'home'), DSH_AGENTS_HOME=str(slot / 'agents'))
        for key in ['DSH_TOOLS_MODE', 'DSH_PROFILE']:
            env.pop(key, None)
        planned['status'] = 'running'
        write_json(public / 'manifest.json', manifest)
        trial = public_trial(manifest, planned, case)
        write_json(trial_file, trial)
        started = time.monotonic()
        status, code = 'error', None
        with (slot / 'events.jsonl').open('xb') as stdout, (slot / 'stderr.txt').open('xb') as stderr:
            process = None
            try:
                process = subprocess.Popen([node, *env_args, str(args.repo / 'apps/cli/lib/bin.js'),
                    '--profile', 'headless', '--patch', str(slot / 'patch.yml'), '--json', '-'],
                    cwd=workspace, env=env, stdin=subprocess.PIPE, stdout=stdout, stderr=stderr,
                    start_new_session=True)
                process.communicate(case['prompt'].encode(), timeout=manifest['timeoutSeconds'])
                status = 'completed' if process.returncode == 0 else 'error'
            except subprocess.TimeoutExpired:
                status = 'timeout'
            except KeyboardInterrupt:
                status = 'interrupted'
            except OSError:
                status = 'error'
            finally:
                if process:
                    terminate_group(process)
                    code = process.returncode
        result = {'status': status, 'exitCode': code,
                  'elapsedSeconds': round(time.monotonic() - started, 3),
                  'initialFiles': before, 'finalFiles': file_hashes(workspace)}
        write_json(slot / 'execution.json', result)
        planned['status'] = status
        write_json(public / 'manifest.json', manifest)
        trial.update(status=status, elapsedSeconds=result['elapsedSeconds'])
        write_json(trial_file, trial)
        print(json.dumps({'trial': planned['id'], 'status': status, 'elapsedSeconds': result['elapsedSeconds']}), flush=True)
        # Collect each attempt, including failures, before proceeding.
        collected = subprocess.run([node, *env_args, str(ROOT / 'collect-dsh.mjs'), '--round', args.round,
                                    '--private-root', str(args.private_root)], capture_output=True, text=True, env=process_env)
        if collected.returncode:
            (slot / 'collector-error.txt').write_text(collected.stderr)
            raise ValueError('Collection failed; diagnostic retained privately, raw attempt preserved')
        # Collection can detect a missing/incomplete Session even after exit code zero.
        status = json.loads(trial_file.read_text())['status']
        planned['status'] = status
        write_json(public / 'manifest.json', manifest)
        if status in ('error', 'timeout', 'interrupted'):
            return 1
    return 1 if any(t['status'] in ('error', 'timeout', 'interrupted', 'blocked') for t in manifest['trials']) else 0


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', action='store_true', help='Freeze inputs without calling the model')
    parser.add_argument('--resume', action='store_true', help='Run only unstarted slots in an existing round')
    parser.add_argument('--round', required=True)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--arm', required=True)
    parser.add_argument('--comparison-id')
    parser.add_argument('--split', choices=['dev', 'test', 'all'], default='dev')
    parser.add_argument('--case', nargs='+')
    parser.add_argument('--repeats', type=int, default=1)
    parser.add_argument('--limit', type=int)
    parser.add_argument('--timeout', type=float, default=360)
    parser.add_argument('--private-root', type=Path, default=DEFAULT_PRIVATE)
    parser.add_argument('--env-file', type=Path)
    args = parser.parse_args()
    try:
        if not all(SAFE_ID.fullmatch(x) for x in [args.round, args.arm]):
            raise ValueError('Round and arm must use letters, digits, dots, underscores or hyphens')
        if args.repeats < 1 or args.limit is not None and args.limit < 1 or not 0 < args.timeout <= 600:
            raise ValueError('Use positive repeats/limit and a timeout no greater than 600 seconds')
        args.repo = args.repo.resolve()
        args.private_root = args.private_root.resolve()
        if args.private_root.is_relative_to(ROOT):
            raise ValueError('Private raw logs must be outside the served benchmark directory')
        if args.env_file:
            args.env_file = args.env_file.resolve(strict=True)
        node = node_binary()
        if args.resume:
            private, public = args.private_root / args.round, ROOT / 'results' / args.round
            config = json.loads((private / 'round.json').read_text())
            manifest = json.loads((public / 'manifest.json').read_text())
            if args.arm != manifest['arm'] or str(args.repo) != config['repo']:
                raise ValueError('Resume must use the original arm and product checkout')
            if manifest['casesSha256'] != digest(private / 'inputs/cases.json'):
                raise ValueError('Frozen cases changed')
            for field in ('id', 'arm', 'model', 'reasoningEffort', 'sourceHead', 'runtimeHashes',
                          'casesSha256', 'rubricSha256', 'cases', 'timeoutSeconds', 'runnerSha256', 'collectorSha256'):
                if manifest.get(field) != config['manifest'].get(field):
                    raise ValueError('Public round differs from its private frozen inputs: ' + field)
            planned = lambda items: [{k: v for k, v in item.items() if k != 'status'} for item in items]
            if planned(manifest['trials']) != planned(config['manifest']['trials']):
                raise ValueError('Planned trial identities changed after freezing')
            if manifest['runnerSha256'] != digest(ROOT / 'run.py') or manifest['collectorSha256'] != digest(ROOT / 'collect-dsh.mjs'):
                raise ValueError('Runner or collector changed after freezing; create a new round instead of rewriting this one')
            if any(manifest['rubricSha256'] != digest(p) for p in (ROOT / 'rubric.md', private / 'inputs/rubric.md', public / 'rubric.md')):
                raise ValueError('Rubric changed after freezing; create a new round with the new scoring rules')
        else:
            manifest, private, public = freeze(args, node)
        print(json.dumps({'round': args.round, 'planned': len(manifest['trials']),
                          'mode': 'plan' if args.plan else 'run', 'manifest': f'results/{args.round}/manifest.json'}), flush=True)
        if not args.plan:
            if args.resume:
                collected = subprocess.run([node, str(ROOT / 'collect-dsh.mjs'), '--round', args.round,
                                            '--private-root', str(args.private_root)], capture_output=True, text=True)
                if collected.returncode:
                    (private / 'collector-error.txt').write_text(collected.stderr)
                    raise ValueError('Could not reconcile preserved attempts before resume; diagnostic retained privately')
                manifest = json.loads((public / 'manifest.json').read_text())
            return execute(args, manifest, private, public, node)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        # Error messages produced here contain paths/field names, never credential values.
        print('Evaluation stopped: ' + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
