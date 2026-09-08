---
name: groom
description: Plan large tracker items into regular items, or turn a raw ask or regular item into an approval-ready AI-first brief. Run after setup-ai-first.
---

# Groom

User-invoked only. Run this workflow when a human explicitly invokes it, not from model inference. The guard clauses guide this invoked session. Direct tracker edits and merges outside the workflow are not automatically blocked; tracker enforcement and required CI checks are optional, separately deployed integrations.

Turns a regular item into a groomed brief that a human can approve, or plans a large item into regular child items. This skill PLANS and CLARIFIES. Execution decomposition and code belong downstream. Intake may create one unclassified small item under the explicit small-item exception below; classification is a separate human-invoked handoff. Regular grooming outputs a brief plus labels and hands off to a human approver, then to `decompose-and-classify`. Large-item planning outputs a split plan and, when requested, unclassified regular children for subsequent grooming.

Require `.ai-first/approval.py`; if absent, rerun setup to install the revision-bound approval protocol. Before doing anything else, read `.ai-first/README.md`, `.ai-first/terminology.md`, `.ai-first/ai-first-schema.md`, and `.ai-first/tracker.md` from the current project. If any is missing, stop and tell the user to install and run `setup-ai-first`. Use the configured large, regular, and small terms in all user-facing text and tracker item types. The tracker file explains which tools to call, how labels are read and written, and how approval identity is checked.


Run `python3 .ai-first/policy.py doctor --require-policy ai-first-policy/v1` before
workflow writes (`python` on Windows). Missing command, nonzero exit, or incompatible
files require setup reconciliation. Review any `unrecorded_changes` against current
project policy; never reset them automatically. Read the relevant command section
of `.ai-first/runtime-guide.md` when preparing helper inputs. Inputs are JSON data
files; remote facts and human judgments still come from inspected evidence.

## Intake and sizing triage

Input is either an item (ID or URL) OR a raw ask: a pasted email, DM, or thread ("could you add support of X to Y", "check this customer issue", "just a small feature for Z"). For raw asks, establish the six intake booleans from the request and run `policy.py intake` before any grooming. Its routing follows this order, first match wins:

1. **Investigation** - it is not yet known whether any work on our side is needed (customer issues, "please check if..."). Do NOT create an item. Run a bounded research pass: query docs MCPs, linked systems, and the repo; answer the question or produce findings. If work turns out to be needed, re-triage the remaining ask with what was learned.
2. **Small** - one outcome, one touched surface, machine-checkable definition of done, zero judgment calls. Create an item using the configured small term and stop with a handoff to `decompose-and-classify` in single-item mode. Do not classify it, apply a tier, or start the next skill automatically. All four conditions must hold; if any is uncertain, fall through.
3. **Large** - more than one destination, or the touched surfaces cannot be named yet, or the route is foggy enough that a multi-session planning effort is warranted. Enter large-item planning mode below. For a raw ask, create the configured large item only when tracker creation is requested; otherwise present the plan in conversation. Groom each resulting regular item separately.
4. **Regular** - everything else. Create an item using the configured regular term and proceed to grooming below.

Tie-break rule: when torn between small and regular, choose regular. Grooming a small thing costs minutes; skipping grooming on a mis-sized thing costs a sprint. The asymmetry is deliberate.

For existing items, fetch the item and linked context read-only and select the mode from configured tracker type and actual scope before regular grooming preconditions. A large item or an explicit large-to-regular planning request enters large-item planning; do not require a groomed or approved parent for this planning step. Do not silently change an existing item's type when scope and type disagree; explain the sizing recommendation.

Always paste the source ask VERBATIM into the created item's description (above the block) and link the thread if one exists. "It is in someone's inbox" is a context-locality score of zero; intake is where that gets fixed.

## Large-item planning

Read [large-item planning](references/large-item-planning.md) for this mode. Plan coherent regular outcomes, create linked unclassified children when requested, and hand off to regular grooming. The regular brief output and approval labels below do not apply to the large parent or ungroomed children.

