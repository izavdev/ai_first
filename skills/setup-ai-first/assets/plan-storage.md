# Plan storage options

Read this guide when configuring plan storage or when the selected backend is
`git-branch`. It changes where the plan and supporting context live, not approval,
classification, stable unit keys, or creation-retry rules.

## Configuration

Setup records `plan-storage: tracker-comment` or `plan-storage: git-branch` in
`.ai-first/README.md`. An absent declaration in an older project means tracker-comment.
An unknown/conflicting value needs repair; do not silently change an existing choice.

Tracker-comment is the default. Store the complete plan JSON in the parent's PLAN
comment as defined by the schema. Normal context links remain in task descriptions.

For git-branch, also record the confirmed values:

```yaml
plan-storage: git-branch
plan-repository: <canonical repository URL>
plan-branch-prefix: ai-first/plan/
plan-path-pattern: .ai-first/work/{item-key}/
plan-archive: <durable archive location and retention owner>
```

`item-key` is a filesystem/Git-safe identifier derived from the canonical parent
identity, with a disambiguating suffix when needed. Validate the concrete branch
and relative paths before use; never use raw tracker text as shell syntax or a path.
Record the actual branch and path on the parent rather than regenerating them later.
The planning repository may be the code repository or a separate approved repository.
If access or the archive destination is unresolved, setup records the pending detail;
branch-backed decomposition waits for it instead of falling back to another backend.

## Branch contents and ownership

For example, branch `ai-first/plan/github-org-repo-123` contains:

```text
.ai-first/work/github-org-repo-123/
├── brief.md
├── plan.json
├── context.md
└── decisions.md
```

`plan.json` is the same `ai-first-decomposition/v1` plan used by tracker-comment
storage, including stable unit IDs and complete intended child contracts. Context
and decision files are optional when they add useful information. `brief.md` is
an optional snapshot of the approved brief, not a second editable source of truth.
If it is instead the authoritative linked brief, grooming must pin its commit/path
and bind its fetched content in the approval digest before decomposition.

The planning branch contains work artifacts and is never merged as an implementation
branch. Keep implementation on its own branch/worktree. Use an isolated worktree or
checkout for planning edits so switching branches cannot disturb current code work.
The tracker owns execution state: child IDs, statuses, bounce history, create intents,
and completion summaries. Do not maintain a second progress ledger in the branch.

## Publish and pin a plan

1. Check the parent for an existing plan or PLAN-REF before creating a branch. Resume
   the recorded location and unit IDs. Existing conflicting plans require reconciliation.
2. Write and commit the plan and useful context to the configured branch. Publish
   it to the configured repository and verify collaborators can retrieve the exact
   commit and files before any child creation. A local-only commit is not shared state.
3. Post a parent comment beginning `[ai-first] PLAN-REF` with a fenced JSON object:

```json
{
  "schema": "ai-first-plan-ref/v1",
  "parent": "<canonical parent identity>",
  "revision": "<approved brief revision>",
  "brief_digest": "<approved brief digest>",
  "repository": "<canonical repository URL>",
  "branch": "<concrete planning branch>",
  "commit": "<full commit object ID>",
  "path": "<relative path to plan.json>"
}
```

4. Read the reference back, fetch the file at that exact commit, and validate its
   parent/revision/digest and unit keys. Do not resolve the branch's moving HEAD as
   the execution plan. Link relevant context files at the pinned commit in child
   descriptions. The plan itself must not embed its own eventual commit ID; record
   that ID in the tracker reference after committing, avoiding a self-reference.
5. Apply the normal schema retry protocol: create intents and outcome records remain
   tracker comments; inventory still includes closed and unlinked children. A failed
   push or PLAN-REF write stops before child creation. On retry, inspect the recorded
   branch/commits and tracker history instead of creating another plan blindly.

PLAN-REF is a storage pointer, not human approval. The parent description and its
approval digest remain unchanged by plan publication. If the approved scope changes,
re-groom and obtain a new approval revision. A changed plan needs explicit review
and reconciliation with existing units; do not silently adopt a newer branch commit.
Record a replacement reference with a link to the superseded record and rationale.
Conflicting unsuperseded references block; retain historical records for audit.
Changing backend mid-task follows the same explicit migration rule and preserves IDs.

## Context freshness

For each relevant code file, document, guide, or convention, explain why it matters.
Use repository + commit + path for exact baselines and documents that define approved
requirements. Mark living reference links as such, with when they were checked; they
are not an immutable approved requirement. Recheck relevant code and living guidance
before execution. If drift changes acceptance criteria or invalidates assumptions,
stop for reconciliation/re-approval rather than following stale context. Preserve
source access boundaries when copying context into the planning repository.

## Finish and archive

Do not delete a planning branch merely because an agent considers its work done.
After the parent and all planned work are complete, preserve the final plan, context,
decisions, and required historical snapshots at the configured durable archive. This
can be a retained immutable reference in an approved archive repository or exported
artifacts in a durable tracker/document store. A link to the soon-deleted branch or
a bare commit ID with no retention arrangement is not an archive.

Verify the archive can be retrieved independently of the temporary branch, including
files needed by pinned task links. Record the archive location and snapshot mapping
on the parent. If original links will stop resolving, add their durable replacements
without discarding the original provenance. Missing archive access or incomplete work
blocks cleanup. Delete the planning branch only under the user's normal cleanup
authorization; setup never creates, pushes, merges, archives, or deletes such branches.

This is an instruction-driven storage option. The package does not ship a Git hosting
service or automatic branch cleanup job. Git operations and remote writes remain
subject to available tools and the authorization for the actual work.
