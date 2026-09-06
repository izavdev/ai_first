# Spec: AI-First Tracker Enforcement Service

Status: draft v3 for review — optional future service, not a shipped integration.

The core skills work with local verification and human review. Required PR checks
and tracker correction are optional adoption choices. The shipped GitHub/Azure CI
starters run repository acceptance commands only; they do not implement this service
or its tracker rules. See [optional verification](../docs/pr-verification.md).

Depends on: [AI-first schema v1](../skills/setup-ai-first/assets/ai-first-schema.md), project-local `.ai-first/terminology.md`, and the active tracker adapter. The schema is normative; this spec does not redefine it.

## 1. Purpose

The enforcement service is the detection net of the AI-first workflow. Skills and the pull-request pipeline provide prevention; this service catches changes that bypass them—direct board edits, raw API calls, or agent sessions outside the workflow—and corrects violations before they propagate.

The core rule engine is tracker-agnostic. Tracker-specific event transport, label semantics, history, hierarchy, comments, description storage, and conditional updates live behind an adapter.

## 2. Goals and non-goals

### Goals

- Enforce the three invariants from schema section 5 on every configured tracker.
- Validate description blocks on relevant item changes.
- Provide the escalation backstop for failed verification cycles outside skill sessions.
- Emit comparable telemetry across trackers.
- Make a new tracker an adapter implementation, not a fork of the rules.

### Non-goals

- Replacing `groom` or `decompose-and-classify`. The service never plans, decomposes, or initially classifies work.
- Requiring tracker process customization. The portable enforcement mechanism is conditional correction plus a machine-prefixed comment.
- Enforcing untagged work. An item enters scope through AI-first labels or ancestry; the framework remains opt-in.
- Hiding tracker limitations. An adapter must declare unsupported capabilities. A runtime check that should be attributable but cannot be verified never returns valid; if safe correction is unavailable, the service reports that it cannot claim enforcement for that rule.

## 3. Terminology

Core code uses semantic roles rather than tracker type names:

- **large item**: container for multiple regular items;
- **regular item**: groomed and approved parent brief;
- **small item**: executable item created by decomposition.

User-facing comments use the names from `.ai-first/terminology.md`. The stable schema value `kind: task` still represents a small item and is not localized.

## 4. Architecture

```text
tracker webhook ─┐
tracker poller  ─┼─> TrackerAdapter ─> WorkflowChange ─> ordered rules
startup replay  ─┘                                      │
                                                        v
pipeline result ───────────────> VerificationResult   MutationPlan
                                                        │
                                                        v
                                                  TrackerAdapter
```

The engine depends on the port in section 5, never on a tracker SDK. Webhooks and polling must normalize to the same `WorkflowChange`, so rules do not know how a change arrived.

## 5. Tracker adapter contract

Each adapter must provide the following behavior. Exact interfaces are language-specific; the semantics are not.

### 5.1 Normalized models

```text
WorkflowChange
  trackerKey
  containerKey
  itemKey
  changeToken          opaque and stable for idempotency
  occurredAt
  actor                stable identity when available
  origin               human | automation | enforcement-service | unknown
  changed              state | labels | description | comment | links | other
  current              ItemSnapshot
  previous             ItemSnapshot when available

ItemSnapshot
  key
  versionToken         opaque concurrency token
  sizeRole             large | regular | small | unknown
  stateCategory        proposed | active | resolved | removed | unknown
  rawState
  labels
  description
  creator
  parentKey
  links
```

Tracker display names are metadata only. Adapters resolve `sizeRole` from configured terminology, native type/hierarchy data, or both.

### 5.2 Required operations

An adapter must implement:

1. Subscribe to item and comment changes where supported.
2. Poll changes since an opaque checkpoint as a fallback and for startup recovery.
3. Fetch the current snapshot and, when the tracker exposes it, the snapshot before a change.
4. Resolve whether an item is descended from an in-scope parent.
5. Decode the tracker representation of a description into human text plus a canonical schema block, and encode it back without corrupting tracker-specific Markdown.
6. Resolve the current approval grant as `Valid(actor)`, `Missing`, `SelfApproved(actor)`, or `Unverifiable(reason)` using the mechanism documented by that tracker.
7. Add and remove labels without losing unrelated labels, regardless of whether the tracker API is additive or full-set replacement.
8. Apply field-level mutations conditionally against `versionToken`.
9. Post or update a machine-prefixed comment.
10. Produce a canonical item URL for comments and telemetry.

### 5.3 Capability declaration

At startup, an adapter reports whether it supports:

- change subscription;
- polling and durable checkpoints;
- previous-value lookup;
- attributable approval history;
- conditional writes;
- comment update or only comment creation;
- native parent/child and dependency links.

