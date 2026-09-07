"""Exercise only copied setup assets, without a source checkout on the import path."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'skills/setup-ai-first/assets'


class InstalledRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.installed = self.root / 'consumer' / '.ai-first'
        shutil.copytree(ASSETS, self.installed, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        shutil.copyfile(ASSETS / 'adapters/github.md', self.installed / 'tracker.md')
        (self.installed / 'README.md').write_text('tracker: github\n', encoding='utf-8')
        (self.installed / 'terminology.md').write_text('large: Epic\nregular: Issue\nsmall: Task\n', encoding='utf-8')
        self.env = dict(os.environ)
        self.env.pop('PYTHONPATH', None)
        self.env['PYTHONNOUSERSITE'] = '1'

    def cli(self, operation, value=None, *args, expected=0):
        command = [sys.executable, str(self.installed / 'policy.py'), operation]
        if value is not None:
            source = self.root / 'input.json'
            source.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
            command.append(str(source))
        result = subprocess.run(command + list(args), cwd=self.root, env=self.env,
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def receipt(self):
        return self.cli('record-installation', None, '--root', str(self.installed),
                        '--source-manifest', str(ASSETS / 'asset-manifest.json'), '--tracker', 'github')

    def brief(self):
        return dict(item='github:org/repo#1', title='Export inventory', tracker='github',
                    body=(ROOT / 'tests/fixtures/schema/github-brief.md').read_text(encoding='utf-8'),
                    linked_content=None)

    def approved(self):
        snapshot = self.brief()
        bound = self.cli('snapshot', snapshot)
        snapshot['body'] = snapshot['body'].replace(bound['stored_digest'], bound['digest'])
        record = dict(body=f'[ai-first] APPROVED revision={bound["payload"]["revision"]} digest={bound["digest"]}',
                      author='independent-reviewer', human=True, edited=False)
        check = dict(snapshot_data=snapshot, records=[record], label_present=True,
                     requester_verified=True, history_complete=True, snapshot_stable=True)
        return snapshot, bound, check

    def test_copy_is_self_contained_and_runtime_is_the_tested_source(self):
        from src.ai_first import classification
        self.assertEqual(Path(classification.__file__).resolve(), ASSETS / 'ai_first/classification.py')
        self.assertEqual(self.cli('version')['package_version'], '0.5.0')
        self.assertEqual(self.cli('classify', dict(v=2, b=2, c=2, a=1,
                         hard_override=False, verification_valid=True))['tier'], 'delegate')
        self.receipt()
        self.assertTrue(self.cli('doctor')['compatible'])

    def test_invalid_json_and_bad_inputs_are_nonzero(self):
        self.cli('classify', dict(v=True, b=2, c=2, a=2), expected=2)
        source = self.root / 'duplicate.json'
        source.write_text('{"v":2,"v":0,"b":2,"c":2,"a":2}', encoding='utf-8')
        self.cli('classify', None, str(source), expected=2)
        source.write_text('{"v":NaN,"b":2,"c":2,"a":2}', encoding='utf-8')
        self.cli('classify', None, str(source), expected=2)

    def test_doctor_rejects_missing_mixed_and_modified_runtime(self):
        self.cli('doctor', expected=1)
        self.receipt()
        self.cli('doctor', None, '--require-policy', 'ai-first-policy/old', expected=1)
        path = self.installed / 'ai_first/classification.py'
        path.write_text(path.read_text(encoding='utf-8') + '\n# local edit\n', encoding='utf-8')
        result = self.cli('doctor', expected=1)
        self.assertTrue(any('classification.py' in error for error in result['errors']))

    def test_upgrade_preserves_customizations_and_diagnoses_legacy_receipt(self):
        schema = self.installed / 'ai-first-schema.md'
        schema.write_text(schema.read_text(encoding='utf-8').replace('solo-mode: false', 'solo-mode: "alice"'), encoding='utf-8')
        capabilities = self.installed / 'ai-first-capabilities.yml'
        capabilities.write_text(capabilities.read_text(encoding='utf-8') + '\n# Team-owned notes\n', encoding='utf-8')
        before = (schema.read_bytes(), capabilities.read_bytes())
        (self.installed / 'installation.json').write_text('{"schema":"ai-first-installation/v1"}', encoding='utf-8')
        self.cli('doctor', expected=1)
        self.receipt()
        self.assertEqual(before, (schema.read_bytes(), capabilities.read_bytes()))
        result = self.cli('doctor')
        self.assertIn('ai-first-schema.md', result['reviewed_customizations'])
        self.assertIn('ai-first-capabilities.yml', result['reviewed_customizations'])
        capabilities.write_text(capabilities.read_text(encoding='utf-8') + '# Later change\n', encoding='utf-8')
        self.assertIn('ai-first-capabilities.yml', self.cli('doctor')['unrecorded_changes'])
        schema.write_text(schema.read_text(encoding='utf-8').replace('ai-first-policy/v1', 'ai-first-policy/old'), encoding='utf-8')
        self.cli('doctor', expected=1)

    def test_failed_receipt_update_preserves_previous_receipt(self):
        self.receipt()
        previous = (self.installed / 'installation.json').read_bytes()
        (self.installed / 'workflow-contract.json').write_text('{}', encoding='utf-8')
        self.cli('record-installation', None, '--root', str(self.installed), '--source-manifest',
                 str(ASSETS / 'asset-manifest.json'), '--tracker', 'github', expected=2)
        self.assertEqual(previous, (self.installed / 'installation.json').read_bytes())

    def test_small_intake_creates_only_an_unclassified_item_and_stops(self):
        result = self.cli('intake', dict(needs_investigation=False, one_outcome=True,
                          one_surface=True, machine_checkable=True, no_decisions=True, large=False))
        self.assertEqual(result['create_role'], 'small')
        self.assertEqual(result['stop_after'], 'create-unclassified-item')
        self.assertEqual(result['next_mode'], 'single-item')
        self.assertNotIn('tier', result)
        self.assertEqual(self.cli('mode', dict(requested='single-item', kind=None))['mode'], 'single-item')
        result = self.cli('intake', dict(needs_investigation=True, one_outcome=True,
                          one_surface=True, machine_checkable=True, no_decisions=True, large=False))
        self.assertIsNone(result['create_role'])

    def test_approval_uses_full_snapshot_and_local_policy(self):
        snapshot, bound, check = self.approved()
        self.assertTrue(self.cli('check-brief', check)['valid'])
        check['records'][0]['author'] = bound['payload']['requester'].upper()
        self.cli('check-brief', check, expected=1)  # Case cannot manufacture an independent GitHub actor.
        schema = self.installed / 'ai-first-schema.md'
        schema.write_text(schema.read_text(encoding='utf-8').replace('solo-mode: false',
                         'solo-mode: ' + json.dumps(bound['payload']['requester'])), encoding='utf-8')
        self.assertTrue(self.cli('check-brief', check)['valid'])
        schema.write_text(schema.read_text(encoding='utf-8') + '\nsolo-mode:false\n', encoding='utf-8')
        result = self.cli('check-brief', check, expected=1)
        self.assertIsNotNone(result['policy_warning'])
        check['snapshot_data']['body'] += 'Changed acceptance after the block.'
        self.cli('check-brief', check, expected=2)

    def test_captured_github_flow_approval_edit_timeout_resume_and_verification(self):
        snapshot, bound, check = self.approved()
        raw_comment = dict(id=1, body=check['records'][0]['body'], user=dict(login='reviewer', type='User'),
                           created_at='2026-09-07T10:00:00Z', updated_at='2026-09-07T10:00:00Z')
        history = self.cli('history', dict(tracker='github', human_ids=['reviewer'],
                           pages=[dict(request_cursor=None, next_cursor=None, data=[raw_comment])]))
        check['records'] = history['records']
        self.assertTrue(self.cli('check-brief', check)['valid'])
        check['snapshot_data'] = dict(snapshot, title='Changed acceptance')
        self.cli('check-brief', check, expected=1)
        check['snapshot_data'] = snapshot
        self.assertTrue(self.cli('check-brief', check)['valid'])
        unit = '12345678-1234-4234-8234-123456789abc'
        self.assertIsNone(self.cli('select-plan', dict(plans=[]))['plan'])
        plan = dict(schema='ai-first-decomposition/v1', parent=snapshot['item'],
                    revision=bound['payload']['revision'], brief_digest=bound['digest'],
                    units=[dict(id=unit, title='Export', body='Reviewed contract', depends_on=[])])
        self.assertEqual(self.cli('select-plan', dict(plans=[plan, plan]))['plan'], plan)
        key = self.cli('unit-key', dict(parent=plan['parent'], revision=plan['revision'],
                       brief_digest=plan['brief_digest'], unit_id=unit))['key']
        request = dict(plan=plan, items=[], intents={}, inventory_complete=True)
        self.assertEqual(self.cli('reconcile', request)['actions'][0]['action'], 'create')
        request['intents'][key] = 'pending'  # Lost response: empty search cannot permit retry.
        self.cli('reconcile', request, expected=2)
        request['items'] = [dict(id='github:org/repo#2', parent=plan['parent'], revision=plan['revision'],
                                brief_digest=plan['brief_digest'], key=key, title='Export',
                                body='Human-edited contract', state='closed', linked=False)]
        for _ in range(2):
            self.assertEqual(self.cli('reconcile', request)['actions'][0]['action'], 'reuse')

        # Real local verification command and exact task snapshot; no live tracker claimed.
        repo = self.root / 'verification'
        repo.mkdir()
        task = repo / 'task.md'
        task.write_text('github:org/repo#2\nAcceptance: output is approved\n', encoding='utf-8')
        (repo / 'output.txt').write_text('approved', encoding='utf-8')
        (repo / 'check.py').write_text('from pathlib import Path\nraise SystemExit(0 if Path("output.txt").read_text() == "approved" else 7)\n', encoding='utf-8')
        registry = repo / 'verification.json'
        registry.write_text(json.dumps(dict(schema='ai-first-verification/v1', checks=dict(acceptance=dict(
            argv=[sys.executable, 'check.py'], timeout_seconds=5, covers='approved output',
            negative_case='wrong output exits 7')))), encoding='utf-8')
        for args in (['init', '-q'], ['config', 'core.autocrlf', 'false'], ['add', '.'],
                     ['-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'fixture']):
            subprocess.run(['git', *args], cwd=repo, check=True, capture_output=True)
        copied_runner = self.root / 'verify.py'
        shutil.copyfile(ROOT / 'integrations/pr-verification/verify.py', copied_runner)
        command = [sys.executable, str(copied_runner),
                   '--config', str(registry), '--contract', str(task)]
        for output, expected in (('approved', 0), ('wrong', 1)):
            (repo / 'output.txt').write_text(output, encoding='utf-8')
            result = subprocess.run(command, cwd=repo, capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
            evidence = json.loads(next(line.removeprefix('AI_FIRST_RESULT ') for line in result.stdout.splitlines()
                                       if line.startswith('AI_FIRST_RESULT ')))
            self.assertEqual(evidence['contract_digest'], 'sha256:' + hashlib.sha256(task.read_bytes()).hexdigest())


if __name__ == '__main__':
    unittest.main()
