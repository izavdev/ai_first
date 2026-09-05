# How to update AI-first capabilities

Use this skill to maintain the project-owned capability manifest or describe a custom skill's classification effects. Registration is an evidence review; it does not install, authenticate, or run the candidate integration.

## Before you start

Run [setup-ai-first](setup-ai-first.md). The workflow requires `.ai-first/README.md`, `ai-first-capabilities.yml`, and `capabilities-guide.md`.

Bring the capability's source or documentation, stable ID and version, exact task classes it supports, owner, prerequisites, limitations, and available telemetry. For a validator, provide its actual command, exit-code behavior, coverage, and representative output.

## Choose an operation

Register or revise an inline capability:

```text
$update-ai-first-capabilities
Review our inventory CSV validator for registration in the project manifest.
Its configuration is at <path>, and its command is <actual command>.
Proposed coverage: inventory-csv-export.
```

Describe a custom skill:

```text
$update-ai-first-capabilities
Read <path-to-skill>/SKILL.md and prepare ai-first-capability.yml beside it.
Review its claimed context-retrieval effect for inventory-csv-export.
```

Review central approval or status:

```text
$update-ai-first-capabilities
Review the discovered metadata for <capability-id>@<version> for project approval.
Telemetry is at <evidence-link-or-path>.
```

You can also explicitly request disabling an entry, promoting or demoting it, reconciling metadata, changing discovery roots, or changing execution profiles.

## Review the evidence and proposed effect

1. The skill reads the complete manifest and the strongest available capability source before asking questions.
2. Answer remaining questions about scope, permissions, availability, failure modes, and evidence. Unverified claims remain identified as claims.
3. Review whether the capability actually changes a classification axis for the proposed task classes.
4. Review the exact YAML change, checked evidence, unresolved claims, and expected effect. Confirm the proposed write when prompted.
5. Check the validation result and the report of enabled, provisional, and score-changing entries.

| Effect | Required justification |
|---|---|
| V +1 | A validator supplies the task's single machine-runnable verification command with a boolean exit code. |
| C +1 | Otherwise-missing context becomes reliably retrievable, project-scoped, and usable by a cold session. |
| A +1 | An approved house approach removes an actual implementation decision. |
| B | No effect is allowed; tooling does not reduce the consequences of failure. |

Coverage should use narrow, stable task classes. An entry can claim at most +1 per permitted axis, and combined entries cannot raise an axis by more than one point for a task.

## Distinguish registration from proven status

New or materially changed capabilities start `provisional`, even when registration is approved. They do not affect classification.

Promotion to `proven` requires recorded telemetry for **at least 10 merged delegate tasks in every approved covered class, with zero escalations**. Documentation or successful demos do not replace that evidence. An escalation rate above 20% over the last 20 covered tasks triggers a demotion recommendation under manifest invariant C6.

Custom skill metadata remains a claim until the central manifest contains an enabled, proven approval for its exact ID and version. Central approval may narrow the metadata's coverage or effects, but cannot expand them. Self-declared `enabled`, `status`, or `evidence` metadata fields do not grant authority.

## Check the result

Central edits update `.ai-first/ai-first-capabilities.yml` and bump its `version`, preserving comments and unrelated entries. Custom skill metadata is written as `ai-first-capability.yml` beside `SKILL.md`, using the [shipped template](../skills/update-ai-first-capabilities/assets/ai-first-capability.template.yml).

Validation checks YAML parsing, unique IDs within each central list, allowed kinds and axes, integer effects from 0 to 1, exact metadata approval matches, bounded approval scope, and evidence for every proven entry. The final report should say whether any entry can now affect classification and which metadata still awaits approval.

## Troubleshoot

| Situation | Next step |
|---|---|
| Tool is installed but has no classification effect | Review project registration and status; installation alone grants no approval. |
| No qualifying telemetry exists | Keep the entry provisional while collecting evidence. |
| Custom skill version changed | Review that exact version and its central approval; an old version's approval does not transfer. |
| Claimed effect conflicts with the implementation | Resolve the discrepancy before accepting the proposed change. |
| You want a live evaluation | Request it separately and authorize its effects; evidence review does not execute the candidate. |

Next: use [decompose-and-classify](decompose-and-classify.md) to classify work against the updated manifest. Source: [update-ai-first-capabilities/SKILL.md](../skills/update-ai-first-capabilities/SKILL.md).
