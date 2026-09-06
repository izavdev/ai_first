"""Run a named, repository-reviewed acceptance check locally or in optional CI.

No tracker or PR text is executed. --contract only hashes a snapshot for evidence;
it does not approve that snapshot. The runner is not a sandbox or a coverage proof.
Run from the repo root. Review changes to this runner, registry, and tests together.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess


CHECK_ID = re.compile(r'[a-z][a-z0-9-]{0,63}')


def digest(data):
    return 'sha256:' + hashlib.sha256(data).hexdigest()


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'Duplicate JSON key: {key}')
        result[key] = value
    return result


def load_check(raw, check_id):
    registry = json.loads(raw, object_pairs_hook=strict_object)
    if not isinstance(registry, dict) or set(registry) != {'schema', 'checks'}:
        raise ValueError('Expected a registry with schema and checks; migrate old argv configs')
    if registry['schema'] != 'ai-first-verification/v1':
        raise ValueError('Unsupported verification registry schema')
    checks = registry['checks']
    if not isinstance(checks, dict) or any(not CHECK_ID.fullmatch(key) for key in checks):
        raise ValueError('Invalid check IDs')
    if not CHECK_ID.fullmatch(check_id) or check_id not in checks:
        raise ValueError(f'Unknown verification check: {check_id}')
    check = checks[check_id]
    if not isinstance(check, dict) or set(check) != {'argv', 'timeout_seconds', 'covers', 'negative_case'}:
        raise ValueError('Each check needs argv, timeout_seconds, covers, and negative_case')
    argv = check['argv']
    if not isinstance(argv, list) or not argv or any(
            not isinstance(arg, str) or not arg.strip() or '\x00' in arg for arg in argv):
        raise ValueError('Configure argv with a real acceptance command before use')
    timeout = check['timeout_seconds']
    if type(timeout) is not int or not 1 <= timeout <= 1500:
        raise ValueError('timeout_seconds must be an integer from 1 to 1500')
    for field in ('covers', 'negative_case'):
        if not isinstance(check[field], str) or not check[field].strip():
            raise ValueError(f'Document {field} before using the check')
    return check


def git(*args):
    return subprocess.run(['git', *args], check=True, capture_output=True).stdout


def worktree_digest():
    # Include tracked diffs and non-ignored untracked files; ignored files/runtime
    # dependencies are outside this evidence boundary and must be reviewed separately.
    state = hashlib.sha256(git('diff', '--binary', 'HEAD', '--'))
    for name in sorted(git('ls-files', '--others', '--exclude-standard', '-z').split(b'\x00')):
        if name:
            path = Path(name.decode('utf-8'))
            value = path.readlink().as_posix().encode() if path.is_symlink() else path.read_bytes()
            for part in (name, value):
                state.update(len(part).to_bytes(8, 'big'))
                state.update(part)
    return 'sha256:' + state.hexdigest()


def run(config_path, check_id='acceptance', contract_path=None):
    try:
        if git('rev-parse', '--show-prefix').strip():
            raise ValueError('Run from the repository root')
        raw = Path(config_path).read_bytes()
        check = load_check(raw, check_id)
        commit = git('rev-parse', 'HEAD').decode().strip()
        before = worktree_digest()
        evidence = dict(schema='ai-first-verification-result/v1', check=check_id,
                        commit=commit, registry_digest=digest(raw),
                        runner_digest=digest(Path(__file__).read_bytes()),
                        contract_digest=None if contract_path is None else digest(Path(contract_path).read_bytes()),
                        dirty=bool(git('status', '--porcelain', '--untracked-files=all').strip()),
                        worktree_digest=before)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f'AI-first verification configuration error: {error}', flush=True)
        return 2
    print(f'AI-first verification: check={check_id} commit={commit}', flush=True)
    command_exit = None
    outcome, code = 'error', 2
    try:
        result = subprocess.run(check['argv'], timeout=check['timeout_seconds'], check=False, shell=False)
        command_exit = result.returncode
        outcome, code = ('pass', 0) if command_exit == 0 else ('fail', 1)
    except subprocess.TimeoutExpired:
        outcome, code = 'timeout', 124
    except OSError as error:
        print(f'AI-first verification could not start: {error}', flush=True)
    try:
        changed = (git('rev-parse', 'HEAD').decode().strip() != commit
                   or worktree_digest() != before
                   or digest(Path(config_path).read_bytes()) != evidence['registry_digest']
                   or digest(Path(__file__).read_bytes()) != evidence['runner_digest']
                   or (contract_path is not None and digest(Path(contract_path).read_bytes()) != evidence['contract_digest']))
        if changed:
            outcome, code = 'inputs-changed', 2
    except (OSError, ValueError, subprocess.SubprocessError):
        outcome, code = 'inputs-unverifiable', 2
    evidence.update(outcome=outcome, command_exit=command_exit)
    print('AI_FIRST_RESULT ' + json.dumps(evidence, sort_keys=True), flush=True)
    return code


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default='.ai-first/ci/verification.json')
    parser.add_argument('--check', default='acceptance')
    parser.add_argument('--contract', help='Optional exact saved task-contract snapshot; hashed, never executed')
    args = parser.parse_args()
    raise SystemExit(run(args.config, args.check, args.contract))
