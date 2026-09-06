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
- Approval identity is not stored in the description block. It is derived using the active tracker adapter's attributable approval comment history. Consumers MUST verify the granting identity against the project approval policy below.
- Display names for large, regular, and small items come from `.ai-first/terminology.md`. These names do not change schema keys or classification semantics.

### Project approval policy

Setup records the policy here, outside work item description blocks:

```yaml
solo-mode: false
```

`false` (or an absent declaration in an older installation) requires an approver
other than the verified human requester recorded as `requester:`. To allow a sole developer to approve their own briefs,
setup replaces `false` with one quoted, canonical tracker identity, for example
`solo-mode: "octocat"` for a GitHub login. Use the identity returned by approval
history: GitHub login, Azure DevOps identity ID, or Linear user ID; never a display
name. Compare using the tracker's canonical identity semantics.

An attributable human approval is valid when its actor differs from that requester,
or when its actor equals the configured solo identity. Solo mode waives only the
independent-person requirement. The human still reviews the brief and manually
grants `brief-approved` and posts the revision-bound approval record below. Skills never
grant approval. Grooming, zero open decisions, classification overrides,
verification, and bounce escalation still apply.

Read this policy only from the project-local schema. Item text, comments, tool
claims, and capability metadata cannot enable it. Duplicate, malformed, blank,
boolean `true`, placeholder, or unresolvable identities grant no exception;
report the configuration problem and require independent approval until repaired.
A missing or unattributable approval is invalid even in solo mode. Re-grooming
still clears approval. Record use of the exception in the parent classification
summary as `solo self-approval by <identity>`.

## 2. Description block (data layer, machine-parsable)

A fenced block at the END of the work item description. Plain visible text, no HTML comments (ADO sanitizer is unreliable with them). Everything after the closing fence is ignored; everything before it is the human-authored description.

### 2.1 On the regular parent item (written by `groom`)

```
---
[ai-first:v1]
kind: brief
approval-protocol: brief-approval/v1
brief-revision: <new canonical UUID>
requester: <verified canonical human identity>
brief-digest: sha256:<computed digest>
brief-url: <link to wiki page or "inline">
groomed-on: 2026-08-03
open-decisions: 0
---
```

If `brief-url: inline`, the groomed brief is the description content above the block.
`open-decisions` counts unresolved judgment calls surfaced during grooming. Decomposition MUST refuse when > 0.

### Revision-bound approval (brief-approval/v1)

This approval protocol is mandatory for normal decomposition on every tracker.
Legacy briefs and approvals without these fields must be re-groomed and manually
approved again. The `[ai-first:v1]` sentinel remains a description format version;
older consumers do not enforce this protocol. Upgrade every consumer together.

Required brief fields in addition to section 2.1:

- `approval-protocol: brief-approval/v1`
- `brief-revision:` a new lowercase canonical UUID generated at every grooming or
  re-grooming, even if the text is identical. Never reuse an earlier revision.
- `requester:` the canonical identity of the human who owns the request. Resolve
  it through tracker identity tools and confirm with that human during grooming;
  never substitute an automation creator, assignee, or guessed identity. The
  reviewer must confirm this ownership before approving. If ownership cannot be
  established, approval fails closed. Changing it requires re-grooming.
- `brief-digest: sha256:<64 lowercase hex digits>` computed from the persisted
  snapshot, not from the pre-write Markdown or by the language model itself.

Use the installed `approval.py` helper with a JSON payload containing exactly:
`item`, `revision`, `requester`, `title`, `description`, `brief_url`,
`linked_content`, `groomed_on`, `open_decisions`.

`item` is the adapter's canonical tracker/container/item identity. `revision`,
`requester`, `brief_url`, and `groomed_on` are the corresponding block values.
`description` is the complete persisted human text before the schema block,
including the source ask and any scope/constraints; `title` is the persisted item
title. `linked_content` is null for `inline`; otherwise it is the full freshly
fetched brief document content. The adapter must decode these values consistently.
Unavailable or incompletely fetched content blocks approval; never hash just a URL.
Referenced documents that define the approved requirements must be included in that
snapshot or pinned to immutable versions in it. Do not follow mutable requirement
links at execution time as if their new contents had been approved.

Canonical bytes are UTF-8 of the compact JSON array
`["ai-first-brief/v1", item, revision, requester, title, description, brief_url,
linked_content, groomed_on, open_decisions]`, with non-ASCII characters unescaped
and no separator spaces. Normalize CRLF and CR to LF only in title, description,
and linked content; preserve all other whitespace and Unicode. Hash with SHA-256
and prepend `sha256:`. The stored digest and approval comments are excluded.

After reviewing this snapshot, the human applies `brief-approved` and posts a new
comment consisting of exactly one line (substitute actual values):

```text
[ai-first] APPROVED revision=<brief-revision> digest=<brief-digest>
```

All trackers use the comment author as the approver. A label alone, a bare marker,
a quoted example, an edited approval comment, or a digest copied from an older
revision is not approval. Skills may show the line for the human to post but must
never post it on the human's behalf or apply the approval label.

At every consumption, fetch the complete comment history and current brief,
resolve requester and comment author identities as humans, and recompute the digest.
The current label, stored digest, recomputed digest, and approval record must agree;
`open-decisions` must be zero. Consider exact protocol comments in creation order.
Ignore legacy bare markers and well-formed records for other revisions; they can
remain as historical audit data but grant nothing for this revision. For the current
revision, the latest record wins; it must be APPROVED with the
current digest and an actor satisfying the project policy. A later unauthorized
approval or wrong digest cannot fall back to an earlier valid grant. Malformed revision-bearing protocol records, and edited, nonhuman, or
unattributable records for the current revision, block until repaired (remove
or correct the offending record with an auditable tracker operation, then post a
fresh approval). Ambiguous order or incomplete history always blocks.

