# Tracker adapter: ADO

Resolves `ai-first-schema.md`'s tracker-neutral terms to Azure DevOps' actual API surface.
Read this alongside the schema before a skill session writes anything to ADO.

## Vocabulary

| Schema term | ADO concept |
|---|---|
| item | ADO work item using the type configured for its size role |
| label | ADO tag |
| linked document | ADO wiki page |

## Fetching and creating items

Use the ADO MCP. Fetch by ID or URL. Create items with the work item types recorded in
`.ai-first/terminology.md`; these must match the process template in use.

## Labels

ADO tags are added/removed individually (no read-modify-write needed - the API is
additive/subtractive per tag, unlike a full-set replace). Apply and remove tags via the ADO
MCP's tag-update call.

## Linked documents

`brief-url:` points at an ADO wiki page URL, or is set to `inline` when the brief lives in
the work item description itself above the `[ai-first:v1]` block.

## Comments

Post via the ADO MCP's comment-create call. Comments are plain text/markdown per ADO's
sanitizer rules (see schema section 2's note on avoiding HTML comments).

## Hierarchy

A decomposed small item is linked to its regular parent via an ADO parent/child work item
link, created with the small item. A large item groups regular items using the same native
hierarchy. The configured words do not alter this relationship.

## Approval-identity check (schema section 1)

Via the ADO MCP's revisions API: fetch the work item's revision history, find the revision
that added the `brief-approved` tag, and compare its author identity to the work item's
creator. Apply the schema's project approval policy using canonical identity IDs:
they must differ unless the human approver matches the configured solo identity.
If this policy fails or the granting revision cannot be attributed, treat
`brief-approved` as not validly granted and block per schema invariant 1.

## Label bootstrap

None required. ADO tags are created automatically on first use; no pre-registration step.
