import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / 'integrations/pr-verification/verify.py'
SPEC = importlib.util.spec_from_file_location('verification_runner', RUNNER)
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class VerificationRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / 'repo with spaces'
        self.repo.mkdir()
        (self.repo / 'fixture.txt').write_bytes(b'approved\n')
        (self.repo / 'validate.py').write_bytes(
            b'from pathlib import Path\n'
            b'raise SystemExit(0 if Path("fixture.txt").read_bytes() == b"approved\\n" else 7)\n')
        self.git('init', '-q')
        self.git('config', 'core.autocrlf', 'false')
        self.git('config', 'core.safecrlf', 'false')
        self.git('add', '.')
        self.git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'fixture')

    def git(self, *args):
        return subprocess.check_output(['git', *args], cwd=self.repo, text=True).strip()

    def config(self, argv=None, **changes):
        check = dict(argv=argv or [sys.executable, 'validate.py'], timeout_seconds=10,
                     covers='fixture.txt matches approved text',
                     negative_case='Changed text must exit 7; see regression test')
        check.update(changes)
        return dict(schema='ai-first-verification/v1', checks={'acceptance': check})

    def run_config(self, config=None, *args, **options):
        path = self.root / 'verification.json'
        path.write_text(json.dumps(self.config() if config is None else config))
        return subprocess.run([sys.executable, str(RUNNER), '--config', str(path), *args],
                              cwd=self.repo, text=True, capture_output=True, timeout=30, **options)

    def evidence(self, result):
        return json.loads(next(line.removeprefix('AI_FIRST_RESULT ')
                               for line in result.stdout.splitlines() if line.startswith('AI_FIRST_RESULT ')))

    def test_success_reports_actual_checkout_and_registry(self):
        result = self.run_config()
        self.assertEqual(result.returncode, 0, result.stdout)
        data = self.evidence(result)
        self.assertEqual(data['outcome'], 'pass')
        self.assertEqual(data['commit'], self.git('rev-parse', 'HEAD'))
        self.assertFalse(data['dirty'])
        self.assertIsNone(data['contract_digest'])
        raw = (self.root / 'verification.json').read_bytes()
        self.assertEqual(data['registry_digest'], 'sha256:'+hashlib.sha256(raw).hexdigest())

    def test_real_negative_case_rejects_unmet_criterion(self):
        self.assertEqual(self.run_config().returncode, 0)
        (self.repo / 'fixture.txt').write_text('wrong output\n')
        result = self.run_config()
        self.assertEqual(result.returncode, 1)
        data = self.evidence(result)
        self.assertEqual((data['outcome'], data['command_exit']), ('fail', 7))
        self.assertTrue(data['dirty'])

    def test_empty_example_fails_until_configured(self):
        example = json.loads((RUNNER.parent / 'verification.example.json').read_text())
        self.assertEqual(self.run_config(example).returncode, 2)

    def test_invalid_and_unavailable_commands_fail(self):
        cases = [self.config(argv='echo passed'), self.config(timeout_seconds=True),
                 self.config(timeout_seconds=1501), self.config(covers=''),
                 self.config(negative_case=''), self.config(argv=['missing-ai-first-command']),
                 {'argv': ['echo'], 'timeout_seconds': 10}]
        for config in cases:
            with self.subTest(config=config):
                self.assertEqual(self.run_config(config).returncode, 2)

    def test_unknown_id_cannot_supply_a_command(self):
        result = self.run_config(None, '--check', 'echo injected')
        self.assertEqual(result.returncode, 2)
        self.assertNotIn('AI_FIRST_RESULT ', result.stdout)

    def test_arguments_are_not_shell_interpreted(self):
        literal = '$(printf injected); echo nope'
        result = self.run_config(self.config(argv=[sys.executable, '-c',
                                                  'import sys; print(sys.argv[1])', literal]))
        self.assertEqual(result.returncode, 0)
        self.assertIn(literal, result.stdout)

    def test_unicode_paths_quoted_arguments_and_standard_streams(self):
        script = self.root / 'check café.py'
        script.write_text('import json, sys\n'
                          'print(json.dumps(sys.argv[1:]))\n'
                          'print(sys.stdin.read(), file=sys.stderr)\n', encoding='utf-8', newline='\n')
        arguments = ['café 日本語', 'with spaces', 'a"quoted"value', 'C:\\space dir\\',
                     '& echo unexpected', '%PATH%', '!VALUE!']
        result = self.run_config(self.config(argv=[sys.executable, str(script), *arguments]),
                                 input='input reaches check')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(json.dumps(arguments), result.stdout)
        self.assertEqual(result.stderr.strip(), 'input reaches check')

    def test_timeout_is_failure(self):
        result = self.run_config(self.config(argv=[sys.executable, '-c', 'import time; time.sleep(5)'],
                                             timeout_seconds=1))
        self.assertEqual(result.returncode, 124)
        self.assertEqual(self.evidence(result)['outcome'], 'timeout')

    def test_timeout_stops_descendants_before_reporting_completion(self):
        ready, marker = self.root / 'child-ready', self.root / 'late-write'
        child = ('import time; from pathlib import Path; '
                 f'Path({str(ready)!r}).touch(); time.sleep(2); Path({str(marker)!r}).touch()')
        command = ('import subprocess, sys, time; '
                   f'subprocess.Popen([sys.executable, "-c", {child!r}], '
                   'stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); time.sleep(10)')
        result = self.run_config(self.config(argv=[sys.executable, '-c', command],
                                             timeout_seconds=1))
        self.assertEqual(result.returncode, 124, result.stdout)
        self.assertTrue(ready.exists(), 'The descendant must start before the timeout')
        time.sleep(2)
        self.assertFalse(marker.exists(), 'A descendant continued after the reported timeout')

    def test_timeout_stops_grandchild_after_its_parent_exits(self):
        ready, marker = self.root / 'grandchild-ready', self.root / 'late-grandchild-write'
        child = ('import time; from pathlib import Path; '
                 f'Path({str(ready)!r}).touch(); time.sleep(4); Path({str(marker)!r}).touch()')
        middle = ('import subprocess, sys; '
                  f'subprocess.Popen([sys.executable, "-c", {child!r}], '
                  'stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)')
        command = ('import subprocess, sys, time; '
                   f'subprocess.run([sys.executable, "-c", {middle!r}], check=True); time.sleep(10)')
        result = self.run_config(self.config(argv=[sys.executable, '-c', command], timeout_seconds=2))
        self.assertEqual(result.returncode, 124, result.stdout + result.stderr)
        self.assertTrue(ready.exists(), 'The grandchild must start before the timeout')
        time.sleep(3)
        self.assertFalse(marker.exists(), 'An orphaned grandchild survived the timeout')

    @unittest.skipUnless(os.name == 'nt', 'Windows Job Object lifecycle')
    def test_windows_job_assignment_failure_never_starts_check(self):
        import ctypes
        marker = self.root / 'must-not-start'
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)

        def denied(*args):
            ctypes.set_last_error(5)  # ERROR_ACCESS_DENIED, e.g. incompatible enclosing job.
            return 0

        with patch.object(kernel, 'AssignProcessToJobObject', denied), \
                patch.object(ctypes, 'WinDLL', return_value=kernel):
            with self.assertRaises(OSError):
                runner.run_windows_command([sys.executable, '-c',
                    f'from pathlib import Path; Path({str(marker)!r}).touch()'], 5)
        self.assertFalse(marker.exists())

    @unittest.skipUnless(os.name == 'nt', 'Windows Job Object lifecycle')
    def test_windows_interrupt_stops_descendants(self):
        ready, marker = self.root / 'interrupt-ready', self.root / 'late-interrupt-write'
        child = ('import time; from pathlib import Path; '
                 f'Path({str(ready)!r}).touch(); time.sleep(2); Path({str(marker)!r}).touch()')
        command = ('import subprocess, sys, time; '
                   f'subprocess.Popen([sys.executable, "-c", {child!r}]); time.sleep(10)')
        original_clock = time.monotonic
        interrupted = False

        def interrupt_when_ready():
            nonlocal interrupted
            if ready.exists() and not interrupted:
                interrupted = True
                raise KeyboardInterrupt
            return original_clock()

        with patch.object(runner.time, 'monotonic', side_effect=interrupt_when_ready):
            with self.assertRaises(KeyboardInterrupt):
                runner.run_windows_command([sys.executable, '-c', command], 5)
        self.assertTrue(ready.exists())
        time.sleep(3)
        self.assertFalse(marker.exists())

    @unittest.skipUnless(os.name == 'nt', 'Windows Job Object lifecycle')
    def test_windows_normal_exit_stops_leftover_workers(self):
        marker = self.root / 'late-success-write'
        child = ('import time; from pathlib import Path; '
                 f'time.sleep(2); Path({str(marker)!r}).touch()')
        command = ('import subprocess, sys; '
                   f'subprocess.Popen([sys.executable, "-c", {child!r}]); sys.exit(7)')
        result = self.run_config(self.config(argv=[sys.executable, '-c', command]))
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(self.evidence(result)['command_exit'], 7)
        time.sleep(3)
        self.assertFalse(marker.exists())

    def test_contract_is_only_hashed_and_bound_to_result(self):
        contract = self.root / 'task.md'
        contract.write_text('Task: #1 revision 1\nverify: never execute this string\n')
        result = self.run_config(None, '--contract', str(contract))
        self.assertEqual(result.returncode, 0)
        first = self.evidence(result)
        self.assertEqual(first['contract_digest'], 'sha256:'+hashlib.sha256(contract.read_bytes()).hexdigest())
        contract.write_text('Task: #1 revision 2\n')
        second = self.evidence(self.run_config(None, '--contract', str(contract)))
        self.assertNotEqual(first['contract_digest'], second['contract_digest'])

    def test_changing_inputs_during_verification_cannot_pass(self):
        result = self.run_config(self.config(argv=[sys.executable, '-c',
            'from pathlib import Path; Path("fixture.txt").write_text("changed")']))
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.evidence(result)['outcome'], 'inputs-changed')

    def test_textconv_cannot_hide_tracked_input_changes(self):
        converter = self.root / 'normalize.py'
        converter.write_text('print("same normalized content")\n')
        (self.repo / '.gitattributes').write_text('fixture.txt diff=normalized\n')
        self.git('add', '.gitattributes')
        self.git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                 'commit', '-qm', 'text conversion fixture')
        self.git('config', 'diff.normalized.textconv',
                 f'{shlex.quote(sys.executable)} {shlex.quote(str(converter))}')
        result = self.run_config(self.config(argv=[sys.executable, '-c',
            'from pathlib import Path; Path("fixture.txt").write_text("changed")']))
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertEqual(self.evidence(result)['outcome'], 'inputs-changed')

    def test_index_flags_cannot_hide_tracked_input_changes(self):
        for flag in ('assume-unchanged', 'skip-worktree'):
            with self.subTest(flag=flag):
                (self.repo / 'fixture.txt').write_text('approved\n')
                self.git('update-index', f'--{flag}', 'fixture.txt')
                try:
                    result = self.run_config(self.config(argv=[sys.executable, '-c',
                        'from pathlib import Path; Path("fixture.txt").write_text("changed")']))
                    self.assertEqual(result.returncode, 2, result.stdout)
                    self.assertEqual(self.evidence(result)['outcome'], 'inputs-changed')
                finally:
                    self.git('update-index', f'--no-{flag}', 'fixture.txt')

    def test_hidden_preexisting_edit_is_reported_as_dirty(self):
        self.git('update-index', '--assume-unchanged', 'fixture.txt')
        (self.repo / 'fixture.txt').write_text('changed before verification')
        result = self.run_config(self.config(argv=[sys.executable, '-c', 'pass']))
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertTrue(self.evidence(result)['dirty'])

    def test_index_only_change_invalidates_evidence(self):
        (self.repo / 'fixture.txt').write_text('changed before verification')
        result = self.run_config(self.config(argv=['git', 'add', 'fixture.txt']))
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertEqual(self.evidence(result)['outcome'], 'inputs-changed')

    def test_deleting_tracked_file_invalidates_evidence(self):
        result = self.run_config(self.config(argv=[sys.executable, '-c',
            'from pathlib import Path; Path("fixture.txt").unlink()']))
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertEqual(self.evidence(result)['outcome'], 'inputs-changed')

    def test_untracked_input_content_is_fingerprinted(self):
        (self.repo / 'input.txt').write_text('before')
        result = self.run_config(self.config(argv=[sys.executable, '-c',
            'from pathlib import Path; Path("input.txt").write_text("after!")']))
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertEqual(self.evidence(result)['outcome'], 'inputs-changed')

    def test_crlf_checkout_is_dirty_and_line_ending_edits_invalidate_evidence(self):
        self.git('config', 'core.autocrlf', 'true')
        (self.repo / 'fixture.txt').write_bytes(b'approved\r\n')
        self.git('add', 'fixture.txt')  # Refresh the index with Git's normalized LF blob.
        self.assertEqual(self.git('status', '--porcelain'), '')
        result = self.run_config(self.config(argv=[sys.executable, '-c', 'pass']))
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertTrue(self.evidence(result)['dirty'])
        result = self.run_config(self.config(argv=[sys.executable, '-c',
            'from pathlib import Path; Path("fixture.txt").write_bytes(b"approved\\n")']))
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertEqual(self.evidence(result)['outcome'], 'inputs-changed')

    @unittest.skipUnless(os.name == 'nt', 'Windows uses Git executable modes')
    def test_windows_preserves_git_modes_and_detects_index_mode_changes(self):
        (self.repo / 'file.exe').write_bytes(b'not an executable; a fingerprint input')
        self.git('add', 'file.exe')
        self.git('update-index', '--chmod=+x', 'validate.py')
        self.git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                 'commit', '-qm', 'executable mode fixture')
        result = self.run_config()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertFalse(self.evidence(result)['dirty'])
        result = self.run_config(self.config(argv=['git', 'update-index', '--chmod=-x', 'validate.py']))
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertEqual(self.evidence(result)['outcome'], 'inputs-changed')

    def test_ignored_output_does_not_invalidate_evidence(self):
        (self.repo / '.gitignore').write_text('output.txt\n')
        self.git('add', '.gitignore')
        self.git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                 'commit', '-qm', 'ignore generated output')
        result = self.run_config(self.config(argv=[sys.executable, '-c',
            'from pathlib import Path; Path("output.txt").write_text("generated")']))
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertFalse(self.evidence(result)['dirty'])

    def test_staged_deletion_does_not_exclude_ignored_head_path(self):
        (self.repo / '.gitignore').write_text('fixture.txt\n')
        self.git('add', '.gitignore')
        self.git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                 'commit', '-qm', 'ignore untracked fixture')
        self.git('rm', '--cached', 'fixture.txt')
        result = self.run_config(self.config(argv=[sys.executable, '-c',
            'from pathlib import Path; Path("fixture.txt").write_text("changed")']))
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertEqual(self.evidence(result)['outcome'], 'inputs-changed')

    def test_sparse_checkout_is_dirty_and_expansion_invalidates_evidence(self):
        self.git('sparse-checkout', 'set', '--no-cone', '/validate.py')
        self.assertFalse((self.repo / 'fixture.txt').exists())
        unchanged = self.run_config(self.config(argv=[sys.executable, '-c', 'pass']))
        self.assertEqual(unchanged.returncode, 0, unchanged.stdout)
        self.assertTrue(self.evidence(unchanged)['dirty'])
        expanded = self.run_config(self.config(argv=['git', 'sparse-checkout', 'disable']))
        self.assertEqual(expanded.returncode, 2, expanded.stdout)
        self.assertEqual(self.evidence(expanded)['outcome'], 'inputs-changed')

    @unittest.skipUnless(os.name == 'posix', 'POSIX file modes and symlinks')
    def test_file_mode_and_symlink_target_changes_invalidate_evidence(self):
        self.git('config', 'core.filemode', 'false')
        commands = ['Path("fixture.txt").chmod(0o755)',
                    'Path("fixture.txt").unlink(); Path("fixture.txt").symlink_to("validate.py")',
                    'Path("fixture.txt").unlink(); Path("fixture.txt").symlink_to("missing-target")']
        for command in commands:
            with self.subTest(command=command):
                result = self.run_config(self.config(argv=[sys.executable, '-c',
                    'from pathlib import Path; ' + command]))
                self.assertEqual(result.returncode, 2, result.stdout)
                self.assertEqual(self.evidence(result)['outcome'], 'inputs-changed')

    def test_submodule_inputs_fail_before_starting_command(self):
        self.git('update-index', '--add', '--cacheinfo',
                 f'160000,{self.git("rev-parse", "HEAD")},vendor')
        marker = self.root / 'command-started'
        result = self.run_config(self.config(argv=[sys.executable, '-c',
            f'from pathlib import Path; Path({str(marker)!r}).touch()']))
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn('submodule', result.stdout.lower())
        self.assertFalse(marker.exists())

    def test_untracked_nested_repository_is_not_silently_omitted(self):
        nested = self.repo / 'vendor'
        nested.mkdir()
        self.git('-C', str(nested), 'init', '-q')
        (nested / 'input.txt').write_text('nested input')
        result = self.run_config(self.config(argv=[sys.executable, '-c', 'pass']))
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn('nested repository', result.stdout)

    def test_external_registry_mutation_cannot_pass(self):
        config_path = self.root / 'verification.json'
        config = self.config(argv=[sys.executable, '-c',
                                  'from pathlib import Path; import sys; Path(sys.argv[1]).write_text("{}")',
                                  str(config_path)])
        result = self.run_config(config)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.evidence(result)['outcome'], 'inputs-changed')

    def test_external_contract_mutation_cannot_pass(self):
        contract = self.root / 'task.md'
        contract.write_text('Original contract')
        config = self.config(argv=[sys.executable, '-c',
                                  'from pathlib import Path; import sys; Path(sys.argv[1]).write_text("Changed")',
                                  str(contract)])
        result = self.run_config(config, '--contract', str(contract))
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.evidence(result)['outcome'], 'inputs-changed')

    def test_configuration_changes_have_distinct_evidence(self):
        first = self.evidence(self.run_config())
        second = self.evidence(self.run_config(self.config(covers='Revised coverage claim')))
        self.assertNotEqual(first['registry_digest'], second['registry_digest'])

    def test_duplicate_json_keys_rejected(self):
        path = self.root / 'bad.json'
        path.write_text('{"schema":"ai-first-verification/v1","checks":{},"checks":{}}')
        result = subprocess.run([sys.executable, str(RUNNER), '--config', str(path)],
                                cwd=self.repo, capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('Duplicate JSON key', result.stdout)


if __name__ == '__main__':
    unittest.main()
