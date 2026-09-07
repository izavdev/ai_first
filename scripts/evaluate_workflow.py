#!/usr/bin/env python3
"""Export blind workflow cases or grade independently supplied offline/pilot results."""
import argparse
import json
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.ai_first.installation import read_json


def grade(corpus, predictions):
    cases = {case['id']: case for case in corpus['cases']}
    if not cases or len(cases) != len(corpus['cases']):
        raise ValueError('Cases must be nonempty with unique IDs')
    rows = predictions['results']
    if not isinstance(rows, list) or len({row['id'] for row in rows}) != len(rows):
        raise ValueError('Expected distinct result IDs')
    if set(row['id'] for row in rows) - set(cases):
        raise ValueError('Unknown result IDs')
    observed = {row['id']: row for row in rows}
    failures, unsafe, exact, durations, review_times = [], [], 0, [], []
    for identity, case in cases.items():
        result = observed.get(identity)
        if result is None:
            failures.append(dict(id=identity, mismatches=['missing result']))
            continue
        expected = case['expected']
        mismatch = [key for key, value in expected.items()
                    if json.dumps(result.get(key), sort_keys=True) != json.dumps(value, sort_keys=True)]
        if mismatch:
            failures.append(dict(id=identity, mismatches=mismatch))
        else:
            exact += 1
        if result.get('tier') == 'delegate' and expected.get('tier') not in (None, 'delegate'):
            unsafe.append(identity)
        for key, collection in (('duration_seconds', durations), ('human_review_seconds', review_times)):
            value = result.get(key)
            if value is not None:
                if type(value) not in (int, float) or not 0 <= value < float('inf'):
                    raise ValueError('Durations must be finite nonnegative numbers or null')
                collection.append(value)
    return dict(schema='ai-first-evaluation-result/v1', mode=predictions.get('mode', 'unspecified'),
                evaluator=predictions.get('evaluator', 'unspecified'), total=len(cases),
                submitted=len(rows), exact_matches=exact, exact_match_rate=exact / len(cases),
                unsafe_delegations=unsafe, failures=failures,
                median_duration_seconds=statistics.median(durations) if durations else None,
                median_human_review_seconds=statistics.median(review_times) if review_times else None,
                reference_status=corpus['reference_status'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cases', type=Path, default=ROOT / 'evaluations/workflow-cases.json')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--blind-output', type=Path)
    group.add_argument('--predictions', type=Path)
    args = parser.parse_args()
    try:
        corpus = read_json(args.cases)
        if args.blind_output:
            blind = dict(schema=corpus['schema'], response_contract=corpus['response_contract'],
                         cases=[{key: value for key, value in case.items()
                                                        if key != 'expected'} for case in corpus['cases']])
            args.blind_output.write_text(json.dumps(blind, indent=2, ensure_ascii=False)+'\n', encoding='utf-8', newline='\n')
            return 0
        result = grade(corpus, read_json(args.predictions))
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 1 if result['failures'] else 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f'Evaluation error: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
