# Installed policy helper

The setup skill installs `policy.py`, `approval.py`, the `ai_first/` package,
`workflow-contract.json`, `adapter-contract.json`, and `runtime-manifest.json` as
real files. Python 3.10+ is the only runtime dependency. The source tests and installed
commands use the same implementation. No tracker or shell command is executed by
the policy helper. Tracker identities, evidence, and completeness are established
through authenticated tools and human review, never inferred from item text.

## Before workflow writes

Run from the consuming repository:

```bash
python3 .ai-first/policy.py doctor --require-policy ai-first-policy/v1
```

On Windows use `python` instead of `python3`. Exit 0 means local runtime bytes and
policy revisions match the reviewed receipt. Exit 1 means incompatible; rerun setup
and reconcile the reported components. Exit 2 indicates malformed input or an I/O
error. A helper missing the `doctor` command is an old consumer, not a passing check.
Review `unrecorded_changes` against the actual current project configuration before
continuing; do not reset them. `reviewed_customizations` identifies differences
already recorded at setup. Compatibility does not certify those policies or remote
facts. The marker is a compatibility declaration, not a cryptographic signature.

Runtime files and field contracts are versioned together. Team policy belongs in
the schema, tracker adapter, and capability manifest, not patched Python copies.
For a custom runtime, maintain a separately reviewed distribution and its tests.

## Commands

All policy commands take a UTF-8 JSON **file path** and return one JSON object.
Duplicate keys and nonstandard JSON constants are rejected. Never interpolate input
from an issue into a shell expression. Save JSON with a serializer, call the fixed
helper command, inspect its exit code and result. A negative approval, readiness,
promotion, or incomplete inventory returns 1; malformed inputs return 2.

| Command | Input object | Result |
|---|---|---|
| `decode` | `body`, `tracker`, optional `labels` | Preserved `human` text and validated `fields` |
| `encode` | `human`, `fields`, `tracker` | Canonical `body` |
| `snapshot` | `item`, `title`, complete persisted `body`, `tracker`, `linked_content` | Validated brief `payload`, recomputed `digest`, `stored_digest` |
| `check-brief` | `snapshot_data` in the preceding shape, `records`, and explicit `label_present`, `requester_verified`, `history_complete`, `snapshot_stable` booleans | `valid` and digest; solo policy comes only from installed schema |
| `classify` | `v`, `b`, `c`, `a`, explicit `hard_override`, `verification_valid` | `tier` |
| `intake` | Explicit `needs_investigation`, `one_outcome`, `one_surface`, `machine_checkable`, `no_decisions`, `large` booleans | Route, creation role, and stopping handoff |
| `mode` | `requested`, `kind` | Validated `mode` |
| `reclassify` | Classifier fields plus `bounce`, `failed_cycles`, optional `cycle_id`, `human_tier` | Tier, ledger, bounce, escalation |
| `adjust-scores` | `raw` axis map, `capabilities` array of resolved entries | Raw/final scores, deltas, applied sources |
| `promotion` | `capability_id`, `version`, `covers`, `effects`, `trials`, `history_complete` | Review eligibility `ready` |
| `select-plan` | `plans` array | One validated consistent plan or null |
| `unit-key` | `parent`, `revision`, `brief_digest`, `unit_id` | Stable `key` |
| `reconcile` | `plan`, `items`, `intents`, explicit `inventory_complete`, optional `resolved_prior` | Create/reuse `actions` or a blocking error |
| `history` | `tracker`, captured `pages`, independently verified `human_ids` | Chronologically ordered approval `records` |
| `adapter-check` | Actual `tracker`, `server` name/version, `checks`, `concurrency` | Readiness and missing capabilities |
| `tag-patch` | ADO `revision`, `current` tags string, `add`, `remove` lists | Revision-guarded JSON Patch operations |
| `inventory` | Fresh complete `listing`, `fetched`, optional `cache`, booleans `inventory_complete`, `strong_revisions` | Missing `fetch_ids`, complete `items`, next `cache` |

The lower-level `digest` and `approval` commands accept the existing approval helper's
payload and evaluation arguments. Workflow skills use `snapshot` and `check-brief`
to ensure the entire persisted description is parsed and solo policy is loaded locally.
Do not use a successful digest computation as an approval decision.

For example, after reviewing scores and verification coverage, save:

```json
{"v": 2, "b": 2, "c": 2, "a": 1, "hard_override": false, "verification_valid": true}
```

Then run `python3 .ai-first/policy.py classify classification.json`. The result is
`{"tier": "delegate"}`. The helper derives the tier; it does not establish the
input scores or command coverage. Use the detailed schema for those judgments.

For a brief, keep the full fetched title/body and linked content in `snapshot.json`.
Run `snapshot` after initial persistence, write its real digest to the brief, re-fetch,
and run it again. The initial unapproved block may use an all-zero SHA-256 placeholder
only while calculating its first real digest; never present that placeholder for approval.
At consumption, pass the fresh snapshot and normalized history to `check-brief`.
Require exit 0 and `valid: true` immediately before each child write.