## Regular grooming preconditions

1. Grooming always operates on an item. Raw asks must pass through intake first, which creates the item and embeds the source thread; never groom a pasted summary without an item to write into.
2. Fetch the item via the tracker MCP. If the fetch fails, stop and report.
3. If the item already carries `groomed`, ask whether to re-groom (which clears `brief-approved` if present, with a `[ai-first] BLOCKED:` comment explaining that re-approval is needed). Never silently overwrite an approved brief.

If a schema block exists, check the entire persisted description. Non-whitespace
content after its closing block needs explicit repair. Preserve those edits in the
reviewed brief before re-grooming; never omit them from the digest or silently erase
them when rewriting the block. A repaired brief needs fresh approval.

## Interrogation

Work through these five areas IN ORDER. Ask focused questions one area at a time; do not dump a questionnaire. Pull answers from the item, linked items, and the docs MCPs before asking the human - come prepared, ask only what you cannot find.

1. **Destination.** What does the world look like when this is done? One or two sentences, outcome not activity. If the requester cannot state it, that is the finding; record it and stop.
2. **Constraints.** Deadlines, performance budgets, compatibility requirements, tech mandates. Query docs MCPs for relevant ADRs and standards; cite them in the brief rather than restating them.
3. **Touched surfaces.** Which services, projects, contracts, and data does this change? Search the docs MCPs and linked items. Explicitly list public API contracts, auth surfaces, and data migrations touched - these feed the classifier's blast radius axis later.
4. **Definition of done.** Concrete, checkable criteria. Push hard here: for each criterion ask "could a machine check this?" and record the answer, because it becomes the verifiability signal downstream. Vague criteria ("works well", "is fast") get rewritten or rejected.
5. **Out of scope + human-only list.** What is explicitly NOT included, and which parts of this work must a human execute regardless of classification (the requester's call, recorded verbatim).

Track unresolved judgment calls as **open decisions**. Do not resolve them yourself; name them, note who should decide, and count them.

## Output

1. Write the brief into the item's description (or a linked document if the team convention is set), structured as: Destination / Constraints / Touched surfaces / Definition of done / Out of scope / Human-only list / Open decisions.
2. Confirm the request owner's canonical human tracker identity; do not substitute the item's automation creator. Generate a fresh UUID for `brief-revision` on every grooming, including re-grooming with unchanged text. Append the parent block per schema 2.1 with `approval-protocol: brief-approval/v1`, the verified `requester`, and the real `open-decisions` count. Remove any approval label before changing the brief. Persist the brief, re-fetch its stored representation and any linked brief content, and calculate `brief-digest` with `policy.py snapshot` from the complete persisted body, title, identity, and fetched linked content. Use `policy.py encode` for the validated block; never omit body text when constructing a payload. Write that digest, then re-fetch and verify it still matches. Never invent a digest. If the helper, identity tools, or linked content are unavailable, stop and report the missing prerequisite; do not announce an approval-ready brief.
3. Apply labels `ai-first` and `groomed`.
4. Show the exact one-line APPROVED record with the computed revision and digest for the human to post after reviewing the persisted snapshot. Explain that both the manual label and this new comment are required on every tracker. Never post the approval record on their behalf. NEVER apply `brief-approved`. Read the schema's project approval policy. In independent mode, post a comment naming the suggested independent approver. In solo mode, name the configured human and explain that they must review and manually self-approve the brief using the tracker's approval mechanism. In both modes, state that decomposition remains blocked until valid approval and zero open decisions; never auto-approve because solo mode is enabled.

## Stop conditions

- The requester cannot articulate a destination: stop, record what is known, do not fake a brief.
- The item is a bug with an obvious one-line fix: say grooming is overkill, suggest classifying it directly as one small item via `decompose-and-classify` in single-item mode.
- Open decisions exceed five: the item belongs at the configured large size. Record the decisions and continue in large-item planning mode to propose regular items. Do not manufacture answers or mark the item groomed; unresolved decisions that prevent choosing child boundaries must remain visible.
