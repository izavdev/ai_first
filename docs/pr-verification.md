# Optional PR verification

You can use the framework before management approves CI changes. A delegate task
still needs a real acceptance command, successful execution, and human review of
the result. Automated merge blocking is optional and does not change its tier.

Start by running the task's `verify` command locally. In the PR description, record
the task link, tested commit, command, result, and relevant output. Re-run after
code changes; review whether the check covers the actual acceptance criteria.
The framework does not automatically prevent a merge in this mode.

## What ships

The [templates](../integrations/pr-verification/) are dormant examples outside active
CI directories. Setup does not copy, enable, register, authenticate, or require them.
Choose when to adopt them; no script is injected into individual PRs.

| Stage | Behavior | Adoption |
|---|---|---|
| Local verification | Developer runs acceptance checks; reviewer inspects evidence | Available now |
| Optional CI | PR/build shows the real pass or fail result; this new check is not required for merge | Copy and configure a template when approved |
| Required CI | Branch policy requires a successful check before merge, subject to the platform's bypass rules | Administrator enables later |

A failed optional check remains red. Do not use `continue-on-error` or suppress the
exit code to simulate optionality: whether it blocks merging is a branch-policy
choice. Existing organization policies may already require checks; confirm the
policy before enabling a workflow.

The templates select a named check from a repository-owned registry. They do **not** fetch
tracker items, prove approval freshness, validate task tiers or parent approvals,
post comments, or update bounce counts. They are verification starters, not the
full tracker enforcement service described in the design specification.

## Prepare the shared runner

Copy these files from this repository into the target repository:

| Source | Destination |
|---|---|
| `integrations/pr-verification/verify.py` | `.ai-first/ci/verify.py` |
| `integrations/pr-verification/verification.example.json` | `.ai-first/ci/verification.json` |

Define a stable check ID mapped to your actual acceptance command. For example,
if your project has this script:

```json
{
  "schema": "ai-first-verification/v1",
  "checks": {
    "acceptance": {
      "argv": ["npm", "run", "test:acceptance"],
      "timeout_seconds": 1200,
      "covers": "Inventory CSV export preserves the approved columns and filters",
      "negative_case": "tests/export.spec.ts: incorrect column order fails the assertion; attach the reviewed failing run"
    }
  }
}
```

`covers` and `negative_case` are review evidence descriptions, not executable
instructions or automatic approval. Before adopting a check, run a representative
case where its acceptance criterion is violated and confirm a failure; then confirm
the correct behavior passes. Mere nonempty metadata or a zero exit code cannot prove
coverage. A no-op such as `true` does not qualify as a verifier.

Run from the repository root:

```bash
python3 .ai-first/ci/verify.py --config .ai-first/ci/verification.json --check acceptance
```

Python 3 and Git are required. Add project runtime/dependency setup and services
before the CI step. The example has no executable command or coverage evidence and
fails with exit 2 until configured. Unknown IDs, duplicate JSON keys, and old
unversioned `argv` configs are rejected. To migrate an earlier starter config, wrap
its command in the versioned `checks` mapping and document its coverage and negative
case. Upgrade the runner and config together.

The runner executes only the selected registry argument array, with no implicit
shell. It never loads a command from an issue description, PR body, or task snapshot.
Do not add extra CLI arguments or shell fragments derived from tracker content.
Multiple named checks can share a registry; select the appropriate ID in the task
and CI configuration. Keep every registry command within the job's permitted scope.

## Bind evidence to the task and tested code

For task-specific evidence, save the current complete task description/schema block
plus canonical task identity and any referenced acceptance requirements in a snapshot
file. Include the parent revision/digest when applicable and pin or include linked
requirements so the snapshot is self-contained. Use a reviewer-selected local path:

```bash
python3 .ai-first/ci/verify.py --check acceptance --contract /path/to/task-snapshot.md
```

The snapshot is hashed as exact bytes, never parsed or executed. Compare it with the
current tracker task during review. The runner does not fetch or authenticate it:
its hash binds the result to supplied content, not to an independently approved
tracker revision. A changed task snapshot needs a new run and review.

The final `AI_FIRST_RESULT` JSON line records:

- selected check ID and checked-out commit;
- SHA-256 of the registry, runner, and optional task snapshot;
- whether the worktree was dirty and its fingerprint;
- outcome and command exit status.

