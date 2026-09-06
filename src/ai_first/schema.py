"""Strict reference codec/validator for tracker-normalized Markdown, not HTML.

This checks syntax and internally consistent fields, not truth of scores, human
identity, approval authenticity, or completeness of a verification command.
"""
from datetime import date
import json
from pathlib import Path
import re
import uuid

from .classification import classify
from .decomposition import unit_key

CONTRACT_PATH = Path(__file__).resolve().parents[2] / 'skills/setup-ai-first/assets/workflow-contract.json'
CONTRACT = json.loads(CONTRACT_PATH.read_text())
TIERS = {'human-only': 0, 'pair': 1, 'delegate': 2}


def typed(value, rule):
    if not isinstance(value, str) or not value.strip() or '\n' in value or '\r' in value:
        raise ValueError('Field values must be nonempty single-line text')
    if rule == 'text':
        return value
    if rule in ('brief', 'task', 'brief-approval/v1'):
        if value != rule:
            raise ValueError(f'Expected {rule}')
    elif rule == 'uint':
        if not re.fullmatch(r'0|[1-9][0-9]*', value):
            raise ValueError('Expected nonnegative decimal integer')
    elif rule == 'uuid':
        if str(uuid.UUID(value)) != value:
            raise ValueError('Expected canonical UUID')
    elif rule == 'digest':
        if not re.fullmatch(r'sha256:[0-9a-f]{64}', value):
            raise ValueError('Expected SHA-256 digest')
    elif rule == 'date':
        if date.fromisoformat(value).isoformat() != value:
            raise ValueError('Expected ISO date')
    elif rule == 'tier':
        if value not in TIERS:
            raise ValueError('Invalid tier')
    elif rule in ('scores', 'deltas'):
        ceiling = '2' if rule == 'scores' else '1'
        if not re.fullmatch(fr'V[0-{ceiling}] B[0-{ceiling}] C[0-{ceiling}] A[0-{ceiling}]', value):
            raise ValueError('Invalid axis values/order')
    elif rule in ('slug', 'slugs'):
        parts = value.split(',') if rule == 'slugs' else [value]
        if len(set(p.strip() for p in parts)) != len(parts) or any(
                not re.fullmatch(r'[a-z][a-z0-9-]*', p.strip()) for p in parts):
            raise ValueError('Expected unique lowercase slugs')
    elif rule == 'cycles':
        if value != 'none':
            parts = [p.strip() for p in value.split(',')]
            if len(set(parts)) != len(parts) or any(not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:/@+\-]*', p) for p in parts):
                raise ValueError('Invalid cycle ledger')
    else:
        raise ValueError(f'Unknown contract type {rule}')
    return value


def validate(fields, labels=None):
    kind = fields.get('kind')
    if kind not in ('brief', 'task'):
        raise ValueError('Unknown item kind')
    for key, rule in CONTRACT[kind].items():
        if key not in fields:
            raise ValueError(f'Missing required field: {key}')
        typed(fields[key], rule)
    if kind == 'task':
        for key, rule in CONTRACT['optional_task'].items():
            if key in fields:
                typed(fields[key], rule)
        axes = lambda key: tuple(int(p[1:]) for p in fields[key].split())
        raw, final, delta = axes('raw-scores'), axes('scores'), axes('capability-deltas')
        if delta[1] or tuple(a + b for a, b in zip(raw, delta)) != final:
            raise ValueError('Final scores must equal raw plus delta; B cannot change')
        cycles = [] if fields['failed-cycles'] == 'none' else fields['failed-cycles'].split(',')
        if int(fields['bounce']) != len(cycles):
            raise ValueError('Bounce/ledger mismatch')
        tier = fields['tier']
        derived = classify(*final, verification_valid=bool(fields.get('verify')))
        if TIERS[tier] > TIERS[derived] or (int(fields['bounce']) >= 2 and tier == 'delegate'):
            raise ValueError('Tier exceeds rubric or bounce cap')
        for key in (('verify', 'stop-ask') if tier == 'delegate' else ()):
            if not fields.get(key):
                raise ValueError(f'Delegate requires {key}')
        if tier != 'human-only' and not fields.get('profile'):
            raise ValueError('Delegate/pair requires profile')
        if tier == 'human-only' and 'profile' in fields:
            raise ValueError('Human-only omits profile')
        provenance = CONTRACT['provenance']
        if set(fields) & set(provenance):
            for key, rule in provenance.items():
                if key not in fields:
                    raise ValueError('Partial decomposition provenance')
                typed(fields[key], rule)
            expected = unit_key(fields['decomposition-parent'], fields['parent-revision'],
                                fields['parent-brief-digest'], fields['decomposition-unit'])
            if fields['decomposition-key'] != expected:
                raise ValueError('Decomposition key mismatch')
        if labels is not None:
            expected = {'delegate': 'ai-delegate', 'pair': 'ai-pair', 'human-only': 'human-only'}[tier]
            if set(labels) & {'ai-delegate', 'ai-pair', 'human-only'} != {expected}:
                raise ValueError('Tier label mismatch')
            if int(fields['bounce']) >= 2 and 'ai-escalated' not in labels:
                raise ValueError('Missing escalation label')
    return fields


def decode(body, tracker='github', *, labels=None):
    if tracker not in ('github', 'ado', 'linear'):
        raise ValueError('Unknown tracker')
    lines = body.replace('\r\n', '\n').replace('\r', '\n').splitlines(keepends=True)
    candidates = [i for i, line in enumerate(lines) if line.rstrip('\n') == CONTRACT['sentinel']]
    if not candidates:
        raise ValueError('Missing sentinel')
    i = candidates[-1]  # Malformed last block fails; never fall back to older data.
    previous = lines[i-1].rstrip('\n') if i else ''
    fenced = tracker == 'linear'
    start = i - 1
    if tracker == 'linear':
        if previous not in ('```', '```text'):
            raise ValueError('Linear requires a fence directly before sentinel')
    else:
        if previous != '---':
            raise ValueError('Opening delimiter missing')
        if start and lines[start-1].rstrip('\n') in ('```', '```text'):
            start -= 1
            fenced = True
    fields = {}
    end = i + 1
    while end < len(lines) and lines[end].rstrip('\n') != '---':
        match = re.fullmatch(r'([a-z][a-z0-9-]*):[ \t]*(.*)', lines[end].rstrip('\n'))
        if not match or match[1] in fields:
            raise ValueError('Malformed or duplicate field')
        fields[match[1]] = match[2]
        end += 1
    if end == len(lines):
        raise ValueError('Closing delimiter missing')
    if fenced and (end+1 == len(lines) or lines[end+1].rstrip('\n') != '```'):
        raise ValueError('Closing fence missing')
    human = ''.join(lines[:start])
    # One newline separates the human text from the canonical encoding.
    if human.endswith('\n'):
        human = human[:-1]
    return human, validate(fields, labels)


def encode(human, fields, tracker='github'):
    if tracker not in ('github', 'ado', 'linear'):
        raise ValueError('Unknown tracker')
    validate(fields)
    for key, value in fields.items():
        if not re.fullmatch(r'[a-z][a-z0-9-]*', key):
            raise ValueError('Invalid field name')
        typed(value, 'text')
    opening = '```\n' if tracker == 'linear' else '```\n---\n'
    return human.replace('\r\n', '\n').replace('\r', '\n') + '\n' + opening + CONTRACT['sentinel'] + '\n' + ''.join(
        f'{key}: {value}\n' for key, value in fields.items()) + '---\n```\n'
