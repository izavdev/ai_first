"""Reference tier derivation for schema v1; does not score work or run commands."""


def classify(v, b, c, a, *, hard_override=False, verification_valid=False):
    """Derive a tier from final scores and caller-assessed policy conditions.

    verification_valid means the caller has established that one runnable command
    checks completion. A=1 means only bounded naming/structure choices remain,
    with linked conventions and explicit stop conditions; the caller assesses this.
    This function cannot establish command safety or coverage.
    """
    scores = (v, b, c, a)
    if any(type(score) is not int or not 0 <= score <= 2 for score in scores):
        raise ValueError("Scores must be integers from 0 through 2")
    if type(hard_override) is not bool or type(verification_valid) is not bool:
        raise ValueError("Policy conditions must be booleans")
    if hard_override or scores.count(0) >= 2:
        return "human-only"
    if (v, b, c) == (2, 2, 2) and a >= 1 and verification_valid:
        return "delegate"
    return "pair"
