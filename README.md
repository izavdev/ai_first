# AI-First Delivery Framework

Poka-yoke skills for AI-assisted delivery: groom the request, require human approval (independent by default, self-approval for configured solo developers), decompose it into small execution items, and classify each item by verifiability and risk.

The repository is now a portable Agent Skills package. There is no generation step and no agent-specific copy to keep in sync.

Licensed under the [MIT License](LICENSE).

## What is available now

The package ships four workflow skills and a portable policy runtime for approval,
classification, parsing, capability evaluation, and retry reconciliation. Skills guide invoked sessions; they do not monitor
all tracker changes or prevent merges outside the workflow.

Delegate work requires actual verification and human review of its evidence.
**Automated PR merge gates are optional.** Start with local verification, then adopt
[optional GitHub Actions or Azure Pipelines templates](docs/pr-verification.md) when
approved. Templates use named repository checks and report the tested commit, configuration hashes, and optional task-snapshot binding. They are dormant and setup does not activate them. The tracker
correction service remains a design specification.

## Install with the cross-agent wizard

```bash
npx skills@latest add izavdev/ai_first
```

Select all four skills, then choose any of the supported clients offered by the installer, including GitHub Copilot, Claude Code, and Codex. The installer copies ordinary, editable skill files into the location expected by each selected client.

Run `setup-ai-first` once in each target repository. It asks which tracker the project uses and what the team calls large, regular, and small work items, and whether briefs need independent approval or named solo self-approval. It then installs the shared schema, capability manifest and guide, terminology, and active adapter under `.ai-first/`. The capability manifest is project-owned and must be filled by the user or team; no score-changing capability is enabled by default. Use `update-ai-first-capabilities` to review tools, MCPs, resources, context retrieval, validators, skills, and agents before approving them. Setup also offers [dedicated planning branches](docs/plan-storage.md) for plan/context files, with tracker comments as the default. Use `groom` and `decompose-and-classify` afterward. Invoke them using the selected client's skill syntax: for example, `$setup-ai-first` in Codex or `/setup-ai-first` in Claude Code.

Do not install the same skills both through `npx skills` and a native plugin in one client; duplicate commands and discovery entries are the likely result.

### GitHub Copilot

