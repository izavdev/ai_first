# How to decompose and classify work

Use this skill to turn an approved brief into small execution items with delegation tiers and verification contracts. It also supports direct classification of small items and reclassification of existing items.

## Before you start

Run [setup-ai-first](setup-ai-first.md). All six `.ai-first/` contract files must exist. Have tracker access and links to the relevant specs, ADRs, contracts, and repository context.

For normal decomposition, the parent must have `groomed` and `brief-approved`, attributable human approval satisfying the project policy (independent or configured solo self-approval), a valid brief schema block, and zero open decisions. Follow the [grooming guide](groom.md) to satisfy those requirements.

## Decompose an approved brief

```text
$decompose-and-classify #123
Decompose the approved brief into small execution items with dependency links.
```

1. The skill checks the parent labels, approval identity, schema, and open decisions. A failed guard produces a comment with remediation and stops decomposition.
2. It splits work into one verifiable outcome per item, links source context, orders dependencies, and carries down the parent's human-only restrictions.
3. It scores each item's raw properties using the project schema, then reads the capability manifest and applicable approved metadata.
4. It creates linked children, applies exactly one tier label to each, and posts a parent summary with tiers and rationales.

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
- B = 0 caps the tier at pair. Capabilities never raise B.
- Delegate requires all four final scores to be 2 and a real, single `verify` command with a boolean exit code.
- Enabled, proven capabilities can raise V, C, or A by at most one point per axis in total, only for matching task classes. Provisional or unapproved claims do not change scores.

## Review the generated items

Each child should contain a summary, acceptance criteria, source context links, and the task schema block. Check its `tier`, final `scores`, `classes`, `rationale`, `bounce`, `manifest`, and `capability-sources`; delegate/pair items also identify an execution `profile`.

A delegate item must include a usable `verify` command and at least one `stop-ask` condition. Confirm the command checks the actual outcome and that a new session can understand the item from its linked context. Each item must carry exactly one of `ai-delegate`, `ai-pair`, or `human-only`, matching its block.

Classification creates execution contracts. Run implementation and verification as the next stage of your delivery process; configure PR enforcement separately if required.

## Classify a small item directly

```text
$decompose-and-classify #124 in single-item mode
Destination: Correct the misspelled heading in the internal help page.
Definition of done: The heading matches the approved copy and the existing
page-content check passes using <actual verification command>.
```

This path asks only for destination and definition of done, then classifies the item itself. It explicitly records why skipping the brief approval gate is acceptable for this small, low-blast-radius change. It refuses when B = 0. `single-task mode` is a supported alias. Using this mode does not guarantee a delegate tier.

## Reclassify after a failed verification cycle

```text
$decompose-and-classify #125 in reclassify mode
The verification cycle failed. Here is the command, output, and failure history:
<paste relevant failure details>
```

The skill re-scores the current item and increments `bounce` when reclassification follows a failed verification cycle. At `bounce: 2`, it must set `tier: pair`, swap the tier label, add `ai-escalated`, and post the failure history in an escalation comment.

To challenge a tier manually, a human can edit both the `tier` field and matching label, then comment with the reason. Reclassification respects that override unless a new bounce forces escalation.

## Troubleshoot

| Situation | Next step |
|---|---|
| Missing or unauthorized self-approval | Obtain independent approval, or use setup to configure your verified solo identity and manually approve. Linear requires the label and approval comment in both modes. |
| Open decisions remain | Resolve them in the brief and keep its count accurate before retrying. |
| Schema is malformed | Repair the rule named in the `[ai-first] SCHEMA:` comment. Use the active adapter's storage format, including Linear's fenced block. |
| No valid verification command exists | Accept a non-delegate classification or improve verification before reclassifying. |
| Capability manifest is malformed | Classification continues on raw scores; repair the manifest through [capability review](update-ai-first-capabilities.md). |
| Discovered metadata is ignored | Check the parent summary for malformed, conflicting, mismatched, or unapproved claims; review central approval. |

Source: [decompose-and-classify/SKILL.md](../skills/decompose-and-classify/SKILL.md).
