"""JSON-in/JSON-out policy operations; no tracker calls or command execution."""
import argparse
import json
from pathlib import Path
import re
import sys

import approval
from . import PACKAGE_VERSION, POLICY_REVISION
from .adapters import check_adapter, normalize_history, tag_patch
from .capabilities import adjust_scores, promotion_ready
from .classification import classify
from .decomposition import reconcile, select_plan, unit_key
from .installation import doctor, read_json, record_installation
from .inventory import refresh_inventory
from .schema import decode, encode
from .workflow import intake, reclassify, select_mode


def snapshot(item, title, body, tracker='github', linked_content=None):
    if not isinstance(item, str) or not item.startswith(tracker + ':'):
        raise ValueError('Canonical item identity must match the selected tracker')
    human, fields = decode(body, tracker)
    if fields['kind'] != 'brief':
        raise ValueError('Expected a persisted brief snapshot')
    payload = dict(item=item, title=title, description=human, linked_content=linked_content,
                   revision=fields['brief-revision'], requester=fields['requester'],
                   brief_url=fields['brief-url'], groomed_on=fields['groomed-on'],
                   open_decisions=int(fields['open-decisions']))
    return dict(payload=payload, digest=approval.brief_digest(payload), stored_digest=fields['brief-digest'])


def check_brief(snapshot_data, records, *, label_present, requester_verified,
                history_complete, snapshot_stable):
    bound = snapshot(**snapshot_data)
    schema = Path(__file__).resolve().parent.parent / 'ai-first-schema.md'
    declarations = re.findall(r'^[ \t]*solo-mode:[ \t]*(.*)$', schema.read_text(encoding='utf-8'), re.MULTILINE)
    solo, warning = None, None
    try:
        value = json.loads(declarations[0]) if len(declarations) == 1 else False
        if len(declarations) > 1 or (value is not False and (not isinstance(value, str)
                or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]*', value))):
            raise ValueError('Invalid solo identity')
        solo = None if value is False else value
    except (ValueError, TypeError):
        warning = 'Malformed solo policy grants no exception; independent approval required'
    valid = approval.approval_valid(bound['payload'], bound['stored_digest'], records,
                label_present=label_present, requester_verified=requester_verified,
                history_complete=history_complete, snapshot_stable=snapshot_stable,
                solo_identity=solo)
    return dict(valid=valid, digest=bound['digest'], policy_warning=warning)


def dispatch(command, value):
    if not isinstance(value, dict):
        raise ValueError('Input must be a JSON object')
    if command == 'decode':
        human, fields = decode(**value)
        return dict(human=human, fields=fields)
    if command == 'encode':
        return dict(body=encode(**value))
    if command == 'classify':
        return dict(tier=classify(**value))
    if command == 'mode':
        return dict(mode=select_mode(**value))
    if command == 'intake':
        return intake(**value)
    if command == 'digest':
        return dict(digest=approval.brief_digest(value))
    if command == 'snapshot':
        return snapshot(**value)
    if command == 'check-brief':
        return check_brief(**value)
    if command == 'approval':
        return dict(valid=approval.approval_valid(**value))
    if command == 'reclassify':
        return reclassify(**value)
    if command == 'adjust-scores':
        return adjust_scores(**value)
    if command == 'promotion':
        return dict(ready=promotion_ready(**value))
    if command == 'select-plan':
        return dict(plan=select_plan(**value))
    if command == 'unit-key':
        return dict(key=unit_key(**value))
    if command == 'reconcile':
        return dict(actions=reconcile(**value))
    if command == 'adapter-check':
        return check_adapter(value)
    if command == 'history':
        return dict(records=normalize_history(**value))
    if command == 'tag-patch':
        return dict(operations=tag_patch(**value))
    if command == 'inventory':
        return refresh_inventory(**value)
    raise ValueError('Unknown operation')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('version')
    check = sub.add_parser('doctor', help='Read-only local compatibility check')
    check.add_argument('--root', default=str(Path(__file__).resolve().parent.parent))
    check.add_argument('--require-policy', default=POLICY_REVISION)
    receipt = sub.add_parser('record-installation', help='Record reviewed installed files; no copying')
    receipt.add_argument('--root', required=True)
    receipt.add_argument('--source-manifest', required=True)
    receipt.add_argument('--tracker', required=True, choices=('github', 'ado', 'linear'))
    for operation in ('decode', 'encode', 'classify', 'mode', 'intake', 'digest', 'approval', 'snapshot', 'check-brief',
                      'reclassify', 'adjust-scores', 'promotion', 'select-plan',
                      'unit-key', 'reconcile', 'adapter-check', 'history', 'tag-patch', 'inventory'):
        command = sub.add_parser(operation)
        command.add_argument('input', type=Path, help='UTF-8 JSON file; never an executable command')
    args = parser.parse_args(argv)
    try:
        if args.command == 'version':
            result = dict(policy_revision=POLICY_REVISION, package_version=PACKAGE_VERSION)
        elif args.command == 'doctor':
            result = doctor(args.root, args.require_policy)
        elif args.command == 'record-installation':
            result = record_installation(args.root, args.source_manifest, args.tracker)
        else:
            result = dispatch(args.command, read_json(args.input))
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        # A negative policy decision is never a successful authorization command.
        if (result.get('valid') is False or result.get('compatible') is False
                or result.get('ready') is False or result.get('complete') is False):
            return 1
        return 0
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        print(json.dumps(dict(error=str(error)), ensure_ascii=False))
        return 2
