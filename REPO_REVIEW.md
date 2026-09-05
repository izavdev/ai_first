# Repository review

Reviewed 5 September 2026, against commit `9247e86`.

My assessment: this is a thoughtful workflow design and a useful skills package, but its claims of deterministic, mistake-proof enforcement run ahead of what the repository delivers. I would pilot it with an attentive team. I would not yet rely on it to enforce delegation or approval policy.

The central idea is worth pursuing: make an agent's assignment independently understandable, record why it is delegable, and define how completion will be checked. The next investment should be executable contracts and evidence from real usage. More policy prose or more tracker integrations would currently add less value.

## Scope and validation

I reviewed all four skills, their configuration and assets, the three tracker adapters, both plugin manifests and the Claude marketplace manifest, the usage guides, the whitepaper, and the enforcement specification. This was a local review; I did not install the package, mutate trackers, or verify current vendor APIs and installer compatibility.

Checks performed:

- All three JSON manifests parse; both plugin versions are `0.4.0`; declared skill paths exist.
- All six YAML files parse, including the capability template. All four skill front matter blocks parse and have names matching their directories and nonempty descriptions.
- An independent enumeration of all 81 possible V/B/C/A score combinations compared two plausible interpretations of the rubric; 31 classifications differ, excluding hard overrides.
- The tracked inventory contains no executable enforcement implementation, test suite, CI workflow, or license file. The local `src/` directory is empty. There was no application test command to run.

Parsing success is a packaging sanity check, not proof of host compatibility or workflow correctness. Findings below distinguish specification defects from risks in the proposed implementation.

## What works well

