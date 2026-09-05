---
name: groom
description: Turn a raw ask or tracker item into an approval-ready AI-first brief through structured interrogation. Run after setup-ai-first.
---

# Groom

User-invoked only. Run this workflow when a human explicitly invokes it, not from model inference. Anyone who skips it is redirected deterministically by guard clauses and the enforcement layer.

Turns a raw item into a groomed brief that a human can approve. This skill PLANS and CLARIFIES. It does not decompose, does not create small execution items, and never writes code. Its output is a brief plus labels; its exit hands off to a human approver, then to `decompose-and-classify`.

Before doing anything else, read `.ai-first/README.md`, `.ai-first/terminology.md`, `.ai-first/ai-first-schema.md`, and `.ai-first/tracker.md` from the current project. If any is missing, stop and tell the user to install and run `setup-ai-first`. Use the configured large, regular, and small terms in all user-facing text and tracker item types. The tracker file explains which tools to call, how labels are read and written, and how approval identity is checked.

## Intake and sizing triage

Input is either an item (ID or URL) OR a raw ask: a pasted email, DM, or thread ("could you add support of X to Y", "check this customer issue", "just a small feature for Z"). For raw asks, run triage BEFORE any grooming, in this order, first match wins:

1. **Investigation** - it is not yet known whether any work on our side is needed (customer issues, "please check if..."). Do NOT create an item. Run a bounded research pass: query docs MCPs, linked systems, and the repo; answer the question or produce findings. If work turns out to be needed, re-triage the remaining ask with what was learned.
2. **Small** - one outcome, one touched surface, machine-checkable definition of done, zero judgment calls. Create an item using the configured small term and hand off to `decompose-and-classify` in single-item mode. All four conditions must hold; if any is uncertain, fall through.
3. **Large** - more than one destination, or the touched surfaces cannot be named yet, or the route is foggy enough that a multi-session planning effort is warranted. Recommend splitting it into regular items first; groom each regular item separately. Do not groom a large item as if it were regular.
4. **Regular** - everything else. Create an item using the configured regular term and proceed to grooming below.

Tie-break rule: when torn between small and regular, choose regular. Grooming a small thing costs minutes; skipping grooming on a mis-sized thing costs a sprint. The asymmetry is deliberate.

Always paste the source ask VERBATIM into the created item's description (above the block) and link the thread if one exists. "It is in someone's inbox" is a context-locality score of zero; intake is where that gets fixed.

## Preconditions

1. Grooming always operates on an item. Raw asks must pass through intake first, which creates the item and embeds the source thread; never groom a pasted summary without an item to write into.
2. Fetch the item via the tracker MCP. If the fetch fails, stop and report.
3. If the item already carries `groomed`, ask whether to re-groom (which clears `brief-approved` if present, with a `[ai-first] BLOCKED:` comment explaining that re-approval is needed). Never silently overwrite an approved brief.

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
2. Append the parent description block per schema section 2.1, with `open-decisions` set to the real count.
3. Apply labels `ai-first` and `groomed`.
4. NEVER apply `brief-approved`. Read the schema's project approval policy. In independent mode, post a comment naming the suggested independent approver. In solo mode, name the configured human and explain that they must review and manually self-approve the brief using the tracker's approval mechanism. In both modes, state that decomposition remains blocked until valid approval and zero open decisions; never auto-approve because solo mode is enabled.

## Stop conditions

- The requester cannot articulate a destination: stop, record what is known, do not fake a brief.
- The item is a bug with an obvious one-line fix: say grooming is overkill, suggest classifying it directly as one small item via `decompose-and-classify` in single-item mode.
- Open decisions exceed five: the item belongs at the configured large size. Recommend splitting it into regular items before grooming continues.