[GitHub Copilot consumes Agent Skills](https://docs.github.com/en/copilot/concepts/agents/about-agent-skills) directly; it does not need a separate plugin manifest or generated `.prompt.md` copies. The cross-agent installer places them in Copilot's project skill directory:

```bash
npx skills@latest add izavdev/ai_first --agent github-copilot
```

[GitHub CLI 2.90 or later also provides a native interactive installer](https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/customize-cloud-agent/add-skills#managing-skills-with-github-cli), currently in public preview:

```bash
gh skill install izavdev/ai_first
```

Copilot loads a skill when its description is relevant to the request. To invoke one intentionally, say “Use the `setup-ai-first` skill” or “Use the `groom` skill”; Agent Skills are not the older prompt-file slash commands.

## Managed plugin bundles

This repository also carries native manifests for clients that support managed plugin bundles:

- Claude Code: [`.claude-plugin/plugin.json`](.claude-plugin/plugin.json) and its repository marketplace file bundle all four skills.
- Codex: [`.codex-plugin/plugin.json`](.codex-plugin/plugin.json) exposes the complete `skills/` tree as one plugin.
- GitHub Copilot: use either installer above; project skills are installed under `.github/skills`, `.claude/skills`, or `.agents/skills`, all of which Copilot recognizes.

The manifests make the repository publishable to the corresponding marketplaces. Until it is listed in a marketplace, the `npx skills` route is the simplest installation path from GitHub.

## Included skills

See the [skill how-to guides](docs/README.md) for prerequisites, example prompts, workflow steps, and troubleshooting for each skill.

| Skill | Purpose |
|---|---|
| `setup-ai-first` | Select Azure DevOps, GitHub Issues, or Linear; configure work item terminology; and create the project's `.ai-first/` contract files. |
| `update-ai-first-capabilities` | Interview capability owners, compare claims with available descriptions and docs, and maintain project approvals or custom-skill metadata. |
| `groom` | Turn a raw request or tracker item into an approval-ready brief. |
| `decompose-and-classify` | Decompose an approved brief, assign delegation tiers, or reclassify a bounced execution item. |

## Package layout

```text
skills/
├── setup-ai-first/
│   ├── SKILL.md
│   └── assets/
│       ├── ai-first-schema.md
│       ├── workflow-contract.json
│       ├── asset-manifest.json
│       ├── plan-storage.md
│       ├── ai-first-capabilities.yml
│       ├── capabilities-guide.md
│       └── adapters/
│           ├── ado.md
│           ├── github.md
│           └── linear.md
├── update-ai-first-capabilities/
│   ├── SKILL.md
│   └── assets/ai-first-capability.template.yml
├── groom/SKILL.md
└── decompose-and-classify/SKILL.md

.claude-plugin/                 Claude Code bundle metadata
.codex-plugin/                  Codex bundle metadata
```

The setup skill owns the distributable contract assets. It copies them into the consuming repository because the capability manifest and terminology are team-specific and because standalone skill installers may copy only selected skill directories. The workflow skills always read the project-local `.ai-first/` files, so tracker choice and vocabulary are runtime configuration rather than build-time forks.

Decomposition aims to maximize useful delegable work by resolving missing context,
decisions, and verification before final classification. Delegate requires V=2,
B=2, C=2, A>=1 and valid verification. A=1 permits bounded implementation choices
within linked conventions and explicit stop conditions; A=2 is mechanical. Planned
prerequisites do not improve a task's current classification.

Existing installations must rerun setup to reconcile the updated project-local
schema and capability profile routing before using this policy. The description
block remains `[ai-first:v1]`; its field format has not changed.

Version 0.4.1 rejects non-whitespace text after the description block and conflicting
snapshots of the same canonical child. Upgrade installed schemas and parsing
consumers together; preserve trailing edits for explicit repair, re-grooming, and
fresh brief approval. If using the optional verification runner, replace its copy
too and rerun checks to obtain the new file-content fingerprint.

Custom skills can advertise classification-relevant behavior in an
`ai-first-capability.yml` beside their `SKILL.md`. `decompose-and-classify` scans
the configured project-local skill roots, but metadata is only a claim: it has no
effect until a user adds an exact ID/version approval to the central project
manifest. This prevents an installed skill from declaring itself proven.

## Installed runtime and compatibility

Version 0.5.0 installs the tested policy runtime with the skills. Rerun setup to
copy `policy.py`, `ai_first/`, the runtime manifest/guide, and adapter contract;
reconcile existing customizations and generate the v2 installation receipt. Before
workflow writes, skills run:

```bash
python3 .ai-first/policy.py doctor --require-policy ai-first-policy/v1
```

The helper parses complete persisted briefs, derives tiers, evaluates approval
records using local solo policy, and reconciles retry inventory. It never calls
trackers or executes item commands. See the [runtime command guide](skills/setup-ai-first/assets/runtime-guide.md).
The `src.ai_first` import path remains a development compatibility shim to the same
shipped implementation; it contains no second policy implementation.

Adapter preflight records the actual connection's capabilities and server version.
Missing pagination, identity, or storage metadata blocks normal decomposition.
Synthetic adapter fixtures are not live compatibility certification. A revision
cache can reduce repeated body downloads when the connection provides authoritative
strong item revisions; complete listings and uncertain-create rules still apply.

See [evaluation and pilot instructions](evaluations/README.md) for blind behavioral
cases, captured-workflow tests, and the inventory workload benchmark.

## Solo developers

During `setup-ai-first`, select solo development and confirm your canonical tracker
identity. Setup records `solo-mode: "<your-tracker-identity>"` in the project's
`.ai-first/ai-first-schema.md`. You can then review and manually approve your own
briefs. Approval labels, revision-bound approval comments, and downstream checks still
apply. Existing projects can rerun setup to reconcile their schema and adapter.
See [working as a solo developer](docs/setup-ai-first.md#work-as-a-solo-developer).

## Tracker approval mechanisms

Every tracker requires both the `brief-approved` label/tag and a new human comment:

```text
[ai-first] APPROVED revision=<brief-revision> digest=<brief-digest>
```

Grooming provides the exact line after hashing the persisted brief with the installed
`approval.py` helper. Review the brief and requester identity before posting it.
Approval binds the item, revision, requester, title, brief text, and linked brief
content. Changes block decomposition; re-grooming always creates a new revision.
The latest record for that revision must be a valid approval. To revoke durably,
post the corresponding `REVOKED` record and remove the label.

Upgrade the schema, helper, adapter, and all consumers together through setup.
Existing briefs require re-grooming and fresh approval; old labels and bare markers
do not satisfy `brief-approval/v1`. See [approval instructions](docs/groom.md#obtain-human-approval).

## Development

Edit the four `SKILL.md` files and the setup assets directly. Validate all skills and both plugin manifests before releasing. Bump both plugin versions together.

Use Python 3.10 or newer. The repository CI matrix covers Python 3.10 and 3.13 on
Linux, macOS, and Windows. The optional verification runner supports native Windows
without WSL; see its [execution boundary](docs/pr-verification.md).

Run all repository checks:

```bash
python3 -m pip install -r requirements-dev.txt
python3 scripts/validate_repo.py
```

On Windows, run the same commands in PowerShell using `python` instead of `python3`
(or `py -3` outside a virtual environment). Install Git and make it available on
`PATH`. Repository text files use UTF-8 and Git checks them out with LF line endings
on every platform so shipped asset hashes remain consistent.

This validates skill front matter, native manifest versions/paths, strict JSON/YAML,
local documentation link targets, capability defaults/profile routing, generated
contract fields, shipped asset hashes, and the complete regression suite. It makes
no network requests and does not enable CI or enforce tracker/PR state. Live tracker
compatibility and external links require separate integration checks.

[Repository CI](.github/workflows/validate.yml) runs this same validator on pushes
and pull requests. This validates the package itself; the optional consumer PR
verification templates remain dormant until separately adopted.

After reviewing intentional changes to setup assets or contract fields, refresh the
field table and source hash manifest, inspect the generated diff, then validate again:

```bash
python3 scripts/validate_repo.py --refresh
python3 scripts/validate_repo.py
```

A plain validation run never rewrites files. `--refresh` updates generated metadata,
not plugin versions or approvals. Setup uses the source manifest to write an
installation receipt with source and final installed hashes, preserving customizations.

The runtime modules under `skills/setup-ai-first/assets/ai_first/` cover classification, capability evidence,
mode/escalation transitions, decomposition retries, and description parsing. Tests
cover all 81 score combinations, approval revisions, verification evidence, and
tracker-normalized Markdown round trips. They can also run independently without
third-party packages using `python3 -m unittest discover -s tests -v`.

The team-facing background material remains in [`whitepaper.md`](whitepaper.md) and [`assets_ai_first/`](assets_ai_first/). The [tracker enforcement specification](assets_ai_first/plugin-workflow-spec.md) defines a tracker-neutral rule engine and adapter contract.