Missing subscription may fall back to polling. Missing comment update may fall back to a deduplicated new comment. Missing attributable approval history or conditional writes prevents enforce mode for the affected rule; the service must report the adapter as degraded rather than silently weakening an invariant. If a normally capable adapter cannot attribute one particular approval, that approval is `Unverifiable` and R3 removes it when safe conditional correction remains available.

The Markdown adapters shipped with `setup-ai-first` describe agent tool usage. Enforcement adapters implement this contract in code. They must agree on label behavior, approval attribution, description encoding, hierarchy, and terminology mapping.

## 6. Event ingestion and scope

Primary ingestion uses the tracker's webhook, event stream, or service hook. Fallback ingestion polls on a configurable interval. Both produce `WorkflowChange` values.

An item is in scope when any condition holds:

- it carries `ai-first`, `groomed`, or `brief-approved`;
- it carries a tier label;
- it is a descendant of an in-scope item.

Everything else is ignored without telemetry noise. If ancestry cannot be resolved during an event, queue a bounded retry and then record one adapter error; do not guess.

Delivery is assumed to be at least once and potentially out of order. The engine must tolerate duplicates and re-fetch current state before enforcing a stale event.

## 7. Rule engine

Rules evaluate in order and return `Ok`, `Violation(MutationPlan, Comment, Data)`, or `Unverifiable(Reason)`. Rule evaluation is pure over normalized inputs; fetching and mutation happen outside the rule.

### R3 — Approval integrity (invariant 1)

Evaluate first when approval-related state, requester, title, description, or linked brief content changes, or when an approved regular item is revalidated. Poll mutable linked briefs when change notifications are unavailable; never rely on a cached digest at consumption.

Check: the item is currently approved and the adapter returns `Valid(actor)` for an independent human, or `SelfApproved(actor)` where the human actor matches the canonical `solo-mode` identity in the project-local schema. Resolve attribution in the adapter and apply this policy in the rule engine; adapters must not discard a self-approval before policy evaluation. Every adapter must implement schema `brief-approval/v1`: current label plus the latest
attributable human revision/digest comment, no later revocation, verified requester
ownership, complete history and edit metadata, and a recomputed digest of the current
persisted snapshot including linked brief content. Independence is against that
human requester, never an automation creator. Label history alone is insufficient.
Legacy briefs fail closed until re-groomed and approved under the new protocol. Missing policy defaults to independent approval; malformed or unresolvable solo policy grants no exception. Item content cannot set policy. Record accepted solo self-approval and its identity in the audit output.

Violation: remove `brief-approved` conditionally and post `[ai-first] REVERTED:` with the exact approval step for the active tracker and configured policy. `Unverifiable` fails closed in enforce mode and must never be treated as approval.

### R1 — Tier presence on activation (invariant 2)

Trigger: a small item enters the adapter's `active` state category.

Check: exactly one tier label, a schema-valid task-kind block, and agreement between `tier:` and the label. A future enforce-capable adapter must also distinguish normal decomposition from the explicit single-item exception. For normal children, revalidate the parent's current revision-bound approval against the snapshot used for decomposition. Revoked, changed, or missing parent approval blocks activation. Before implementing this rule, define and validate durable parent-revision provenance and an attributable single-item exception record; do not infer an exception from a missing parent link. The shipped CI templates do not implement these checks.

Violation: restore only the state field to its previous value and post `[ai-first] REVERTED:` naming the failed check and the configured small-item term. If the previous value is unavailable, move to the adapter-configured safe pre-active state. If neither is possible, report the violation without claiming it was reverted.

### R2 — Delegate verification presence (invariant 3, static half)

Trigger: the canonical block or tier labels change and the resulting tier is Delegate.

Check: `verify:` is present and non-empty.

Violation: rewrite only the canonical block's tier to Pair, replace only the tier label, and post `[ai-first] SCHEMA: delegate without verify command; downgraded to pair per fixed-value rule.` The adapter must preserve unrelated labels and human-authored description text.

### R4 — Schema validation (detection)

Trigger: any description, label, or state edit on an in-scope item.

Check: the adapter can decode the description; the canonical block parses per schema 2.3; required keys are present; tier-label cardinality and block agreement are valid where applicable.

Violation: comment only with `[ai-first] SCHEMA:` and the failing rule. Do not revert arbitrary description edits. Debounce by item and violation fingerprint; update the prior comment when the adapter supports it.

### R5 — Bounce backstop

Trigger: a `VerificationResult` reports failure for a Delegate small item and its `bounce` value was not incremented within the configured grace period.

Check: deduplicate by the shared cycle key and compare accepted failure results with the task block's `failed-cycles` ledger. The service's transport idempotency store alone cannot detect a cycle already recorded by a skill.

