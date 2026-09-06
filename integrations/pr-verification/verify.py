"""Run one repository-reviewed acceptance command locally or in optional CI.

No tracker or PR text is fetched or executed. This is a command runner, not a
sandbox, approval validator, or proof of test coverage. Run from the repo root.
"""
import argparse
import json
from pathlib import Path
import subprocess


def run(config_path):
    try:
        config = json.loads(Path(config_path).read_text(encoding='utf-8'))
        if not isinstance(config, dict) or set(config) != {'argv', 'timeout_seconds'}:
            raise ValueError('Expected exactly argv and timeout_seconds')
        argv = config['argv']
        timeout = config['timeout_seconds']
        if not isinstance(argv, list) or not argv or any(
                not isinstance(arg, str) or not arg.strip() for arg in argv):
            raise ValueError('Configure argv with a real acceptance command before use')
        if type(timeout) is not int or not 1 <= timeout <= 1500:
            raise ValueError('timeout_seconds must be an integer from 1 to 1500')
        commit = subprocess.run(['git', 'rev-parse', 'HEAD'], check=True,
                                capture_output=True, text=True).stdout.strip()
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f'AI-first verification configuration error: {error}', flush=True)
        return 2
    print(f'AI-first verification: commit={commit} config={config_path}', flush=True)
    try:
        result = subprocess.run(argv, timeout=timeout, check=False, shell=False)
    except subprocess.TimeoutExpired:
        print('AI-first verification: TIMEOUT', flush=True)
        return 124
    except OSError as error:
        print(f'AI-first verification could not start: {error}', flush=True)
        return 2
    print(f'AI-first verification: {"PASS" if result.returncode == 0 else "FAIL"} '
          f'command_exit={result.returncode} commit={commit}', flush=True)
    return 0 if result.returncode == 0 else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default='.ai-first/ci/verification.json')
    raise SystemExit(run(parser.parse_args().config))
