"""Preflight outbound tracker payloads before an expensive remote write."""


def preflight_payload(payload, forbidden=None, max_bytes=None):
    if not isinstance(payload, str) or not payload:
        raise ValueError('payload must be a nonempty string')
    if forbidden is None:
        forbidden = ['PLACEHOLDER']
    if (not isinstance(forbidden, list) or any(not isinstance(value, str) or not value
                                               for value in forbidden)):
        raise ValueError('forbidden must be a list of nonempty strings')
    if max_bytes is not None and (isinstance(max_bytes, bool) or not isinstance(max_bytes, int)
                                  or max_bytes <= 0):
        raise ValueError('max_bytes must be a positive integer or null')

    matched = [value for value in forbidden if value in payload]
    size = len(payload.encode('utf-8'))
    over_limit = max_bytes is not None and size > max_bytes
    issues = [f'forbidden marker remains: {value}' for value in matched]
    if over_limit:
        issues.append(f'payload is {size} UTF-8 bytes; declared limit is {max_bytes}')
    return dict(ready=not issues, utf8_bytes=size, matched_forbidden=matched,
                over_limit=over_limit, issues=issues)
