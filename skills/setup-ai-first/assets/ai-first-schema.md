# AI-First Workflow Schema (v1)

The shared contract between the `groom` skill, the `decompose-and-classify` skill, PR validation, and any tracker-specific enforcement integration. Every consumer reads and writes the same structures. Version bumps to the sentinel (`[ai-first:v2]`) require updating every consumer.

## 1. Tags (visible layer, filterable)

| Tag | Applied to | Applied by | Meaning |
|---|---|---|---|
| `ai-first` | Regular/large item | `groom` | Item is managed by this workflow |
| `groomed` | Regular item | `groom` | Brief exists in the item |
| `brief-approved` | Regular item | Human (manually) | Gate 1 passed. MUST NOT be applied by any skill |
| `ai-delegate` | Small execution item | `decompose-and-classify` | Delegate tier |
| `ai-pair` | Small execution item | `decompose-and-classify` | Pair tier |
| `human-only` | Small execution item | `decompose-and-classify` | Human-only tier |
| `ai-escalated` | Small execution item | Skill or enforcement integration | Tier was auto-downgraded after bounces |

Rules:
- A small execution item carries exactly one tier tag. Consumers treat multiple tier tags as a schema violation.
- Tags are flags only. Never encode data in tag names.
- Approval identity is not stored in the description block. It is derived using the active tracker adapter's auditable history mechanism. Consumers MUST verify that the identity which granted `brief-approved` differs from the item creator.
- Display names for large, regular, and small items come from `.ai-first/terminology.md`. These names do not change schema keys or classification semantics.

## 2. Description block (data layer, machine-parsable)

A fenced block at the END of the work item description. Plain visible text, no HTML comments (ADO sanitizer is unreliable with them). Everything after the closing fence is ignored; everything before it is the human-authored description.

### 2.1 On the regular parent item (written by `groom`)

```
---
[ai-first:v1]
kind: brief
brief-url: <link to wiki page or "inline">
groomed-on: 2026-08-03
open-decisions: 0
---
```

If `brief-url: inline`, the groomed brief is the description content above the block.
`open-decisions` counts unresolved judgment calls surfaced during grooming. Decomposition MUST refuse when > 0.

### 2.2 On each small execution item (written by `decompose-and-classify`)

```
---
[ai-first:v1]
kind: task
tier: delegate | pair | human-only
verify: <single machine-runnable command, required when tier=delegate>
classes: <comma-separated stable task-class slugs>
scores: V2 B0 C2 A0
profile: bulk-mechanical | deep-planning | triage    <execution profile, delegate/pair only>
manifest: 2026.09                                    <capability manifest version used>
capability-sources: ai-first-capabilities/v2@2026.09  <plus applied metadata id@version values>
rationale: <one line, human-readable>
bounce: 0
context: <comma-separated links or IDs: ADRs, specs, related items>
stop-ask: <semicolon-separated conditions under which an agent must halt>
---
```

Field rules:
- `kind: task` is the stable machine value for every small execution item. It does not change when the team configures another display term such as Sub-issue or Sub-task.
- `tier` must match the tier tag on the item. Mismatch = schema violation.
- `verify` is REQUIRED when `tier: delegate` and must be a single command with a boolean exit code (e.g. `dotnet test --filter Category=Checkout`). If no such command exists, the execution item is not Delegate by definition (see rubric).
- `classes` records one or more narrow, stable task-class slugs used to match
  capability `covers` entries. Classification must not invent a broader class to
  make a capability apply.
- `scores` records the four classification axes (section 3) for auditability: V=verifiability, B=blast radius, C=context locality, A=ambiguity, each 0-2. Record them POST-manifest (final values), and name any applied capability effect in `rationale`.
- `profile` names an execution profile from `ai-first-capabilities.yml`, never a model name. Model names churn far faster than work items live; the indirection means a model upgrade is a one-line manifest edit rather than a mass rewrite of historical items.
- `manifest` records the capability manifest version in force at classification time. Without it, retro data is uninterpretable across tooling changes: you cannot tell whether tier accuracy moved because the rubric improved or because the toolset did. Cheap to record now, impossible to reconstruct later.
- `capability-sources` records the central manifest schema/version and every
  custom-skill metadata `id@version` whose effect was applied. When none was
  applied, record only the central manifest source. This makes discovered claims
  auditable without treating discovery as approval.
