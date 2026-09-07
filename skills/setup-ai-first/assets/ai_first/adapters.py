"""Validate captured adapter evidence and normalize complete comment pages.

Inputs are supplied by an authenticated caller, never read from item assertions.
No function proves that a capture is authentic or that a human identity is genuine.
"""
from datetime import datetime
from pathlib import Path

from .installation import read_json

CONTRACT_PATH = Path(__file__).resolve().parent.parent / 'adapter-contract.json'


def check_adapter(evidence):
    contract = read_json(CONTRACT_PATH)
    if evidence.get('tracker') not in ('github', 'ado', 'linear'):
        raise ValueError('Unknown tracker')
    server = evidence.get('server', {})
    if not all(isinstance(server.get(key), str) and server[key].strip() for key in ('name', 'version')):
        raise ValueError('Record the actual connected server/client name and version')
    checks = evidence.get('checks', {})
    missing = [name for name in contract['required'] if not isinstance(checks.get(name), dict)
               or checks[name].get('supported') is not True
               or not isinstance(checks[name].get('evidence'), str)
               or not checks[name]['evidence'].strip()]
    concurrency = evidence.get('concurrency')
    if concurrency not in ('conditional-writes', 'serialized'):
        missing.append('concurrency: establish conditional writes or serialized operation')
    return dict(ready=not missing, tracker=evidence['tracker'], server=server,
                missing=missing, concurrency=concurrency,
                scope='Caller-supplied capability evidence; not a live integration certification')


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError('Missing comment timestamp')
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('Comment timestamps require a timezone')
    return result


def normalize_history(tracker, pages, human_ids):
    """Normalize API-shaped pages with an explicitly completed cursor chain.

    Each capture has request_cursor and data. GitHub also needs next_cursor from
    the HTTP Link header (explicit null when absent). ADO uses continuationToken;
    Linear uses connection pageInfo. Human IDs are independently reviewed identities.
    """
    if tracker not in ('github', 'ado', 'linear') or not isinstance(pages, list) or not pages:
        raise ValueError('Supply tracker and every captured comment page')
    if not isinstance(human_ids, list) or any(not isinstance(i, str) or not i.strip() for i in human_ids):
        raise ValueError('Supply independently verified canonical human IDs')
    humans = {i.casefold() if tracker == 'github' else i for i in human_ids}
    cursor, used_cursors, comments = None, set(), {}
    for page in pages:
        if 'request_cursor' not in page or page['request_cursor'] != cursor:
            raise ValueError('Missing, reordered, or disconnected history page')
        if cursor in used_cursors:
            raise ValueError('Repeated history cursor')
        used_cursors.add(cursor)
        data = page['data']
        if tracker == 'github':
            rows = data
            cursor = page['next_cursor']  # Capture absence explicitly; do not guess from row count.
        elif tracker == 'ado':
            rows = data['comments']
            if 'continuationToken' not in data:
                raise ValueError('ADO capture must explicitly record absent continuationToken as null')
            cursor = data['continuationToken'] or None
        else:
            rows = data['nodes']
            info = data['pageInfo']
            if type(info['hasNextPage']) is not bool:
                raise ValueError('Invalid Linear pagination metadata')
            cursor = info['endCursor'] if info['hasNextPage'] else None
            if info['hasNextPage'] and not cursor:
                raise ValueError('Missing Linear continuation cursor')
        if cursor is not None and (not isinstance(cursor, str) or not cursor.strip()):
            raise ValueError('Invalid history cursor')
        if not isinstance(rows, list):
            raise ValueError('Comment page must contain an array')
        for row in rows:
            if row.get('isDeleted') is True:
                continue  # Capture retains the audited deletion; deleted records grant nothing.
            if tracker == 'github':
                actor = row['user']['login']
                actor = actor.casefold() if isinstance(actor, str) else actor
                body, created, updated = row['body'], row['created_at'], row['updated_at']
                nonhuman = row['user'].get('type') != 'User'
            elif tracker == 'ado':
                actor = row['createdBy']['id']
                body, created, updated = row['text'], row['createdDate'], row['modifiedDate']
                nonhuman = False  # Human status still requires independent identity resolution.
            else:
                actor = row['user']['id']
                body, created, updated = row['body'], row['createdAt'], row['updatedAt']
                nonhuman = False
            if not isinstance(actor, str) or not actor.strip() or not isinstance(body, str):
                raise ValueError('Missing attributable comment body/author')
            identity = row.get('id', row.get('commentId'))
            if 'id' in row and 'commentId' in row and row['id'] != row['commentId']:
                raise ValueError('Conflicting comment identities')
            if type(identity) not in (int, str) or not str(identity).strip():
                raise ValueError('Missing stable comment identity')
            created_at, updated_at = timestamp(created), timestamp(updated)
            if updated_at < created_at:
                raise ValueError('Comment modification predates creation')
            record = dict(body=body, author=actor, human=actor in humans and not nonhuman,
                          edited=created_at != updated_at or (tracker == 'ado' and row.get('version', 1) != 1))
            snapshot = (created_at, record)
            if identity in comments and comments[identity] != snapshot:
                raise ValueError('Conflicting snapshots for one comment')
            comments[identity] = snapshot
    if cursor is not None:
        raise ValueError('Incomplete comment history: fetch the continuation page')
    ordered = sorted(comments.values(), key=lambda value: value[0])
    protocol_times = set()
    for created_at, record in ordered:
        if record['body'].startswith(('[ai-first] APPROVED revision=', '[ai-first] REVOKED revision=')):
            if created_at in protocol_times:
                raise ValueError('Ambiguous protocol comment creation order')
            protocol_times.add(created_at)
    return [record for _, record in ordered]


def tag_patch(revision, current, add=None, remove=None):
    """ADO JSON Patch for reviewed selective changes; apply through authenticated tools."""
    if type(revision) is not int or revision < 1 or not isinstance(current, str):
        raise ValueError('Supply fetched numeric ADO revision and current System.Tags text')
    add, remove = [] if add is None else add, [] if remove is None else remove
    for values in (add, remove):
        if not isinstance(values, list) or any(not isinstance(v, str) or not v.strip()
                or ';' in v or '\n' in v or '\r' in v for v in values):
            raise ValueError('Tag changes must be arrays of individual tag names')
    removals = {name.strip().casefold() for name in remove}
    if removals & {name.strip().casefold() for name in add}:
        raise ValueError('A tag cannot be added and removed together')
    existing = [name.strip() for name in current.split(';') if name.strip()]
    tags = {name.casefold(): name for name in existing if name.casefold() not in removals}
    for name in add:
        tags.setdefault(name.strip().casefold(), name.strip())
    return [dict(op='test', path='/rev', value=revision),
            dict(op='replace' if current else 'add', path='/fields/System.Tags',
                 value='; '.join(tags.values()))]