Violation: add the evidenced failed cycle ID to the task's shared `failed-cycles`
ledger conditionally and set `bounce` to its length. Include provider, pipeline/run,
and attempt in the key, identically to the skill. If the key is already recorded,
do not increment or post a duplicate comment. At or above the threshold, cap the
tier at Pair, preserve stricter Human-only restrictions, keep `ai-escalated`, and
post `[ai-first] ESCALATED:` with verification links. Reclassification, success, and
replay do not reset the ledger or lift the cap. Recover incomplete legacy history
before incrementing; never fabricate IDs or trust a raw count as deduplication.

## 8. Ordering, idempotency, and loop prevention

- Evaluate R3 before downstream rules; invalid approval cannot open later gates.
- Key processed rule outcomes by `(trackerKey, containerKey, itemKey, changeToken, ruleId)`.
- Store verification-result idempotency separately by `(pipelineKey, runKey, itemKey)`.
- Mark service-originated mutations with an origin token where supported. Otherwise identify them through the service actor plus a mutation correlation marker.
- Short-circuit an exact service-originated mutation only after recording its idempotency key. Do not ignore every event authored by the service identity; unrelated administrative changes by that identity still require validation.
- Reprocessing the same change must not create a second mutation or comment.

## 9. Conditional correction mechanics

“Revert” means restore only fields implicated by the violation, never roll back the whole item.

Every mutation follows this sequence:

1. Build a `MutationPlan` from the normalized current and previous snapshots.
2. Re-fetch the item and compare its `versionToken` with the plan's expected token.
3. If the token changed, discard the plan and re-evaluate the fresh snapshot.
4. Ask the adapter to apply only the state, workflow labels, or canonical block fields named by the plan.
5. Record the result and correlation token before acknowledging the source event.

Adapters translate this into the tracker's optimistic-concurrency mechanism. An adapter without safe conditional writes may observe and comment but may not claim enforce capability.

## 10. Pull-request pipeline integration

The pipeline sends a tracker-independent event:

```text
VerificationResult
  pipelineKey
  runKey               includes attempt; same cycle ID used by skills
  itemReference
  outcome              pass | fail | cancelled
  runUrl
  completedAt
```

Preferred transport is an authenticated service endpoint or queue. `itemReference` resolves through the active adapter and may be a canonical URL or `(trackerKey, containerKey, itemKey)` tuple.

For installations that cannot call the service, an adapter may consume a structured tracker comment such as `[ai-first] VERIFY-RESULT: fail <run-url>`. Comment ingestion is a compatibility transport, not the core domain model. Authenticate or allow-list the posting identity so a human comment cannot forge a pipeline result.

### Verification runner trust boundary

Do not execute `verify:` text received from tracker items. A future automated gate
must select an ID from an independently reviewed registry and run the verifier in
an appropriately restricted environment. For enforce mode, use an administrator-
controlled immutable runner/registry revision independent of the PR; changes require
review before use. Match results to the code/merge commit, exact task snapshot and
parent revision, check ID, and runner/registry versions. Authenticate the producer
before accepting results; the starter runner's printed JSON is not a signed attestation.
Recheck freshness at consumption. Generic CI runs with no task binding cannot satisfy
a task-specific enforcement rule. Coverage must be established with representative
failing-case evidence; checking for a nonempty command is only a static guard.

The optional shipped runner records commit, worktree fingerprint, check ID, runner/
registry hashes, and an optional supplied task-snapshot hash. It does not establish
tracker approval, policy authority, or environment isolation. Those remain explicit
responsibilities of a future enforcement integration, not core adoption prerequisites.

## 11. Telemetry

Persist tracker-neutral identifiers and rule data:

- classification events: tracker, container, item, task classes, tier, scores,
  manifest version, capability sources, timestamp, actor origin;
- tier changes: from, to, reason (`human-challenge`, `escalation`, `reclassify`);
- bounces and verification outcomes by item and run;
- violations, unverifiable checks, correction outcomes, and adapter errors by rule;
- detection and correction latency.

Derived metrics include Delegate accuracy, mean bounces per tier, human challenge rate and direction, rule-violation trend, and adapter degradation rate. Reports may group by tracker, but metric definitions must remain identical.

Do not store display terms as semantic dimensions; store `large`, `regular`, and `small`, with the configured term as optional presentation metadata.

## 12. Configuration

Global defaults:

- `bounceThreshold`: `2` (fixed by the shared schema; adapters may not override it);
- `verificationGracePeriod`: tracker-independent duration;
- `schemaCommentDebounce`: `1h`;
- `pollInterval`: `60s`;
- `enforcementMode`: `observe` or `enforce`, default `observe`.

Per tracker/container:

