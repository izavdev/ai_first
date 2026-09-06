# Store plans in tracker comments or a planning branch

Choose during `setup-ai-first`. Tracker comments remain the default and need no
additional Git workflow. A dedicated planning branch is useful when a feature needs
several plan/context files or a reviewable history of planning decisions.

| Responsibility | Tracker-comment option | Git-branch option |
|---|---|---|
| Plan and stable unit IDs | Parent PLAN comment | `plan.json` at a pinned commit |
| Supporting context | Links in tracker items | Optional context/decision files plus source links |
| Plan location | Parent item | Parent PLAN-REF with repository, full commit ID, and path |
| Child IDs, status, retries, bounces | Tracker | Tracker |
| Completion retention | Tracker history | Verified durable archive before branch cleanup |

## Configure a planning branch

```text
$setup-ai-first
Use a dedicated Git branch for plans and context in this repository.
Use branch prefix ai-first/plan/ and paths .ai-first/work/{item-key}/.
Use <approved archive destination> with <retention owner> for completed plans.
```

Setup confirms the repository, naming/path convention, and archive arrangement,
then writes the choice into `.ai-first/README.md` and installs `plan-storage.md`.
It preserves existing settings on reruns. Missing access or archive details are
reported as pending; setup does not create branches or migrate an in-progress plan.

For a parent issue, a later decomposition might create:

```text
Branch: ai-first/plan/github-org-repo-123

.ai-first/work/github-org-repo-123/
├── brief.md       # optional approved snapshot
├── plan.json      # complete classified plan and stable unit IDs
├── context.md     # relevant files, docs, guides, and why they matter
└── decisions.md   # decisions and rationale when useful
```

The branch is never merged as implementation. Code work stays on its implementation
branch; the planning workflow uses an isolated checkout/worktree. Avoid duplicating
progress in these files—the tracker owns execution state.

## Work with pinned snapshots

Decomposition publishes the plan, then records a PLAN-REF parent comment containing
the exact repository, full commit ID, and file path. Child creation starts only once
that snapshot can be fetched and validated. Retry uses that same plan and unit IDs,
not the branch's latest contents. A plan cannot include its own eventual commit ID;
the tracker stores that pointer after publication.

A PLAN-REF is not an approval. The existing approved brief remains authoritative.
If `brief.md` becomes the authoritative linked brief, grooming pins and hashes it
before approval. Material requirement changes still need re-grooming and approval.
Changes to an existing plan require explicit review/reconciliation and an attributable
replacement reference; a newer commit is never adopted silently.

Use commit-pinned links for code baselines and approved requirement documents. Mark
living guides as references and recheck them before execution. A context bundle helps
a cold session understand the task; it does not make stale assumptions current.

## Complete and clean up

When the parent and planned work are complete, retain the final plan, context,
decisions, and required historical snapshots at the configured archive. Verify it
can be retrieved independently of the temporary branch, and add durable replacement
links for any task links that would stop resolving. Record the archive mapping on
the parent before deleting the branch under the normal cleanup authorization.

There is no automatic branch deletion job. An unresolved archive destination means
keep the branch. A bare commit ID without a retention arrangement is insufficient.

For exact configuration keys, PLAN-REF fields, migration, and cleanup rules, see the
[shipped plan-storage guide](../skills/setup-ai-first/assets/plan-storage.md), which
setup copies into the target repository. This option also works with Linear as the
tracker; the planning repository is configured separately.
