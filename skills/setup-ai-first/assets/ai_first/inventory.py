"""Reuse bodies only behind complete listings and authoritative strong revisions.

Never use timestamps, search snippets, or absence from a partial search as proof.
The adapter establishes listing completeness and revision semantics. This cache is
an optimization within a read/recheck cycle, not a lock or an idempotency service.
"""
import hashlib
import json


def refresh_inventory(listing, fetched, cache=None, *, inventory_complete=False,
                      strong_revisions=False):
    """Return missing body IDs or a complete normalized inventory and next cache.

    listing: [{id, revision}], all states including unlinked items. fetched:
    [{id, revision, item}], where item is the normalized reconcile() snapshot.
    Cache entries are bound to exact item bytes so accidental edits are rejected.
    With strong_revisions=False every body must be fetched, regardless of cache.
    """
    if inventory_complete is not True:
        raise ValueError('A complete authoritative inventory listing is required')
    if type(strong_revisions) is not bool:
        raise ValueError('Revision support must be an established boolean')
    if not isinstance(listing, list) or not isinstance(fetched, list):
        raise ValueError('Listing and fetched snapshots must be arrays')
    cache = {} if cache is None else cache
    if not isinstance(cache, dict):
        raise ValueError('Invalid inventory cache')
    revisions = {}
    for entry in listing:
        identity, revision = entry['id'], entry['revision']
        if not isinstance(identity, str) or not identity.strip():
            raise ValueError('Missing canonical inventory identity')
        if type(revision) not in (int, str) or not str(revision).strip():
            raise ValueError('Missing item revision')
        if identity in revisions and revisions[identity] != revision:
            raise ValueError('Conflicting inventory revisions; refetch the listing')
        revisions[identity] = revision
    supplied = {}
    for entry in fetched:
        identity = entry['id']
        if identity not in revisions or entry['revision'] != revisions[identity]:
            raise ValueError('Fetched snapshot differs from listing; refetch the listing')
        if not isinstance(entry['item'], dict) or entry['item'].get('id') != identity:
            raise ValueError('Snapshot canonical identity mismatch')
        if identity in supplied and supplied[identity] != entry:
            raise ValueError('Conflicting fetched snapshots')
        supplied[identity] = entry
    next_cache, missing = {}, []
    for identity, revision in revisions.items():
        entry = supplied.get(identity)
        if entry is None and strong_revisions:
            old = cache.get(identity)
            if isinstance(old, dict) and old.get('revision') == revision:
                raw = json.dumps(old.get('item'), sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()
                if old.get('digest') != 'sha256:' + hashlib.sha256(raw).hexdigest():
                    raise ValueError('Cached snapshot changed; discard cache and refetch')
                if not isinstance(old.get('item'), dict) or old['item'].get('id') != identity:
                    raise ValueError('Cached identity mismatch')
                entry = old
        if entry is None:
            missing.append(identity)
            continue
        raw = json.dumps(entry['item'], sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()
        next_cache[identity] = dict(revision=revision, item=entry['item'],
                                    digest='sha256:' + hashlib.sha256(raw).hexdigest())
    return dict(complete=not missing, fetch_ids=missing, cache=next_cache,
                items=[] if missing else [entry['item'] for entry in next_cache.values()],
                listing_count=len(revisions), fetched_count=len(supplied))
