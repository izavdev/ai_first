"""Reference decomposition reconciliation; never performs tracker writes.

Adapters provide complete normalized inventory, persisted plans, and create intents.
This detects retries/conflicts; exactly-once concurrent creation needs tracker support.
"""
import hashlib
import json
import re
import uuid


def unit_key(parent, revision, brief_digest, unit_id):
    if not isinstance(parent, str) or not parent.strip():
        raise ValueError('Missing canonical parent')
    for value in (revision, unit_id):
        if not isinstance(value, str) or str(uuid.UUID(value)) != value:
            raise ValueError('Expected canonical UUID')
    if not isinstance(brief_digest, str) or not re.fullmatch(r'sha256:[0-9a-f]{64}', brief_digest):
        raise ValueError('Invalid approved brief digest')
    raw = json.dumps(['ai-first-unit/v1', parent, revision, brief_digest, unit_id],
                     ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def validate_plan(plan):
    if not isinstance(plan, dict) or set(plan) != {'schema', 'parent', 'revision', 'brief_digest', 'units'}:
        raise ValueError('Invalid decomposition plan')
    if plan['schema'] != 'ai-first-decomposition/v1' or not isinstance(plan['units'], list) or not plan['units']:
        raise ValueError('Plan requires units')
    seen = set()
    for unit in plan['units']:
        if not isinstance(unit, dict) or set(unit) != {'id', 'title', 'body', 'depends_on'}:
            raise ValueError('Invalid planned unit')
        unit_key(plan['parent'], plan['revision'], plan['brief_digest'], unit['id'])
        if unit['id'] in seen or not all(isinstance(unit[k], str) and unit[k].strip() for k in ('title', 'body')):
            raise ValueError('Duplicate unit or empty content')
        dependencies = unit['depends_on']
        if (not isinstance(dependencies, list) or any(not isinstance(d, str) for d in dependencies)
                or len(set(dependencies)) != len(dependencies) or not set(dependencies) <= seen):
            raise ValueError('Dependencies must reference distinct earlier units')
        seen.add(unit['id'])
    return plan


def select_plan(plans):
    """Accept identical retry copies, but never choose between competing plans."""
    if not plans:
        return None
    canonical = set()
    for plan in plans:
        validate_plan(plan)
        canonical.add(json.dumps(plan, sort_keys=True, ensure_ascii=False, separators=(',', ':')))
    if len(canonical) != 1:
        raise ValueError('Conflicting persisted plans require reconciliation')
    return plans[0]


def reconcile(plan, items, intents, *, inventory_complete=False, resolved_prior=None):
    """Return create/reuse decisions, or block the batch on ambiguity.

    items: canonical id, parent marker, revision, brief_digest, key, title, body.
    Include all states and unlinked items, not just current hierarchy children.
    intents maps keys to pending, created, or confirmed-not-created; adapters must
    resolve that state from durable history. Missing intent means no attempt began.
    """
    validate_plan(plan)
    resolved_prior = {} if resolved_prior is None else resolved_prior
    if not isinstance(resolved_prior, dict) or any(not isinstance(k, str) or not k.strip()
            or not isinstance(v, str) or not v.strip() for k, v in resolved_prior.items()):
        raise ValueError('Prior-item resolutions require canonical IDs and reviewed evidence')
    if inventory_complete is not True:
        raise ValueError('Complete tracker inventory required before creation')
    desired = {unit_key(plan['parent'], plan['revision'], plan['brief_digest'], u['id']): u
               for u in plan['units']}
    if not isinstance(intents, dict) or any(k not in desired or v not in
            ('pending', 'created', 'confirmed-not-created') for k, v in intents.items()):
        raise ValueError('Unknown or conflicting create intent')
    found = {}
    for item in items:
        if item.get('parent') != plan['parent'] and item.get('key') not in desired:
            continue
        if (item.get('parent') != plan['parent'] or item.get('revision') != plan['revision']
                or item.get('brief_digest') != plan['brief_digest'] or item.get('key') not in desired):
            if item.get('key') not in desired and item.get('id') in resolved_prior:
                continue  # Explicit human disposition, never suppress a current-key collision.
            raise ValueError('Legacy, prior-revision, or conflicting child requires explicit reconciliation')
        key = item['key']
        if not isinstance(item.get('id'), str) or not item['id'].strip():
            raise ValueError('Missing canonical child identity')
        if key in found and found[key] != item:
            raise ValueError('Multiple items or conflicting snapshots for one unit key')
        found[key] = item
    actions = []
    for key, unit in desired.items():
        existing = found.get(key)
        if existing:
            actions.append(dict(action='reuse', key=key, item=existing['id'],
                                content_changed=any(existing.get(k) != unit[k] for k in ('title', 'body'))))
        elif intents.get(key) in ('pending', 'created'):
            raise ValueError('Uncertain or missing created item: do not retry creation')
        else:
            actions.append(dict(action='create', key=key, unit=unit['id']))
    return actions
