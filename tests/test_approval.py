import copy
import hashlib
import importlib.util
from pathlib import Path
import unittest

PATH = Path(__file__).resolve().parents[1] / 'skills/setup-ai-first/assets/approval.py'
spec = importlib.util.spec_from_file_location('approval', PATH)
approval = importlib.util.module_from_spec(spec)
spec.loader.exec_module(approval)


class ApprovalTests(unittest.TestCase):
    def setUp(self):
        self.payload = dict(item='github:org/repo#1',
                            revision='12345678-1234-4234-8234-123456789abc',
                            requester='alice', title='Résumé', description='Brief\n',
                            brief_url='inline', linked_content=None,
                            groomed_on='2026-09-06', open_decisions=0)
        self.digest = approval.brief_digest(self.payload)
        self.records = [self.record()]

    def record(self, action='APPROVED', author='bob', **changes):
        result = dict(body=f'[ai-first] {action} revision={self.payload["revision"]} digest={self.digest}',
                      author=author, human=True, edited=False)
        result.update(changes)
        return result

    def valid(self, **changes):
        args = dict(payload=self.payload, stored_digest=self.digest, records=self.records,
                    label_present=True, requester_verified=True,
                    history_complete=True, snapshot_stable=True)
        args.update(changes)
        return approval.approval_valid(**args)

    def test_canonical_bytes_and_newlines(self):
        canonical = '["ai-first-brief/v1","github:org/repo#1","12345678-1234-4234-8234-123456789abc","alice","Résumé","Brief\\n","inline",null,"2026-09-06",0]'
        self.assertEqual(self.digest, 'sha256:' + hashlib.sha256(canonical.encode('utf-8')).hexdigest())
        self.payload['description'] = 'Brief\r\n'
        self.assertEqual(approval.brief_digest(self.payload), self.digest)
        self.payload['description'] = 'Brief \n'
        self.assertNotEqual(approval.brief_digest(self.payload), self.digest)

    def test_independent_and_solo_approval(self):
        self.assertTrue(self.valid())
        self.records = [self.record(author='alice')]
        self.assertFalse(self.valid())
        self.assertTrue(self.valid(solo_identity='alice'))
        self.assertFalse(self.valid(solo_identity='carol'))
        self.assertFalse(self.valid(solo_identity='alice', label_present=False))

    def test_every_bound_field_change_rejects_old_approval(self):
        changes = dict(item='github:org/repo#2', revision='12345678-1234-4234-8234-123456789abd',
                       requester='carol', title='New title', description='New brief',
                       groomed_on='2026-09-07', open_decisions=1)
        for key, value in changes.items():
            with self.subTest(key=key):
                payload = dict(self.payload, **{key: value})
                self.assertFalse(self.valid(payload=payload))
                # Updating the stored digest does not update the human's approval.
                self.assertFalse(self.valid(payload=payload, stored_digest=approval.brief_digest(payload)))

    def test_mutable_linked_content_must_be_refetched(self):
        self.payload.update(brief_url='doc:1', linked_content='Approved linked brief')
        self.digest = approval.brief_digest(self.payload)
        self.records = [self.record()]
        self.assertTrue(self.valid())
        self.payload['linked_content'] = 'Changed requirements'
        self.assertFalse(self.valid())
        self.payload['linked_content'] = None
        self.assertFalse(self.valid())

    def test_revocation_and_fresh_grant(self):
        self.records.append(self.record('REVOKED', author='alice'))
        self.assertFalse(self.valid())
        self.assertFalse(self.valid(label_present=False))
        self.records.append(self.record())
        self.assertTrue(self.valid())
        self.records.append(self.record(author='alice'))
        self.assertFalse(self.valid())  # No fallback to Bob's earlier approval.

    def test_legacy_quoted_edited_and_unattributable_records(self):
        records = [self.record(body='[ai-first] APPROVED'),
                   self.record(body='> ' + self.records[0]['body']),
                   self.record(edited=True), self.record(human=False),
                   self.record(author=''), self.record(body=self.records[0]['body']+' extra')]
        for record in records:
            with self.subTest(record=record):
                self.assertFalse(self.valid(records=[record]))
        self.assertFalse(self.valid(records=[]))
        self.assertFalse(self.valid(records=[dict(body=self.records[0]['body'], author='bob')]))

    def test_historical_records_do_not_prevent_migration(self):
        old = self.record(edited=True)
        old['body'] = old['body'].replace(self.payload['revision'],
                                        '12345678-1234-4234-8234-123456789abd')
        self.records = [self.record(body='[ai-first] APPROVED'), old, self.record()]
        self.assertTrue(self.valid())

    def test_unverifiable_snapshot_fails_closed(self):
        for key in ('label_present', 'requester_verified', 'history_complete', 'snapshot_stable'):
            for value in (False, None, 'true'):
                with self.subTest(key=key, value=value):
                    self.assertFalse(self.valid(**{key: value}))

    def test_wrong_digest_latest_record_blocks(self):
        bad = self.record(body=self.records[0]['body'].replace(self.digest, 'sha256:'+'0'*64))
        self.records.append(bad)
        self.assertFalse(self.valid())

    def test_label_restoration_and_exact_content_restoration(self):
        self.assertFalse(self.valid(label_present=False))
        self.assertTrue(self.valid(label_present=True))
        original = copy.deepcopy(self.payload)
        self.payload['description'] = 'Edited'
        self.assertFalse(self.valid())
        self.payload = original
        self.assertTrue(self.valid())
        self.records.append(self.record('REVOKED'))
        self.assertFalse(self.valid())

    def test_invalid_payloads_do_not_grant_approval(self):
        for changes in ({'revision': 'bad'}, {'open_decisions': True}, {'requester': ''},
                        {'linked_content': 'unexpected'}, {'unknown': 'value'}):
            with self.subTest(changes=changes):
                self.assertFalse(self.valid(payload=dict(self.payload, **changes)))


if __name__ == '__main__':
    unittest.main()
