# Workflow evaluation and pilot

The ten [cases](workflow-cases.json) cover mechanical work, bounded implementation
choices, a sham verifier, unavailable context, a public-contract boundary, credential
handling, unresolved decisions, provisional capabilities, small intake, and uncertain
creation. Reference answers are draft rubric-derived expectations that still need
maintainer calibration. They are not production telemetry or capability-promotion evidence.

## Run a blind offline evaluation

```bash
python3 scripts/evaluate_workflow.py --blind-output /tmp/ai-first-cases.json
```

Give an evaluator only the exported cases, their response contract, and the current
installed skills/configuration. Use an isolated workspace; no tracker mutations,
brief approvals, or implementation changes are needed. Ask it to use the documented
policy and save independently produced answers as:

```json
{
  "schema": "ai-first-predictions/v1",
  "mode": "independent-offline-agent",
  "evaluator": "actual evaluator identifier",
  "results": []
}
```

Each result follows the exported response contract. Optional `duration_seconds` and
`human_review_seconds` are actual measured values or omitted, never estimated from
the answer. Keep rationales and note missing/contradictory instructions. Do not
give reference answers to the evaluator or manufacture predictions by copying them.

```bash
python3 scripts/evaluate_workflow.py --predictions /tmp/predictions.json
```

The grader reports exact agreement, unsafe delegation, missing cases, and available
timing medians. Missing responses remain in the denominator. Exit 1 means a mismatch,
not automatically a safety failure: inspect the raw decision and rationale. Preserve
initial results before making supported wording or harness changes.

The [initial independent run](results/2026-09-07-offline-initial-result.json) scored
9/10 exact matches with no unsafe delegation. Its uncertain-create answer refused
creation correctly, but used `stop-for-reconciliation` instead of `block`; the first
blind export had omitted allowed response enums. The response contract now specifies
them. The evaluator also identified ambiguous raw-scoring language and an outdated
capability-invariant reference, both corrected in the workflow sources. Raw predictions
and the evaluated skill hashes are retained alongside the result. This small synthetic
run does not establish inter-rater reliability, task completion quality, or team benefit.

The [rerun](results/2026-09-07-offline-rerun-result.json) with clarified instructions
and explicit output enums matched all ten cases with no unsafe delegation. The same
independent evaluator performed this rerun without reference answers. It also confirmed
the instructions distinguish absent blocks from malformed blocks and new plans from
resumed plans. Both raw runs and their context hashes remain available; this is a
small offline behavioral check, not a human-reviewed live pilot.

## Exercise the installed workflow

`python3 scripts/validate_repo.py` includes tests against copied setup assets in a
temporary consumer repository. The synthetic GitHub flow covers full-snapshot
approval, changed-content rejection, a timed-out create, safe resume of a closed
unlinked child, and copied local verification with a real passing and failing case
bound to an exact task snapshot. Separate fixtures exercise GitHub REST, ADO REST,
and Linear GraphQL comment pagination. These are API-shaped synthetic fixtures,
not live storage or connector certification.

## Measure inventory cost

```bash
python3 scripts/benchmark_inventory.py --items 10000 --writes 10
```

This local workload counts body downloads with and without the strong-revision
cache: 110,000 versus 10,010 for the default case. It still requires 110,000 complete
listing records. Printed elapsed time measures Python work on this machine, not
network latency. Use caching only after the actual connection demonstrates reliable
item revisions; timestamps and incomplete searches do not qualify.

## Run an authorized live pilot

Choose a disposable tracker container and a human reviewer before creating test
items. Record the server/client version, permissions, response captures, storage
format, pagination, and conditional-write behavior in the adapter evidence record.
Do not mark a server supported solely because its brand has a shipped adapter.

Start with an empty capability manifest and a modest set of real, reviewed tasks.
Record original request, independent raw scores/rationales, chosen tier, preparation
time, human review time, successful completion, duplicate items, failure cycles,
and any unplanned human rescue. Use the team's actual observations; a reference
score is not ground truth merely because it appears in this corpus.

Exercise a complete brief → manual approval → decomposition → verification flow,
then change the approved brief and verify it blocks. Simulate a lost create response
in the test container and verify a resume finds the existing child. Include two-page
comment history and a preexisting unrelated label. Confirm stored Markdown survives
the real service before accepting description-round-trip evidence. Retain task-bound
verification output and reviewer dispositions; follow approved cleanup procedures.

Live tracker certification and measured team outcomes remain pending until these
observations exist. Do not convert an offline agent result into a claim of human
review, actual tool use, or capability promotion.