- `bounce` is incremented by the skill on every failed verification cycle. At 2, tier is rewritten to `pair`, tags are swapped, `ai-escalated` is added, and a comment explains why.
- `stop-ask` is the agent's halt list. An executing agent MUST stop and ask a human when any condition is met, instead of improvising.

### 2.3 Parsing rules (all consumers)

- Locate the LAST occurrence of a line equal to `[ai-first:v1]` preceded by `---` and followed by `key: value` lines until a closing `---`.
- Unknown keys are ignored (forward compatibility). Missing required keys are a schema violation.
- The block is human-editable BY DESIGN. Devs challenge a tier by editing `tier:` and the tag, then commenting why. Consumers therefore treat the block as intent and validate schema on every read; the plugin comments on malformed blocks rather than assuming they parse (see plugin spec).
- Edit history of the block IS the audit trail. No separate log.

## 3. Classification rubric

Score each axis 0-2. Higher = more delegable.

| Axis | 0 | 1 | 2 |
|---|---|---|---|
| **V** Verifiability | Success is a judgment call | Partially checkable (some tests, manual steps remain) | Fully machine-checkable with one command |
| **B** Blast radius (inverted: 2 = small) | Auth, payments, data migration, public API contract, security config | Internal behavior with cross-team consumers | Isolated, reversible, behind tests or flags |
| **C** Context locality | Requires knowledge outside repo/docs (heads, Slack, stakeholder preference) | Mostly in repo, minor external context that can be linked | Everything needed is in repo + linked docs |
| **A** Ambiguity residue (inverted: 2 = none) | Open judgment calls remain after grooming | Minor naming/structure decisions | Mechanical transformation, no decisions |

### Capability adjustment (between scoring and derivation)

Score the execution item on its raw properties FIRST, as if the team had no tooling.
Then read `ai-first-capabilities.yml`, scan the project-local custom-skill metadata
roots it declares, and apply effects subject to invariants C1-C10 in the manifest.
Inline entries must be enabled and proven. Discovered `ai-first-capability.yml`
metadata must additionally have an exact enabled, proven central approval for its
ID and version. Effects apply only where a task class matches `covers`; at most +1
per axis applies in total; and **no entry may ever raise B**.

This ordering is deliberate. Raw-first scoring keeps the rubric stable as tooling changes: the rubric never evolves, only the scores do. Better models, new skills, new MCPs, and custom agents change what the team can currently do (mostly C and A, occasionally V), not what the axes mean.

### Derivation (apply in order, first match wins)

1. **Hard overrides to `human-only`**, regardless of scores: secrets/credentials handling, production data migration without rollback, legal/compliance text, anything on the parent brief's explicit human-only list.
2. **B = 0 caps the tier at `pair`.** High blast radius never delegates, even fully verified.
3. **V < 2 means the execution item CANNOT be `delegate`.** This is the fixed-value poka-yoke: if the classifier cannot produce a `verify` command, it must not emit `tier: delegate`. Absence of the command IS the classification signal. Downgrade to `pair` automatically and say so in `rationale`.
4. **All four axes = 2** (V2 B2 C2 A2, after overrides) -> `delegate`.
5. **Sum >= 5 with no zero** -> `pair`.
6. **Any other combination** -> `human-only` for two or more zeros, otherwise `pair`.

## 4. Comment conventions (plugin + skills)

Machine-posted comments are prefixed so they are filterable and never mistaken for human discussion:

- `[ai-first] BLOCKED:` precondition failure, includes the exact remediation step
- `[ai-first] ESCALATED:` bounce threshold reached, tier downgraded
- `[ai-first] SCHEMA:` malformed block detected, includes the failing rule
- `[ai-first] REVERTED:` plugin moved state back (see plugin spec)

## 5. Invariants (the three hard poka-yoke points)

1. No decomposition without `brief-approved` on the parent, applied by someone other than the requester.
2. No small execution item enters Active without exactly one tier tag and a schema-valid block.
3. No `delegate` execution item without a `verify` command, and the PR pipeline executes that command as a merge precondition.

Everything else in the workflow is soft (detection or convention).
