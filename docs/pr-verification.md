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
      "argv": ["python", "scripts/check_export.py"],
      "timeout_seconds": 1200,
      "covers": "Inventory CSV export preserves the approved columns and filters",
      "negative_case": "scripts/check_export.py: incorrect column order fails the assertion; attach the reviewed failing run"
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

Python 3.10 or newer and Git are required. The optional runner supports Linux,
macOS, and native Windows 10/11 and Windows Server 2016 or newer; WSL is optional.
On Windows, run from PowerShell with Python and Git on `PATH`:

```powershell
python .ai-first/ci/verify.py --config .ai-first/ci/verification.json --check acceptance
```

Use `py -3` if that is how Python is installed, and set the registry's `argv` to an
executable available in that environment. Add project runtime/dependency setup and services
before the CI step. The example has no executable command or coverage evidence and
fails with exit 2 until configured. Unknown IDs, duplicate JSON keys, and old
unversioned `argv` configs are rejected. To migrate an earlier starter config, wrap
its command in the versioned `checks` mapping and document its coverage and negative
case. Upgrade the runner and config together.

The runner executes only the selected registry argument array, with no implicit
shell. It never loads a command from an issue description, PR body, or task snapshot.
On Windows, `.bat`/`.cmd` files and shell built-ins need an explicitly reviewed shell
command in the registry, for example `["cmd.exe", "/d", "/c", "npm.cmd run test:acceptance"]`.
Native executables and Python scripts invoked through Python need no shell. The
shipped CI templates select Ubuntu; choose a Windows runner/pool and Windows command
paths when adopting them for a Windows project.
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
- whether the worktree was dirty, its fingerprint, and `worktree_schema`;
- outcome and command exit status.

The `ai-first-worktree/v2` fingerprint reads actual file bytes, executable modes,
symlink targets, missing tracked paths, index entries, and non-ignored untracked
files. It does not use diff presentation, text conversion, or clean/smudge filters;
`assume-unchanged`, `skip-worktree`, and `core.filemode` cannot hide file changes.
On Linux/macOS, executable modes come from the filesystem. Windows has no Unix
executable bit, so regular files use their Git index mode (or HEAD mode after a
staged deletion); index mode changes still invalidate evidence. Real symlinks are
hashed as links on either platform. A Git symlink checked out as a regular file on
Windows is fingerprinted as that actual file and counts as dirty.
Paths tracked by either HEAD or the index remain inputs, including staged deletions.
Dirty status compares those raw contents and modes with HEAD and the index, so
checkout filters or line-ending conversions can make a checkout count as dirty
even when Git status appears clean. Sparse-checkout omissions count as missing,
dirty inputs. Submodules, non-ignored nested repositories, and unresolved index
conflicts fail before execution; the runner does not fingerprint nested repositories.
An explicitly ignored nested repository is outside the evidence boundary, like
other ignored dependencies.

A dirty local run records its actual state but is not proof that the clean commit
passes; re-run after committing the final changes. Registry, runner, snapshot, HEAD,
index, or worktree changes during a run produce `inputs-changed` and exit 2, even if the
command returned zero. Configure normal test output directories in `.gitignore`
before adoption, so expected generated reports do not alter those inputs. Ignored
files, external services, dependencies, and transient changes restored during a run
are outside this fingerprint; the environment and check coverage remain review responsibilities.

On Linux/macOS, timeout or interruption kills the command's process group and reaps
the direct child. On Windows, the runner creates the command suspended, assigns it
to a Job Object, and resumes it only after assignment succeeds. It terminates the
job's process tree and waits for cleanup before returning, including leftover
workers after a normal exit. If job assignment is denied by an enclosing host's
restrictions, verification fails before the check runs.

Checks must wait for their own workers. On Linux/macOS they must not detach workers
into another session or process group. This handles ordinary descendant cleanup;
it does not contain a process that deliberately escapes. The runner is not a sandbox.

Upgrade existing runner copies to adopt these fixes. Version 2 fingerprints cannot
be compared with the earlier diff-based fingerprints; retain the recorded runner
hash and rerun verification with the updated runner.

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