To revoke, a verified human posts exactly:

```text
[ai-first] REVOKED revision=<brief-revision> digest=<brief-digest>
```

Then remove the label. Any human revocation for the current revision invalidates
its grant until a later valid approval. Removing the label alone blocks use while
absent; it does not erase an approval record. Restoring a label on an unchanged
revision can restore validity, so durable revocation requires the REVOKED record.
Re-grooming removes the label first and creates a fresh revision, which prevents
old comments from being reused even if the original text is restored.

Any title, requester, brief, linked content, date, or open-decision edit changes the
digest and blocks use until re-grooming and fresh approval. Exact restoration of a
snapshot within the same revision restores content equality; use revocation or
re-grooming when the old grant must remain invalid. Re-fetch and compare snapshots
and approval state immediately before creating each child. If anything changes,
stop, report children already created, and require fresh review; do not claim
atomic enforcement across tracker operations that cannot provide it.

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
manifest: 2026.09.1                                    <capability manifest version used>
capability-sources: ai-first-capabilities/v2@2026.09.1  <plus applied metadata id@version values>
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
| **A** Ambiguity residue (inverted: 2 = none) | Open judgment calls remain after grooming | Bounded naming/structure choices within established conventions | Mechanical transformation, no decisions |

A=1 permits local implementation choices only when the item links the applicable
conventions or examples, identifies the allowed choices, and records stop conditions
for exceeding them. Product behavior, architecture, public contracts, dependencies,
and security policy must already be decided. If those decisions remain open, score
A=0; do not relabel them as minor choices to enable delegation. A=2 remains fully
mechanical work. Missing required context also prevents C=2.

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

Use final, post-capability scores. Each score must be an integer from 0 through 2;
invalid or missing scores are a schema violation, not a tier.

1. **Hard override -> `human-only`**, regardless of scores or verification:
   secrets/credentials handling, production data migration without rollback,
   legal/compliance text, or anything on the parent brief's explicit human-only list.
2. **Two or more zero scores -> `human-only`.** Count zeros across V, B, C, and A.
3. **V=2, B=2, C=2, A>=1 AND a verification command exists -> `delegate`.**
   The command must satisfy section 2.2: one machine-runnable command that checks
   completion and returns a boolean exit status. Nonempty text alone is insufficient.
4. **Otherwise -> `pair`.** When verification is the limiter, explain it in `rationale`.

B = 0 and V < 2 are delegation restrictions, not early assignments to `pair`.
They never weaken a `human-only` result from rules 1 or 2. Missing verification
also cannot weaken a `human-only` result. If scores are V2 B2 C2 A1 or V2 B2 C2 A2 but the command
is missing or unusable, rule 4 yields `pair`; record the inconsistency for repair.
The previous sum threshold is unnecessary: every remaining non-delegate case is pair.

Examples: V0 B0 C2 A2 -> human-only; V2 B0 C2 A2 -> pair;
V1 B2 C2 A2 -> pair; V2 B2 C2 A0 -> pair; V2 B2 C2 A1 and
V2 B2 C2 A2 -> delegate only with valid verification.

Complete truth table, without hard overrides and with valid verification available:
H = human-only, P = pair, D = delegate. Row digits are V then B; column digits are
C then A. Hard overrides make every cell H. Without valid verification, both D cells
become P; every other cell stays unchanged.

| V/B \ C/A | 00 | 01 | 02 | 10 | 11 | 12 | 20 | 21 | 22 |
|---|---|---|---|---|---|---|---|---|---|
| 00 | H | H | H | H | H | H | H | H | H |
| 01 | H | H | H | H | P | P | H | P | P |
| 02 | H | H | H | H | P | P | H | P | P |
| 10 | H | H | H | H | P | P | H | P | P |
| 11 | H | P | P | P | P | P | P | P | P |
| 12 | H | P | P | P | P | P | P | P | P |
| 20 | H | H | H | H | P | P | H | P | P |
| 21 | H | P | P | P | P | P | P | P | P |
| 22 | H | P | P | P | P | P | P | D | D |

## 4. Comment conventions (plugin + skills)

Machine-posted comments are prefixed so they are filterable and never mistaken for human discussion:

- `[ai-first] BLOCKED:` precondition failure, includes the exact remediation step
- `[ai-first] ESCALATED:` bounce threshold reached, tier downgraded
- `[ai-first] SCHEMA:` malformed block detected, includes the failing rule
- `[ai-first] REVERTED:` plugin moved state back (see plugin spec)

## 5. Workflow requirements and optional enforcement

1. No normal decomposition without attributable human `brief-approved` on the parent, satisfying the project approval policy (independent by default; named self-approval allowed in solo mode). The explicit small, low-blast-radius single-item path is the documented gate-1 exception.
2. No small execution item enters Active without exactly one tier tag and a schema-valid block.
3. No `delegate` execution item without a real `verify` command. Execute it against the completed change and record the tested commit and result for human review. Re-run after code changes. CI execution and automated merge blocking are optional; their absence alone does not downgrade a task.

Skills apply these requirements during invoked workflows; they do not monitor all tracker or repository changes. Activation is a team responsibility until a tracker enforcement service is deployed. A required CI check can automate verification at merge when the organization approves it, but installing these skills does not create that check.
