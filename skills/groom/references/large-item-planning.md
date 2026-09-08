# Large-item planning

Use the project's configured large and regular terms (for example Epic → Issues).
This mode organizes scope before regular grooming. It does not create execution
tasks, assign delegation tiers, or grant brief approval.

## Establish the split

Read the source ask, large item, linked specs, and existing children before asking
questions. Clarify the overall destination, constraints, exclusions, human-only
work, and major outcomes. Propose regular items with one coherent outcome each;
split by outcomes and real dependencies, not by arbitrary task counts or technical
layers. Record unresolved decisions and their owners. Ask only for decisions that
prevent choosing meaningful child boundaries; other decisions may remain for each
child's grooming. Do not require execution commands or zero open decisions here.

For each proposed child, provide a title, destination, scope and exclusions,
initial acceptance criteria, known touched surfaces, context links, dependencies,
inherited constraints and human-only work, and open decisions. Clearly mark unknowns.
Explain how the children cover the large item's outcome and identify gaps or
overlaps. Reuse suitable existing children, including completed work; preserve human
edits and flag conflicts instead of replacing them.

## Persist only the requested work

A request to propose or review a split produces the plan without tracker writes.
A request to decompose an Epic into Issues authorizes creating and linking those
Issues; do not ask for the same permission again. If creation was not requested,
finish the concrete proposal before asking whether to create it. Do not create a
large parent for a raw ask unless tracker creation is within the requested scope.

Before writes, run the shared doctor check and verify the actual tracker supports
the required child types and relationships. If it cannot, deliver the concrete
plan and report the missing operation. Do not substitute execution tasks for regular
items. For an existing large parent, keep planning progress in comments or a linked
planning document; preserve its description, schema, and approval state. Its approval
does not approve any child. This planning mode never applies `groomed`,
`brief-approved`, tier labels, or brief/task schema blocks.

Before creating children, persist and read back the split plan on the parent with a
stable UUID per proposed child and any reused child IDs. Record that UUID and parent
link in each new child's initial description as ordinary planning provenance,
outside the reserved schema format. Include the original source ask verbatim,
distinguish the child's scope from that source, and link the source thread and plan.
Create each missing child using the configured regular type, then attach hierarchy
and dependency links supported by the adapter.

On resume, read the saved plan and current related-item inventory, including closed
items, and search for its child UUIDs before creating anything. Reuse existing matches
and repair missing links. Record each returned ID promptly. If creation times out,
search for the UUID and stop if the result remains uncertain; do not blindly retry.
Ambiguous matches or incomplete inventory block further creation until resolved.
Do not reuse execution decomposition's PLAN/CREATE-INTENT records or helpers: those
require an approved brief and classified task blocks.

Re-fetch created/reused children and verify their types and required links. Report
the plan, IDs, remaining decisions, and any incomplete operations. Stop with a
handoff to `$groom <regular-item-id>` for each child; if the user already requested
grooming those children, continue that authorized work in regular mode. Each child
needs its own persisted brief and human approval before an explicit
`decompose-and-classify` invocation can produce small execution items.