Tracked diffs and non-ignored untracked file contents contribute to the fingerprint.
A dirty local run records its actual state but is not proof that the clean commit
passes; re-run after committing the final changes. Registry, runner, snapshot, HEAD,
or worktree changes during a run produce `inputs-changed` and exit 2, even if the
command returned zero. Configure normal test output directories in `.gitignore`
before adoption, so expected generated reports do not alter those inputs. Ignored
files, external services, dependencies, and transient changes restored during a run
are outside this fingerprint; the environment and check coverage remain review responsibilities.

Exit codes: 0 success, 1 command failure, 2 configuration/start errors or changed or
unverifiable inputs, 124 timeout. Output goes to the terminal/build log. Keep the
result line with the task link, snapshot, and reviewed run evidence. CI templates
omit `--contract` by default, so their `contract_digest` is null: that is general
repository-check evidence, not task-specific approval or verification. Add an
explicit saved snapshot only through a reviewed configuration change.

## Command trust and execution permissions

Repository ownership alone does not make a command safe or sufficient. Review the
registry, runner, workflow, and referenced test/script changes together. A PR can
change these files; the starter templates do not prevent that or independently
approve the new commands. Compare the result hashes to the reviewed files. If a
future required gate needs a stronger trust boundary, load the runner and registry
from an administrator-controlled immutable revision, independently of the PR, and
protect changes to that policy. The optional starters make no such enforcement claim.

The runner is not a sandbox. Keep its job free of deployment secrets, privileged
service connections, and reusable privileged runners for untrusted PRs. The supplied
jobs use hosted runners, no persisted checkout credentials, and no mapped tracker or
deployment tokens. Commands can still execute arbitrary repository code and access
whatever the environment permits. Use your organization's approved runtime/network
restrictions, and pin GitHub actions to an approved immutable revision when adopting.
Automated merge blocking remains optional throughout.

## GitHub Actions

1. Copy `integrations/pr-verification/github-actions.yml` to
   `.github/workflows/ai-first-verification.yml` in the target repository.
2. Configure the shared runner and runtime setup. The template uses `pull_request`
   and `workflow_dispatch`, read-only contents permission, and no persisted checkout
   credentials. It uses the event's default checkout, which for ordinary PR runs
   tests the PR merge commit. Manual dispatch tests the selected ref.
3. Review and merge the configuration through your normal approval process. Keep
   `AI-first acceptance` out of required checks during the optional trial.
4. Open a trial PR and confirm both a real passing and intentionally failing case
   are reported. Fork PR runs can require approval under your repository settings.
5. Later, an administrator can select this check in the target branch's required
   status checks/ruleset. Confirm that it runs on every PR the policy covers; add
   merge-queue support separately if your repository uses a merge queue.

Do not replace `pull_request` with `pull_request_target` to run PR code with a
privileged context. See [GitHub event behavior](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows),
[checkout configuration](https://github.com/actions/checkout), and
[required status checks](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches).

## Azure DevOps: Azure Repos + Azure Pipelines

1. Copy `integrations/pr-verification/azure-pipelines.yml` to
   `azure-pipelines-ai-first.yml` in the target repository and configure the shared runner.
2. When approved, create an Azure Pipeline pointing to that YAML file. Initially run
   it manually against a selected branch. The log records the tested commit;
   a manual run is not automatically evidence for a later PR merge commit.
3. For automatic PR reporting, an administrator adds this pipeline under the target
   branch's **Build validation** policy: choose **Automatic** trigger and **Optional**
   policy requirement during the trial.
4. Later, management can approve changing that requirement to **Required**. Review
   build-expiration settings so a changed target branch cannot reuse stale evidence.

Azure Repos does not use YAML `pr:` triggers; PR validation is configured through
branch policy and runs on the PR merge commit. The template's disabled YAML triggers
allow manual adoption before that policy is added. See
[Azure Repos pipeline triggers](https://learn.microsoft.com/en-us/azure/devops/pipelines/repos/azure-repos-git?view=azure-devops)
and [build validation policies](https://learn.microsoft.com/en-us/azure/devops/repos/git/branch-policies?view=azure-devops).
These instructions target Azure Repos, not a GitHub repository connected to Azure Pipelines.

## Linear

Linear can remain the work tracker while GitHub Actions or Azure Pipelines verifies
the code repository. No Linear-specific integration is installed by these templates.
Keep the Linear task link and verification evidence in the PR manually for now.
