# How to decompose and classify work

Use this skill to turn an approved brief into small execution items with delegation tiers and verification contracts. It also supports direct classification of small items and reclassification of existing items.

## Before you start

Run [setup-ai-first](setup-ai-first.md). The `.ai-first/` contract files must exist. Have tracker access and links to the relevant specs, ADRs, contracts, and repository context.

For normal decomposition, the parent must have `groomed` and `brief-approved`, attributable human approval satisfying the project policy (independent or configured solo self-approval), a valid brief schema block, and zero open decisions. Follow the [grooming guide](groom.md) to satisfy those requirements.

## Decompose an approved brief

```text
$decompose-and-classify #123
Decompose the approved brief into small execution items with dependency links.
```

1. The skill selects normal decomposition for the brief-kind parent, then checks the parent labels, approval identity, exact revision/content digest, schema, and open decisions. It repeats approval checking before each child write. A failed guard produces a comment with remediation and stops decomposition.
2. It first checks saved plans, create intents, and existing items in all states. If a plan exists for this approved revision, it resumes that plan. Otherwise it splits work into verifiable outcomes, links context, orders dependencies, and carries down human-only restrictions.
3. It scores each item's raw properties using the project schema, then reads the capability manifest and applicable approved metadata.
4. It saves the complete classified plan in the configured backend (tracker comment by default, or a pinned Git planning branch), assigns stable unit keys, then creates only missing units. It reuses existing matches, repairs unambiguous missing links/labels, and reports actual progress on the parent.

## Resume an interrupted decomposition

Invoke the same parent again:

```text
$decompose-and-classify #123
Resume the saved decomposition and report any incomplete links or labels.
```

The plan is saved before creating children, leaving the approved brief description
unchanged. By default it lives in a parent comment; optional branch storage uses a
parent PLAN-REF pointing to an exact repository/commit/path. See [plan storage](plan-storage.md). Unit IDs and keys persist across runs. A child carries
its parent identity, approved revision/digest, and unit key in the initial create
body, so it can be found even if hierarchy linking failed afterward.

For example, if two of three children were created before interruption, the retry
reuses those two and creates only the third. A child that is already closed or has
human edits is preserved. Missing links or labels are repaired against the current
item, rather than regenerating its original description or resetting bounce history.

If creation timed out, its pending intent remains until the outcome is established.
The skill searches for the exact key, including unlinked and closed items. If it
cannot find the item, it stops for reconciliation; search absence alone does not
prove that another create is safe. Run only one decomposition session per parent
unless the tracker supplies safe concurrent idempotency.

Duplicate keys, conflicting saved plans, and legacy or older-revision children
require explicit review. Record which old items should be retained separately,
superseded, or adopted after scope/provenance reconciliation. The skill never deletes
or reopens them automatically. A revised brief does not justify silently recreating
unfinished work from an older revision.

## Make more work delegable

Decomposition actively resolves delegation blockers: it links missing context,
uses established conventions, obtains necessary human decisions, and identifies
acceptance checks. It keeps the largest coherent units that can be independently
verified. Sensitive work stays separately classified when a real boundary allows it.

For example, an internal formatting feature can become V2 B2 C2 A1 after its output
behavior is agreed, an acceptance check exists, and local conventions are linked.
The agent may choose a private helper name and file structure within those conventions.
It must stop before introducing a new dependency or changing the agreed behavior.

If the acceptance check still needs to be built, that is a prerequisite with its own
tier. The feature stays at its current tier and blocked until the check exists and
reclassification confirms eligibility. A promised prerequisite does not raise scores.
Material changes to the approved brief return to grooming and approval. Splitting a
sensitive change into smaller pieces does not itself reduce its blast radius.

## Understand the classification

Each axis ranges from 0 to 2; higher means more delegable.

| Axis | What it measures |
|---|---|
| V — verifiability | Whether a single machine-runnable command can fully verify completion. |
| B — blast radius | How isolated and reversible a failure would be. |
| C — context locality | Whether a cold session can retrieve all required context. |
| A — ambiguity residue | Whether implementation decisions remain. |

