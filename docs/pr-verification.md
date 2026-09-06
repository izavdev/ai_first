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

The templates run one repository-owned acceptance command. They do **not** fetch
tracker items, prove approval freshness, validate task tiers or parent approvals,
post comments, or update bounce counts. They are verification starters, not the
full tracker enforcement service described in the design specification.

## Prepare the shared runner

Copy these files from this repository into the target repository:

| Source | Destination |
|---|---|
| `integrations/pr-verification/verify.py` | `.ai-first/ci/verify.py` |
| `integrations/pr-verification/verification.example.json` | `.ai-first/ci/verification.json` |

Edit `argv` to your real acceptance command, as an argument array. For example,
if your project has that test script:

```json
{
  "argv": ["npm", "run", "test:acceptance"],
  "timeout_seconds": 1200
}
```

Run from the repository root:

```bash
python3 .ai-first/ci/verify.py --config .ai-first/ci/verification.json
```

Python 3 and Git are required. Add your project's runtime, dependency installation,
and test services to the CI template before the verification step. The empty example
fails with exit 2 until configured. The runner records the checked-out commit and
returns 0 for success, 1 for command failure, 2 for configuration/start errors,
or 124 for timeout. Output goes to the terminal/build log; no tracker credentials
are needed. The outer CI job also has a timeout.

A task may use this runner as its `verify` command only if the configured checks
cover its acceptance criteria. A green general test suite is insufficient evidence
for an unrelated task. Review a representative failing case before trusting a new
check. Keep verification config, runner, tests, and workflow changes visible in
review; use immutable action versions approved by your organization when adopting
the GitHub example. The runner uses an argument array with no implicit shell, but
executing repository code still requires an appropriate CI environment. Keep this
verification job free of deployment secrets and privileged service connections.

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
