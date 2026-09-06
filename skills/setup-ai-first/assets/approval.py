"""Portable reference for brief approval binding. No tracker access or mutations.

CLI: python approval.py payload.json
The input shape and canonicalization are defined in ai-first-schema.md.
Identity, human authorship, complete history, and snapshot consistency are adapter
responsibilities. Do not infer these properties from an item's own assertions.
"""
import hashlib
import json
import re
import sys
import uuid

KEYS = {'item', 'revision', 'requester', 'title', 'description', 'brief_url',
        'linked_content', 'groomed_on', 'open_decisions'}
RECORD = re.compile(r'\[ai-first\] (APPROVED|REVOKED) revision=([0-9a-f-]{36}) digest=(sha256:[0-9a-f]{64})')


def _text(value):
    if not isinstance(value, str):
        raise ValueError('Expected text')
    return value.replace('\r\n', '\n').replace('\r', '\n')


def brief_digest(payload):
    """Hash a decoded tracker snapshot; never trust a stored digest alone."""
    if not isinstance(payload, dict) or set(payload) != KEYS:
        raise ValueError('Payload must contain exactly the documented keys')
    revision = payload['revision']
    if not isinstance(revision, str) or str(uuid.UUID(revision)) != revision:
        raise ValueError('Revision must be a canonical UUID')
    for key in ('item', 'requester', 'brief_url', 'groomed_on'):
        if not isinstance(payload[key], str) or not payload[key].strip():
            raise ValueError(f'Missing {key}')
    decisions = payload['open_decisions']
    if type(decisions) is not int or decisions < 0:
        raise ValueError('open_decisions must be a nonnegative integer')
    linked = payload['linked_content']
    if payload['brief_url'] == 'inline':
        if linked is not None:
            raise ValueError('Inline brief cannot carry linked_content')
    elif not isinstance(linked, str) or not linked.strip():
        raise ValueError('Linked brief content must be fetched')
    canonical = ['ai-first-brief/v1', payload['item'], revision,
                 payload['requester'], _text(payload['title']),
                 _text(payload['description']), payload['brief_url'],
                 None if linked is None else _text(linked),
                 payload['groomed_on'], decisions]
    encoded = json.dumps(canonical, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    return 'sha256:' + hashlib.sha256(encoded).hexdigest()


def approval_valid(payload, stored_digest, records, *, label_present,
                   requester_verified, history_complete, snapshot_stable,
                   solo_identity=None):
    """Evaluate chronologically ordered, adapter-normalized human comments.

    records: [{body, author, human, edited}], ordered by creation time. The adapter
    must reject ambiguous ordering, missing metadata and noncanonical identities.
    solo_identity is verified project configuration, never an item field.
    """
    if any(value is not True for value in
           (label_present, requester_verified, history_complete, snapshot_stable)):
        return False
    try:
        digest = brief_digest(payload)
    except (ValueError, TypeError, AttributeError):
        return False
    if digest != stored_digest or payload['open_decisions'] != 0:
        return False
    latest = None
    for record in records:
        body = record.get('body')
        if not isinstance(body, str):
            return False
        # Only standalone protocol messages participate. Quoted examples do not.
        if not body.startswith(('[ai-first] APPROVED revision=', '[ai-first] REVOKED revision=')):
            continue
        match = RECORD.fullmatch(body)
        if not match:
            return False
        action, revision, signed_digest = match.groups()
        if revision != payload['revision']:
            continue
        if (record.get('human') is not True
                or record.get('edited') is not False
                or not isinstance(record.get('author'), str)
                or not record['author'].strip()):
            return False
        # A wrong digest for this revision invalidates the current grant.
        latest = (action, signed_digest, record['author'])
    if latest is None:
        return False
    action, signed_digest, actor = latest
    return (action == 'APPROVED' and signed_digest == digest
            and (actor != payload['requester'] or actor == solo_identity))


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Usage: python approval.py payload.json')
    with open(sys.argv[1], encoding='utf-8') as stream:
        print(brief_digest(json.load(stream)))
