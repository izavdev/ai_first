"""Reference capability evaluation policy, not evidence authentication or promotion.

Callers supply reviewed chronological records and resolved central approvals.
These functions cannot establish that a human claim or external artifact is true.
"""
AXES = ('V', 'B', 'C', 'A')


def scores_valid(scores):
    return (isinstance(scores, dict) and set(scores) == set(AXES)
            and all(type(v) is int and 0 <= v <= 2 for v in scores.values()))


def effects_valid(effects):
    return (isinstance(effects, dict) and bool(effects)
            and set(effects) <= {'V', 'C', 'A'}
            and all(type(v) is int and 0 <= v <= 1 for v in effects.values())
            and any(v == 1 for v in effects.values()))


def adjust_scores(raw, capabilities):
    """Apply resolved, centrally approved effects with a +1 total cap per axis.

    Entries contain id, version, effects, enabled, status, applicable (class/scope
    match), approved, evidence_current, and prerequisites_met. Missing/unknown checks grant no effect.
    """
    if not scores_valid(raw):
        raise ValueError('Invalid raw scores')
    final = dict(raw)
    deltas = dict.fromkeys(AXES, 0)
    applied = []
    for entry in capabilities:
        if (not isinstance(entry, dict) or not effects_valid(entry.get('effects'))
                or not entry.get('id') or not entry.get('version')
                or entry.get('status') != 'proven'
                or any(entry.get(key) is not True for key in
                       ('enabled', 'applicable', 'approved', 'evidence_current', 'prerequisites_met'))):
            continue
        actual = {}
        for axis in entry['effects']:
            if entry['effects'][axis] == 1 and deltas[axis] == 0 and raw[axis] < 2:
                final[axis] += 1
                deltas[axis] = 1
                actual[axis] = 1
        if actual:
            applied.append(dict(id=entry['id'], version=entry['version'], deltas=actual))
    return dict(raw_scores=dict(raw), scores=final, capability_deltas=deltas, applied=applied)


def promotion_ready(capability_id, version, covers, effects, trials, *, history_complete=False):
    """Review eligibility: latest ten completed trials per class, distinct tasks.

    Full relevant trial history is supplied in completion order. A trial records
    capability_id/version, task_id/class, completed, reviewed, supervised, used,
    prerequisites_met, outcome, baseline_scores, observed_scores, and axis_evidence.
    Observed scores are experimental and never update an execution tier themselves.
    """
    if (history_complete is not True or not covers or len(set(covers)) != len(covers)
            or not effects_valid(effects)):
        return False
    for task_class in covers:
        records = [t for t in trials if t.get('capability_id') == capability_id
                   and t.get('version') == version and t.get('class') == task_class
                   and t.get('completed') is True]
        # Repeated attempts on one task cannot manufacture ten independent tasks.
        # Keep the latest result for that task in chronological order.
        latest = {}
        for trial in records:
            task_id = trial.get('task_id')
            if not isinstance(task_id, str) or not task_id.strip():
                return False
            latest.pop(task_id, None)
            latest[task_id] = trial
        window = list(latest.values())[-10:]
        if len(window) < 10:
            return False
        for trial in window:
            if (trial.get('outcome') != 'pass'
                    or any(trial.get(key) is not True for key in
                           ('reviewed', 'supervised', 'used', 'prerequisites_met'))):
                return False
            if (not trial.get('reviewer') or trial.get('unplanned_rescue') is not False
                    or any(not trial.get(key) for key in
                           ('usage_evidence', 'prerequisite_evidence', 'verification_evidence'))):
                return False
            baseline, observed = trial.get('baseline_scores'), trial.get('observed_scores')
            if not scores_valid(baseline) or not scores_valid(observed):
                return False
            # Isolate the claimed effect; unchanged B and no unclaimed uplift.
            for axis in AXES:
                expected = effects.get(axis, 0)
                if observed[axis] - baseline[axis] != expected:
                    return False
                if expected and not trial.get('axis_evidence', {}).get(axis):
                    return False
    return True