**The work item is the durable execution contract.** Requiring acceptance criteria, context links, scores, a rationale, verification, and stop conditions is practical. The cold-session requirement is especially strong: it exposes missing context before implementation starts. See [decomposition](skills/decompose-and-classify/SKILL.md#decomposition).

**Capability discovery does not grant authority.** Empty defaults, exact metadata ID/version approvals, conservative effects, and explicit distrust of embedded instructions form a coherent policy. The prohibition on raising blast-radius scores is a useful distinction between improving execution and reducing consequences. See [capability policy](skills/setup-ai-first/assets/ai-first-capabilities.yml).

**Packaging is small and understandable.** One shared skill tree serves multiple clients. Project-owned copies separate a team's configuration from installed package assets. The how-to guides supply usable prompts and troubleshooting without requiring the whitepaper first.

**The enforcement draft anticipates real operational problems.** Conditional field-level corrections, duplicate events, out-of-order delivery, degraded adapters, and authenticated pipeline results are all covered. This is a credible starting specification, although implementation and acceptance-test evidence remain future work. See [enforcement specification](assets_ai_first/plugin-workflow-spec.md).

## Findings

### 1. High — Tier derivation has conflicting control flow

**Addressed in the working tree:** the schema now uses terminal rules for hard overrides, two zero scores, verified V2 B2 C2 A>=1 delegation, and pair fallback. A reference classifier and regression tests cover all 81 combinations and policy conditions; documentation and the installed truth table are aligned. The assessment below records the original finding.

The [normative derivation](skills/setup-ai-first/assets/ai-first-schema.md#derivation-apply-in-order-first-match-wins) says “first match wins,” then mixes terminal assignments with caps. Rule 2 caps B=0 at pair; rule 3 explicitly downgrades V<2 to pair; rule 6 assigns human-only when two or more scores are zero.

For `V0 B0 C2 A2`, a literal early-return interpretation yields pair. Treating rules 2 and 3 as restrictions and continuing to rule 6 yields human-only. Across 81 combinations, those interpretations disagree on 31. The literal interpretation produces 78 pair, two human-only, and one delegate outcome before hard overrides.

This matters because separate agents can follow the same instructions and apply different levels of human involvement. The whitepaper's diagram also mixes “first match wins” with “continue.”

**Recommendation:** define one pure classification function and a complete 81-case truth table. Make hard overrides terminal, then explicitly distinguish caps from assignments. Generate the prose examples from those cases.

### 2. High — Approval is not bound to the brief being executed

The [GitHub adapter](skills/setup-ai-first/assets/adapters/github.md#approval-identity-check) checks the latest approval-label event, but does not check whether the brief changed afterward. The [Linear adapter](skills/setup-ai-first/assets/adapters/linear.md#approval-identity-check-schema-section-1) accepts a comment containing `[ai-first] APPROVED` without tying it to a brief revision or approval cycle.

Concrete Linear sequence: a reviewer approves; re-grooming removes the label; the brief changes; someone restores the label. The original comment still satisfies the documented check. Even without re-grooming, an ordinary body edit can retain approval under the documented tracker checks. Linked mutable brief documents create the same problem.

Additionally, [independence is defined against the tracker item creator](skills/setup-ai-first/assets/ai-first-schema.md#project-approval-policy). When intake uses a shared automation identity, the requester can differ from the creator and satisfy that check without a second person reviewing. The whitepaper instead describes independence from the requester.

**Recommendation:** bind approval to a brief revision or content digest, including linked content; invalidate it on material changes. Define the human requester/brief owner independently of the account that creates the item. Linear approval should use an exact structured record tied to that revision, with explicit revocation semantics. Its adapter also openly leaves the creator response field unconfirmed; verify that before claiming integration readiness.

### 3. High — The shipped package cannot provide the advertised enforcement guarantees

Both workflow skills say skipped steps are redirected “deterministically” by an enforcement layer. The [schema invariants](skills/setup-ai-first/assets/ai-first-schema.md#5-invariants-the-three-hard-poka-yoke-points) require activation checks and verification at merge. The repository ships instructions and an enforcement draft, but no running service or PR validation implementation.

The [guide index](docs/README.md#project-configuration-is-authoritative) does acknowledge that enforcement and PR integration are separate work. That is good, but it conflicts with the stronger present-tense assurances in the skills and whitepaper. Installing the plugin cannot prevent a direct tracker edit or an unverified merge.

Even the proposed service needs another check: R3 validates an existing approval, while R1 validates the child's tier/schema on activation. Neither explicitly requires a normal decomposed child's parent to remain approved. The single-item exception needs a durable representation if an engine is to distinguish it from a bypass.

**Recommendation:** clearly label shipped capabilities versus planned enforcement. Implement one tracker plus one merge gate, including parent-approval checks and the explicit single-item exception, before broadening coverage.

### 4. High design risk — Verification needs a trusted execution boundary

The [task contract](skills/setup-ai-first/assets/ai-first-schema.md#22-on-each-small-execution-item-written-by-decompose-and-classify) is intentionally human-editable and contains a command that the proposed pipeline executes. A nonempty command, or even a zero exit status, does not establish that the acceptance criteria were checked. `true` demonstrates the gap without any malicious behavior.

The enforcement spec correctly tells its service never to execute item content, but does not define the separate runner's command authorization, checkout revision, permissions, or verification integrity. This is a missing design boundary, not an observed exploit in shipped code.

**Recommendation:** prefer reviewed verification IDs mapped to repository-owned commands. Bind the check to the PR commit and task-contract revision, use a restricted runner, and review changes to the verification mechanism. Include a failing-case demonstration showing that the check detects an unmet criterion.

### 5. Medium — Mode selection and escalation rules conflict

The [classification skill](skills/decompose-and-classify/SKILL.md#guard-clauses-run-before-anything-else-fail-loudly) requires parent approval guards “before anything else,” but later defines single-item and reclassify modes that operate without that normal parent path. A literal executor can block the documented exceptions before selecting their mode.

Reclassification unconditionally sets pair at `bounce = 2` after re-scoring. If re-scoring discovers a human-only hard override, this instruction can weaken it. The text also leaves behavior at `bounce > 2` and duplicate reports of one failed cycle unclear; the future service has run-key deduplication, but the skill does not.

**Recommendation:** dispatch modes before their guards. Preserve hard overrides during escalation, use a threshold policy rather than equality alone, and identify each verification cycle so retries cannot count twice.

### 6. Medium — Capability evidence does not establish the claimed improvement

[Promotion](skills/update-ai-first-capabilities/SKILL.md#5-choose-status-and-authority) requires ten merged delegate tasks per covered class with zero escalations, while provisional capabilities cannot raise scores. This allows evaluation on already-delegable tasks, but provides no clear route to demonstrate an uplift for a class that needs the capability to become delegable. Classes that always touch public API contracts are capped below delegate, making that evidence requirement unattainable for them under the stated rules.

The classifier records final scores and applied metadata, but the contract does not require raw scores, per-axis deltas, or which provisional capabilities were actually used during execution. Successful tasks therefore need not establish that the proposed capability caused an improvement. Metadata includes requirements and limitations, yet classification does not explicitly require checking those preconditions in the current environment.

**Recommendation:** define a supervised evaluation path that preserves the current tier while measuring a capability. Record raw/final scores, actual usage, conditions, and outcomes. Require runtime prerequisites before applying an approved effect. Treat ten successes as an initial operational threshold, not proof that a validator or capability is reliable.

### 7. Medium — Workflow retries can create duplicate execution items

[Decomposition output](skills/decompose-and-classify/SKILL.md#output-per-execution-item) instructs the agent to create children and then post a summary. There is no reconciliation step for an already partially decomposed parent, stable child identity, or restart protocol.

If a session stops after creating three children, retrying can create them again. This is particularly relevant to an agent workflow spanning multiple external writes. The service draft's idempotency rules do not cover the skill's initial decomposition.

**Recommendation:** inspect existing children first, identify planned units using stable keys tied to the approved brief revision, and resume or reconcile partial work. Report actual successful writes when a later operation fails.

### 8. Medium — Contract drift is already visible and has no automated check

The [whitepaper](whitepaper.md) still says users cannot approve their own briefs and that grooming sign-off is never self-approved, despite the shipped solo policy. Its profile discussion and the manifest include a `delegate, B=1` route that cannot occur under the all-four-axes-equal-two rule. The Linear adapter deliberately changes the block delimiter from the normative parser's form; that exception needs shared parser fixtures.

The parser prose also omits decisions such as duplicate-key handling and a complete required-field/type definition. These are important for independent consumers of a supposedly machine-parsable contract.

**Recommendation:** add automated schema fixtures, mode and approval scenarios, tracker encoding round trips, manifest checks, and documentation consistency checks. Keep the whitepaper conceptual and link to normative rules rather than restating changing policy. Record the installed asset revision during setup so project-local copies can be compared during upgrades.

## Product judgment and priorities

The repo's strongest product is a disciplined handoff from an ask to a verifiable assignment. The larger capability registry and multi-tracker enforcement architecture are promising, but currently make users absorb substantial policy before there is evidence that the workflow saves time or catches defects.

I would sequence the next work as follows:

1. Resolve tier derivation, approval freshness, mode dispatch, and hard-override preservation; add regression fixtures for each.
2. Ship a small deterministic parser/classifier and one trusted PR verification integration. Prove the complete path on one tracker.
3. Pilot real work and measure grooming time, classification disagreement, duplicate/recovery incidents, escaped defects, and delivery time alongside bounce rates.
4. Use that evidence to refine capability promotion and expand adapters. Publish a license and a repeatable release validation command before encouraging broader redistribution.

My confidence is high in the local consistency findings and packaging checks. Actual agent adherence, tracker behavior, installation compatibility, and productivity benefits remain unmeasured in this review.
