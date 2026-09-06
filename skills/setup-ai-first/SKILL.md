---
name: setup-ai-first
description: Configure AI-first delivery for Azure DevOps, GitHub Issues, or Linear by installing the shared schema, capability manifest, and active tracker adapter. Run once before groom or decompose-and-classify.
---

# Set up AI-first delivery

Configure the current project for the `groom` and `decompose-and-classify` skills. This is an interactive setup skill. Inspect first, recommend choices when the repository provides evidence, confirm with the user, then write.

## 1. Inspect

Check for:

- an existing `.ai-first/` directory;
- tracker references in `AGENTS.md`, `CLAUDE.md`, repository docs, remotes, and environment configuration;
- available Azure DevOps, GitHub, or Linear tools;
- existing work item types and hierarchy language in tracker configuration and project docs;
- an existing capability manifest that the team may have customized;
- an existing plan-storage choice, planning repository, and archive convention.

Do not infer a tracker solely from an installed tool when both are plausible.

## 2. Choose the tracker

Ask which tracker this project uses when inspection did not settle it. Supported choices are:

- **Azure DevOps**: use [assets/adapters/ado.md](assets/adapters/ado.md).
- **GitHub Issues**: use [assets/adapters/github.md](assets/adapters/github.md).
- **Linear**: use [assets/adapters/linear.md](assets/adapters/linear.md).

If the tracker is unsupported, stop after explaining that a tracker adapter must define vocabulary, item operations, labels, linked documents, comments, hierarchy, approval identity, description-block storage, and label bootstrap behavior.

## 3. Choose work item terminology

The workflow has three semantic sizes but does not prescribe their names:

| Size role | Meaning | Common names |
|---|---|---|
| Large | Contains multiple independently groomed regular items; split before grooming | Epic, Initiative, Feature |
| Regular | The main unit that `groom` turns into a brief and later decomposes | Issue, Story, User Story, PBI |
| Small | One executable, classifiable outcome created by decomposition | Sub-issue, Sub-task, Task |

Infer the team's existing terms from the tracker and repository when possible. Present all three together and ask the user to confirm or change them. Recommend `Epic / Issue / Sub-issue` when there is no established vocabulary, while explaining that `Story` and `Task` are equally valid choices.

Record one singular display term for each role. The meanings above are fixed; only the words are configurable. Do not infer size from tracker type names alone after setup—always interpret the configured terms through their recorded roles.

## 4. Choose the approval policy

Ask whether the project has another human available to review briefs or is maintained
by a sole developer. Default to independent approval; never infer solo mode from
contributor count, installed tools, or the current login alone. Present an existing
policy on reruns and preserve it unless the user requests a change.

For solo development, offer explicit self-approval for one named human tracker
identity. Explain that the developer must still review and manually approve each
brief, including the revision-bound approval comment on every tracker; only the second-person requirement is
waived. Confirm the choice and canonical identity (GitHub login, Azure DevOps
identity ID, or Linear user ID). Resolve it with available tracker identity tools;
never use a display name or guess. If tools are unavailable, finish local setup
with `solo-mode: false`, report solo mode as pending identity verification, and
explain how to rerun setup after connecting the tracker.

Write the confirmed `solo-mode` value into the project-local schema's Project
approval policy section: `false` for independent approval, or a quoted canonical
identity for solo approval. Keep exactly one declaration. Do not change the
shipped asset's default. On an existing installation, show and reconcile the
schema and active adapter changes together so all consumers use the same rule.
Removing solo mode restores independent approval; existing self-approvals must be
rechecked under that policy before further decomposition.

## 5. Choose plan storage

Read [assets/plan-storage.md](assets/plan-storage.md). Offer tracker comments as the
default, or a dedicated Git planning branch for larger plans and context bundles.
Preserve an existing choice on reruns unless the user requests a change. Confirm
this alongside the other setup choices; do not require branch storage for delegation.

For git-branch, confirm the repository, branch prefix, work-artifact path pattern,
and durable archive destination/owner. Recommend `ai-first/plan/` and
`.ai-first/work/{item-key}/` when there is no convention. Explain that the tracker
pins a full commit ID and path; the branch holds plan/context, while the tracker
holds progress and creation intents. The branch is never merged as implementation
and is eligible for deletion only after completion and verified archival.