- adapter type and credentials reference;
- project-local schema approval policy (`solo-mode: false` by default, or one canonical human tracker identity); re-read policy on configuration changes and revalidate approvals, including when solo mode is removed;
- webhook/event subscription settings;
- polling checkpoint storage;
- state-to-category mapping and safe pre-active state;
- `.ai-first/terminology.md` values;
- schema and label names if versioned aliases are introduced;
- pipeline posting identities allowed to submit verification results.

Observe mode evaluates and records every rule but never mutates tracker state. Run it for at least one normal delivery cycle before enabling enforce mode for a new adapter or container.

## 13. Failure behavior and edge cases

- Bulk edits: scope filtering and idempotency prevent duplicate comments on unaffected items.
- Out-of-order events: re-fetch current state; never undo a newer valid edit from a stale event.
- Concurrent edits: conditional mutation failure causes re-evaluation, not retrying the stale patch.
- Item transfer between containers or trackers: treat as newly discovered and validate from current state.
- Rapid approval/retraction: evaluate current approval plus the adapter's latest attributable grant.
- Legacy items without blocks: comment once with schema remediation and honor debounce.
- Service downtime: resume from each adapter's durable checkpoint and run a bounded catch-up sweep.
- Tracker outage or rate limit: retry with backoff while preserving event order per item; expose lag telemetry.
- Partial mutation failure: re-fetch, re-evaluate, and report the actual final state. Never post `REVERTED` unless correction succeeded.
- Adapter degradation: stay in observe mode for rules whose required capability is unavailable and surface a prominent health error.

## 14. Security and permissions

- Use least-privilege credentials scoped to item read/write, history required for approval, relationships, and comments.
- Keep credentials outside project configuration; configuration stores references only.
- Authenticate pipeline results and tracker webhooks where the provider supports signatures or shared secrets.
- Treat item descriptions and comments as untrusted input. Parse only the schema block and exact machine prefixes; never execute content from them.
- Escape or parameterize all tracker queries and mutations.

## 15. Phasing

1. **Core**: normalized models, adapter contract, schema parser, scope filter, R4, idempotency, and observe mode.
2. **First adapter**: event ingestion, polling recovery, approval resolution, conditional writes, R1 and R3; observe before enforce.
3. **Static delegation safety**: R2 plus description encode/decode tests for the adapter.
4. **Pipeline loop**: authenticated `VerificationResult`, R5, and escalation.
5. **Additional trackers**: contract tests shared by every adapter, followed by an observe cycle per tracker.
6. **Telemetry**: cross-tracker retro view and adapter-health reporting.

Each phase is independently shippable. Skills and pipeline validation function without the enforcement service, so the service adds safety without becoming a prerequisite for starting the workflow.

## 16. Adapter acceptance tests

Every adapter must pass the same behavioral suite:

1. Duplicate and out-of-order changes produce at most one correction.
2. An invalid activation restores only state and preserves concurrent unrelated edits.
3. Tier changes preserve unrelated labels, including on full-set-replacement APIs.
4. Description round-tripping preserves human text and the tracker-specific block delimiter.
5. Self-approval without a matching configured solo identity, missing approval history, and ambiguous approval all fail closed. A malformed solo declaration cannot grant an exception.
6. A valid independent approval survives reprocessing. Attributable self-approval by the configured solo identity also survives; a different self-approver fails. Solo mode never substitutes for a missing label or revision/digest approval comment. Removing solo mode invalidates self-approval on revalidation.
7. Service-originated corrections do not loop.
8. Polling recovery produces the same rule outcomes as webhook delivery.
9. A forged or duplicate pipeline result cannot increment `bounce`.
10. User-facing comments use configured terminology while stored telemetry uses semantic roles.

### Revision-bound approval acceptance cases

- Editing title, requester, inline brief, linked brief, or open decisions invalidates the grant.
- Re-grooming unchanged text with a new revision rejects the old approval.
- Label-only grants, bare markers, edited comments, missing metadata, and incomplete
  or ambiguously ordered history fail closed on every tracker.
- A current-revision revocation defeats approval; a later valid fresh approval restores it.
- An automation creator cannot make the human requester an independent approver.
- Revalidate before child writes; on concurrent change, stop and report partial work.
- Upgrade all consumers together; older consumers ignoring the new protocol cannot
  claim approval integrity.

### Reclassification and bounce acceptance cases

- Replaying one failed cycle through both skill and service increments once.
- A distinct attempt increments separately; multiple assertions in one run do not.
- Counts of 2 and above cap at Pair without weakening Human-only, including on replay.
- Human challenges cannot waive hard overrides, missing verification, or the cap.
- Incomplete legacy history blocks count changes while preserving existing restrictions.