## Adapter preflight and history captures

The required checks are listed in `adapter-contract.json`. Record each as
`{"supported": true, "evidence": "reference to inspected response or tool contract"}`.
Unknown or missing checks block normal decomposition. Save the observed server name
and version; no server version is claimed live-certified by the shipped fixtures.
Use `concurrency: "conditional-writes"` when supported, or `"serialized"` only after
establishing a single workflow owner. Readiness is a report about supplied evidence.

`history` accepts these transport captures. The first `request_cursor` is null;
each subsequent one must equal the preceding continuation cursor. An unconsumed
cursor blocks. Do not manufacture terminal metadata from a short page or a tool that
hides pagination. Normalize an explicitly absent ADO token to null after inspecting
the full response; retain the original capture for review.

- GitHub REST: `{"request_cursor": null, "next_cursor": null, "data": [...]}`.
  Preserve the next-page URL from the HTTP Link header, and each comment's `id`,
  `body`, `user.login`, `user.type`, `created_at`, `updated_at`.
- ADO REST: `{"request_cursor": null, "data": {"comments": [...], "continuationToken": null}}`.
  Preserve `id` or `commentId`, `text`, `createdBy.id`, `createdDate`, `modifiedDate`,
  and any `version`/`isDeleted`. Conflicting IDs are rejected; deleted records grant nothing.
- Linear GraphQL comment connection: `{"request_cursor": null, "data": {"nodes": [...],
  "pageInfo": {"hasNextPage": false, "endCursor": null}}}`. Fetch `id`, `body`,
  `user.id`, `createdAt`, `updatedAt`. An MCP with a different representation needs
  an explicit, reviewed mapping; missing metadata cannot be guessed.

Independent identity lookup supplies `human_ids`. A user-like API account alone
does not prove human authorship. Conflicting snapshots, missing timestamps, and
ambiguous protocol creation order block. Keep capture scope bound to the exact
tracker item and re-fetch when it changes; the helper does not authenticate captures.

Sources: [GitHub issue comments](https://docs.github.com/en/rest/issues/comments),
[ADO comments and pagination](https://learn.microsoft.com/en-us/rest/api/azure/devops/wit/comments/get-comments?view=azure-devops-rest-7.1),
[Linear pagination](https://linear.app/developers/pagination).

## Reconcile without repeatedly downloading unchanged bodies

`inventory` always requires a fresh, complete all-state listing of canonical IDs
and revisions, including unlinked items. Supply fetched entries as
`{"id": "ado:org/project/1", "revision": 4, "item": {...normalized child snapshot...}}`.
Listing entries contain just `id` and `revision`. First call with an empty fetched
list to obtain IDs to fetch, then supply those snapshots and the returned cache.
Reconcile only a result with `complete: true`.

Enable `strong_revisions` only when the adapter establishes that the listed version
changes with every field relevant to the normalized snapshot. ADO numeric work-item
revisions can support this after connection validation. Timestamps alone (including
GitHub `updated_at`) are insufficient. Otherwise leave it false and fetch every body.
Fresh listings still cover the entire container; this reduces body downloads, not
the listing's complexity. Revision conflicts require a new listing. Discard a cache
on provenance uncertainty, backend changes, or incompatible representation changes.

For large inventories, redirect the helper's JSON to a local result file and
inspect only `complete`, counts, and `fetch_ids`; pass the stored `items` directly
to the next helper input with a JSON serializer. Do not paste all bodies into agent
context. Cache files are operational session data and should not be committed.

Reuse is scoped to a single authenticated container and reviewed session. The
caller owns that scope; never load cache claims from tracker text. Preserve create
intents and perform fresh parent/child/label checks before writes. The cache does
not authorize a retry after an uncertain response or guarantee atomic creation.

## Record a reviewed installation

After copying/reconciling all runtime files, guides, schema, selected tracker, and
project README/terminology, run the installed helper against the original setup
asset manifest:

```bash
python3 .ai-first/policy.py record-installation --root .ai-first --tracker github --source-manifest /path/to/setup-ai-first/assets/asset-manifest.json
python3 .ai-first/policy.py doctor --require-policy ai-first-policy/v1
```

This verifies source and runtime hashes before atomically replacing
`installation.json` with a v2 receipt. It preserves customized files and records
source and installed hashes separately. Unknown source commit/dirty state remain
null. An old v1 receipt requires an explicit setup reconciliation; do not just
change its version field. A receipt and its hashes record reviewed provenance,
not authenticity against a malicious editor with access to the same files.

Large intake returns `next_mode: large-item-planning` and `stop_after: plan-regular-items`.
`create_role: null` means intake does not itself authorize creation; `groom` plans
regular children and creates the large parent/regular children only within the
user's requested tracker scope. These children remain unclassified until groomed
and approved individually. Existing large tracker items enter this planning mode
directly after read-only sizing, without passing regular brief approval guards.