The [schema's ordered derivation rules](../skills/setup-ai-first/assets/ai-first-schema.md#3-classification-rubric) determine the tier. Key constraints:

- Hard overrides, including the parent's human-only list, take precedence.
- Two or more final zero scores require human-only. B = 0 and V < 2 prohibit delegation without weakening human-only outcomes. Capabilities never raise B.
- Delegate requires V=2, B=2, C=2, A>=1 and a real, single `verify` command that checks completion and returns a boolean exit status. A=1 allows bounded naming/structure choices within linked conventions and explicit stop conditions; A=2 is mechanical.
- Enabled, proven capabilities can raise V, C, or A by at most one point per axis in total, only for matching task classes. Provisional or unapproved claims do not change scores.

## Review the generated items

Each child should contain a summary, acceptance criteria, source context links, and the task schema block. Check its `tier`, `raw-scores`, final `scores`, `capability-deltas`, `classes`, `rationale`, `bounce`, `manifest`, and `capability-sources`; delegate/pair items also identify an execution `profile`.

A delegate item must include a usable `verify` command and at least one `stop-ask` condition. Confirm the command checks the actual outcome and that a new session can understand the item from its linked context. For registry-backed checks, confirm `verify-id` selects a reviewed command with demonstrated acceptance coverage. Retain the task snapshot and the runner result so the reviewer can match the evidence to the tested code and requirements. Each item must carry exactly one of `ai-delegate`, `ai-pair`, or `human-only`, matching its block.

Classification creates execution contracts. Run implementation and verification next, and record the tested commit, command, result, and task link in the PR for human review. CI and automatic merge blocking are optional and do not affect delegation eligibility. See [optional PR verification](pr-verification.md) for GitHub and Azure DevOps templates.

## Classify a small item directly

```text
$decompose-and-classify #124 in single-item mode
Destination: Correct the misspelled heading in the internal help page.
Definition of done: The heading matches the approved copy and the existing
page-content check passes using <actual verification command>.
```

Explicit single-item mode applies to an unclassified small item. It asks for destination and definition of done, establishes a bounded scope, then classifies that item itself without the normal parent guards or child creation. An existing task goes to reclassification; a brief goes to normal decomposition. It explicitly records why skipping the brief approval gate is acceptable for this small, low-blast-radius change. It refuses when B = 0. `single-task mode` is a supported alias. Using this mode does not guarantee a delegate tier.

## Reclassify after a failed verification cycle

```text
$decompose-and-classify #125 in reclassify mode
The verification cycle failed. Here is the command, output, and failure history:
<paste relevant failure details>
```

The skill selects reclassification before normal parent-approval guards and updates
only the existing task. It can record a failure even when parent approval is absent
or revoked; that does not authorize further execution. It still needs the parent's
human-only restrictions to justify an upgrade. Missing restrictions preserve the
existing tier or a stricter bounce cap while the missing context is resolved.

Give each failed verification cycle a stable ID and evidence: CI provider/pipeline,
run ID and attempt, or a local UUID saved with the command, tested commit, task
snapshot, and output. Re-report the same ID on retries. One failing run is one cycle,
not one cycle per failed assertion. Passes, cancellations, and routine reclassification
do not increment or reset the count.

The item records `failed-cycles` alongside `bounce`. A new failed ID increments
once; duplicates do not. At **bounce >= 2**, the item cannot delegate: pair is the
maximum, and any hard override, two-zero result, or stricter human-only challenge
remains human-only. Keep `ai-escalated` at and above the threshold. Profiles follow
the final tier, with no profile for human-only.

A human can request a stricter tier or provide evidence for re-scoring. Editing the
tier cannot waive hard restrictions, absent verification, or the bounce cap. A
successful later run alone does not restore delegation.

For legacy items with bounce zero, initialize an empty ledger. For nonzero counts,
reconstruct cycle IDs from failure evidence first. If the history is incomplete,
preserve the count and existing cap and ask for reconciliation; never reset it or
invent past failures. Repeated comments use the same cycle ID, and concurrent/partial
writes must be reconciled against the current item state.

## Troubleshoot

| Situation | Next step |
|---|---|
| Missing or unauthorized self-approval | Obtain independent approval, or use setup to configure your verified solo identity and manually approve. Every tracker requires the label and exact revision/digest approval comment in both modes. |
| Open decisions remain | Resolve them in the brief and keep its count accurate before retrying. |
| Schema is malformed | Repair the rule named in the `[ai-first] SCHEMA:` comment. Use the active adapter's storage format, including Linear's fenced block. |
| No valid verification command exists | Accept a non-delegate classification or improve verification before reclassifying. |
| Capability manifest is malformed | Classification continues on raw scores; repair the manifest through [capability review](update-ai-first-capabilities.md). |
| Discovered metadata is ignored | Check the parent summary for malformed, conflicting, mismatched, or unapproved claims; review central approval. |

Source: [decompose-and-classify/SKILL.md](../skills/decompose-and-classify/SKILL.md).
