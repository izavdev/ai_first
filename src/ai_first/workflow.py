"""Pure mode dispatch and reclassification transitions; no tracker operations."""
import re

from .classification import classify

TIERS = {'human-only': 0, 'pair': 1, 'delegate': 2}
CYCLE_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9._:/@+\-]*')


def select_mode(requested=None, *, kind=None):
    """Dispatch after read-only intake; a missing brief never implies an exception."""
    if requested == 'single-task':
        requested = 'single-item'
    if requested not in (None, 'decompose', 'reclassify', 'single-item'):
        raise ValueError('Unknown mode')
    if kind not in (None, 'brief', 'task'):
        raise ValueError('Invalid item kind; repair the schema')
    if requested == 'single-item':
        if kind is not None:
            raise ValueError('Single-item mode requires an unclassified item')
        return requested
    mode = requested or {'brief': 'decompose', 'task': 'reclassify'}.get(kind)
    if mode is None:
        raise ValueError('Specify the intended mode for this unclassified item')
    if kind != {'decompose': 'brief', 'reclassify': 'task'}[mode]:
        raise ValueError('Item kind does not match the requested mode')
    return mode


def reclassify(v, b, c, a, *, bounce, failed_cycles, cycle_id=None,
               hard_override=False, verification_valid=False, human_tier=None):
    """Count a newly evidenced failed cycle once, then apply the stricter tier.

    cycle_id is only supplied for an evidenced failure. Identity/authenticity and
    complete history are adapter responsibilities, not claims trusted from text.
    """
    if type(bounce) is not int or bounce < 0:
        raise ValueError('bounce must be a nonnegative integer')
    if not isinstance(failed_cycles, list) or any(
            not isinstance(key, str) or not CYCLE_ID.fullmatch(key) for key in failed_cycles):
        raise ValueError('Invalid failed cycle ledger')
    if len(set(failed_cycles)) != len(failed_cycles) or len(failed_cycles) != bounce:
        raise ValueError('Reconcile bounce with complete unique failed-cycle history')
    if cycle_id is not None and (not isinstance(cycle_id, str) or not CYCLE_ID.fullmatch(cycle_id)):
        raise ValueError('A failed cycle needs a stable ID')
    if human_tier is not None and human_tier not in TIERS:
        raise ValueError('Invalid human tier')
    derived = classify(v, b, c, a, hard_override=hard_override,
                       verification_valid=verification_valid)
    ledger = list(failed_cycles)
    new_failure = cycle_id is not None and cycle_id not in ledger
    if new_failure:
        ledger.append(cycle_id)
    count = len(ledger)
    candidates = [derived]
    if human_tier is not None:
        candidates.append(human_tier)
    if count >= 2:
        candidates.append('pair')
    return dict(tier=min(candidates, key=TIERS.get), bounce=count,
                failed_cycles=ledger, new_failure=new_failure, escalated=count >= 2)
