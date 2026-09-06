# How to set up AI-first

Run this skill once in each target repository, before grooming or classification. It supports Azure DevOps, GitHub Issues, and Linear.

## Before you start

- Install `setup-ai-first` and the workflow skills you intend to use.
- Open the target repository in your agent client.
- Know the tracker and the team's names for large, regular, and small work items.
- Have tracker tools available if you want label bootstrap completed in the same session. Local setup can finish without them.

## Run setup

```text
$setup-ai-first
Configure this repository for GitHub Issues.
Use Epic / Issue / Sub-issue for large / regular / small work items.
```

1. Let the skill inspect existing configuration, repository references, and available tracker tools.
2. Confirm the tracker and all three terminology choices. For Azure DevOps, use work item types supported by the project's process template.
3. Confirm independent approval or solo development and your canonical tracker identity. Review the installation preview. If `.ai-first/` already exists, review differences and decide how to reconcile customized files.
4. Choose tracker comments (default) or a dedicated Git planning branch. For a branch, confirm the repository, naming/path convention, and durable archive destination/owner. Setup configures the option without creating or pushing branches.
5. Let the skill write the local contract files.
6. For GitHub or Linear, review and explicitly approve creation of missing labels when prompted.

The seven workflow labels are `ai-first`, `groomed`, `brief-approved`, `ai-delegate`, `ai-pair`, `human-only`, and `ai-escalated`. GitHub creates them in the repository; Linear creates workspace-level labels. Azure DevOps needs no label bootstrap.

## Check the result

The target repository should contain:

```text
.ai-first/
├── README.md
├── ai-first-schema.md
├── workflow-contract.json
├── installation.json
├── ai-first-capabilities.yml
├── capabilities-guide.md
├── plan-storage.md
├── approval.py
├── terminology.md
└── tracker.md
```

Check that `README.md` names the intended tracker, `terminology.md` contains the confirmed terms, and `tracker.md` is the selected adapter. Files are real copies so they remain usable independently of the skill installation.

The shipped capability manifest has no enabled score-changing capabilities. Installed tools do not automatically become approved capabilities. Use [update-ai-first-capabilities](update-ai-first-capabilities.md) to review them.

## Check installed provenance

Setup copies the machine-readable field contract with the schema and writes
`installation.json`: package version, source asset hashes, actual installed hashes,
tracker/path mapping, and source commit/dirty status when known. Source and installed
hashes are separate so team customizations are visible. An unknown source commit
is recorded as null; the verified asset hashes still identify the copied content.
On reruns, compare the receipt and current files before reconciling updates. The
receipt is an audit aid, not a permission to overwrite customized configuration.

## Choose where plans live

Use tracker comments for a simple setup, or select a dedicated branch to keep
`plan.json`, context, and decisions together. The tracker pins the branch's exact
commit/path and continues to own progress, child IDs, and retry history. Planning
branches are never merged as implementation and are deleted only after completion
and verified archival. See [plan storage options](plan-storage.md) for an example
setup prompt and the lifecycle.

## Work as a solo developer

Choose solo mode during setup when no other person can review your briefs:

```text
$setup-ai-first
I am the only developer. Enable solo self-approval for this GitHub repository.
My GitHub login is <your-login>. Keep the existing terminology and capabilities.
```

Setup confirms the choice and verifies the identity used by tracker approval
history: GitHub login, Azure DevOps identity ID, or Linear user ID. The project
schema contains one policy declaration:

```yaml
solo-mode: "<your-canonical-tracker-identity>"
```

The placeholder above must be replaced by your actual identity. `solo-mode: false`
is the default; older schemas without the setting also require independent
approval. Setup leaves that default in place if it cannot verify the solo identity
and reports how to finish after connecting tracker tools.

For each regular item:

1. Run `groom` and review the resulting destination, constraints, scope, and completion criteria.
2. Resolve every open decision.
3. Manually apply `brief-approved` using your configured account. On every tracker, also post the exact revision/digest APPROVED line supplied by grooming yourself.
4. Invoke `decompose-and-classify`. Its parent summary records use of solo self-approval.

Solo mode bypasses the need for a second person. It keeps the deliberate human
approval step and all classification, verification, and escalation rules. An
agent cannot approve for you. Re-grooming still requires fresh approval.

For an existing project, rerun setup and review the proposed schema and active
adapter changes together; preserve other project customizations. To return to
team approval, rerun setup and choose independent approval (`solo-mode: false`).
Existing self-approvals will no longer pass subsequent approval checks. Never try
to enable the exception through an issue description or comment.

## Explain approval to the team

After grooming, an independent human grants approval by default. In configured solo mode, the named developer may approve their own brief:

| Tracker | Approval action and evidence |
|---|---|
| GitHub | Apply the label and post the exact revision/digest APPROVED comment; its author is the approver. |
| Azure DevOps | Apply the tag and post the exact revision/digest APPROVED comment; its author is the approver. |
| Linear | Apply the label and post the exact revision/digest APPROVED comment; its author is the approver. |

Setup now also installs `approval.py` (Python 3, no external dependencies). Upgrade
all consumers together and re-groom existing briefs: label-only and bare-marker
approvals cannot carry forward. See the [approval protocol](groom.md#obtain-human-approval)
for edits, revocation, and fresh approval.

No skill grants brief approval. See [grooming](groom.md#obtain-human-approval) for the handoff.

## Troubleshoot

| Situation | Next step |
|---|---|
| Tracker tools are unavailable | Finish local setup, then connect the required integration separately. Setup does not install or authenticate integrations. |
| Existing files are customized | Review the differences. Preserve team capability entries unless explicitly resetting them. |
| Tracker is unsupported | Provide an adapter defining item operations, vocabulary, labels, documents, comments, hierarchy, approval identity, block storage, and bootstrap behavior before proceeding. |
| Labels were not created | Complete the approved bootstrap before running workflows that apply those labels. |

Next: [groom a request](groom.md). Source: [setup-ai-first/SKILL.md](../skills/setup-ai-first/SKILL.md).
