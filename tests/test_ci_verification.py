import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / 'integrations/pr-verification/verify.py'


class VerificationRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        (self.repo / 'fixture.txt').write_text('approved\n')
        (self.repo / 'validate.py').write_text(
            'from pathlib import Path\n'
            'raise SystemExit(0 if Path("fixture.txt").read_text() == "approved\\n" else 7)\n')
        self.git('init', '-q')
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

    def run_config(self, config=None, *args):
        path = self.root / 'verification.json'
        path.write_text(json.dumps(self.config() if config is None else config))
        return subprocess.run([sys.executable, str(RUNNER), '--config', str(path), *args],
                              cwd=self.repo, text=True, capture_output=True)

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

    def test_timeout_is_failure(self):
        result = self.run_config(self.config(argv=[sys.executable, '-c', 'import time; time.sleep(5)'],
                                             timeout_seconds=1))
        self.assertEqual(result.returncode, 124)
        self.assertEqual(self.evidence(result)['outcome'], 'timeout')

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