Inspect available repository access read-only. If details are missing, record them
as pending for branch-backed work. Setup configures the choice and installs the guide;
it does not create, push, merge, archive, or delete a planning branch or move existing
plans. Backend changes for in-progress work need explicit later reconciliation.

## 6. Preview the installation

Show the proposed tracker, approval policy (and solo identity if selected), plan-storage choice and any pending branch/archive details, and these project-local files:

```text
.ai-first/
├── README.md
├── ai-first-schema.md
├── ai-first-capabilities.yml
├── capabilities-guide.md
├── plan-storage.md
├── approval.py
├── terminology.md
└── tracker.md
```

The source files shipped with this skill are:

- [assets/ai-first-schema.md](assets/ai-first-schema.md)
- [assets/plan-storage.md](assets/plan-storage.md)
- [assets/approval.py](assets/approval.py)
- [assets/ai-first-capabilities.yml](assets/ai-first-capabilities.yml)
- [assets/capabilities-guide.md](assets/capabilities-guide.md)
- the selected file under `assets/adapters/`

If `.ai-first/` already exists, compare before overwriting. Preserve team changes to `ai-first-capabilities.yml` unless the user explicitly chooses to reset it. Never silently replace a customized schema or adapter; show the differences and ask how to reconcile them.

## 7. Write

Create the directory and copy the selected source content into the project-local paths above. Write `.ai-first/README.md` with:

- `tracker: ado`, `tracker: github`, or `tracker: linear`;
- the setup date;
- `plan-storage: tracker-comment` or `plan-storage: git-branch`; for git-branch,
  the confirmed repository, branch prefix, path pattern, archive destination/owner,
  and pending details per `plan-storage.md`;
- a pointer to `plan-storage.md` for publication, pinning, context, and cleanup;
- the confirmed approval policy and a pointer to the schema as its source of truth;
- a note that `tracker.md` is the active adapter;
- a note that `terminology.md` defines the project's large, regular, and small item names;
- a note that `groom` and `decompose-and-classify` read these files;
- a note that the capability manifest is intentionally project-owned, must be
  filled and approved by the user/team, and may be calibrated from telemetry;
- a note that no score-changing capabilities are enabled by the shipped default;
- a pointer to `capabilities-guide.md` and the `update-ai-first-capabilities` skill.

Do not infer or pre-approve capabilities during setup. Copy the conservative empty
manifest even when tools or skills are installed. After writing, offer to run
`update-ai-first-capabilities` with the user for each capability they want the
project to recognize.

Write `.ai-first/terminology.md` in this form, substituting the confirmed terms:

```markdown
# Work item terminology

- large: Epic
- regular: Issue
- small: Sub-issue

The large item contains multiple independently groomed regular items. The regular item is the unit groomed into an approved brief. The small item is one executable outcome created and classified during decomposition.
```

Use real file copies, not symlinks. Plugin caches and cross-agent skill installers may not preserve symlinks.

Install `approval.py` as a real copy alongside the schema. It requires Python 3
and no external packages. On upgrades, reconcile schema, helper, and active adapter
together. Explain that every consumer must support `brief-approval/v1`; existing
briefs need re-grooming and fresh approval, and label-only/bare-marker grants are
not migrated automatically. Preserve historical comments for audit. Do not grant
approval or rewrite historical grants during setup.

## 8. Tracker bootstrap

Read the selected adapter's label-bootstrap section.

- Azure DevOps needs no bootstrap.
- GitHub needs the seven repository labels listed in its adapter.
- Linear needs the seven workspace labels listed in its adapter.

For either GitHub or Linear, label creation changes an external repository or workspace. Show the exact labels and get explicit approval immediately before creating them. Skip labels that already exist.

Do not configure, install, or authenticate tracker integrations. If the required tracker tools are unavailable, finish the local setup and report the missing integration as the next step.

Do not install or activate optional CI templates or change branch policies during setup.
Local verification and human review work without a required PR gate.

## 9. Finish

Report the active tracker, the three selected terms, approval policy and any pending identity verification, plan-storage choice and pending archive/access details, and the files written. Tell the user that `groom` is ready. Explain the two-part approval rule on every tracker: a manual label plus a new human comment containing the exact brief revision and digest. Explain durable revocation through the REVOKED record.
