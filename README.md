# AI-First Delivery Framework

Poka-yoke skills for AI-assisted delivery: groom the request, require human approval (independent by default, self-approval for configured solo developers), decompose it into small execution items, and classify each item by verifiability and risk.

The repository is now a portable Agent Skills package. There is no generation step and no agent-specific copy to keep in sync.

## Install with the cross-agent wizard

```bash
npx skills@latest add izavdev/ai_first
```

Select all four skills, then choose any of the supported clients offered by the installer, including GitHub Copilot, Claude Code, and Codex. The installer copies ordinary, editable skill files into the location expected by each selected client.

Run `setup-ai-first` once in each target repository. It asks which tracker the project uses and what the team calls large, regular, and small work items, and whether briefs need independent approval or named solo self-approval. It then installs the shared schema, capability manifest and guide, terminology, and active adapter under `.ai-first/`. The capability manifest is project-owned and must be filled by the user or team; no score-changing capability is enabled by default. Use `update-ai-first-capabilities` to review tools, MCPs, resources, context retrieval, validators, skills, and agents before approving them. Use `groom` and `decompose-and-classify` afterward. Invoke them using the selected client's skill syntax: for example, `$setup-ai-first` in Codex or `/setup-ai-first` in Claude Code.

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

Custom skills can advertise classification-relevant behavior in an
`ai-first-capability.yml` beside their `SKILL.md`. `decompose-and-classify` scans
the configured project-local skill roots, but metadata is only a claim: it has no
effect until a user adds an exact ID/version approval to the central project
manifest. This prevents an installed skill from declaring itself proven.

## Solo developers

During `setup-ai-first`, select solo development and confirm your canonical tracker
identity. Setup records `solo-mode: "<your-tracker-identity>"` in the project's
`.ai-first/ai-first-schema.md`. You can then review and manually approve your own
briefs. Approval labels, Linear's approval comment, and downstream checks still
apply. Existing projects can rerun setup to reconcile their schema and adapter.
See [working as a solo developer](docs/setup-ai-first.md#work-as-a-solo-developer).

## Tracker approval mechanisms

On GitHub, `brief-approved` is attributed through the issue event history. The latest event for that label must be a `labeled` event whose actor satisfies the project approval policy: independent by default, or the configured solo developer.

Linear approval has two parts:

1. Add the `brief-approved` label.
2. Add a comment containing `[ai-first] APPROVED`.

The comment supplies the approver identity that Linear's label mutation API does not expose. Azure DevOps derives that identity from work-item revisions and does not need the extra comment.

## Development

Edit the four `SKILL.md` files and the setup assets directly. Validate all skills and both plugin manifests before releasing. Bump both plugin versions together.

Run the reference classifier checks with Python 3 (no third-party dependencies):

```bash
python3 -m unittest discover -s tests -v
```

`src/ai_first/classification.py` implements tier derivation from final scores. The
checks cover all 81 score combinations, hard overrides, missing verification,
invalid inputs, and agreement with the truth table embedded in the installed
schema. This reference function does not score tasks, validate command coverage,
or enforce tracker or PR state.

The team-facing background material remains in [`whitepaper.md`](whitepaper.md) and [`assets_ai_first/`](assets_ai_first/). The [tracker enforcement specification](assets_ai_first/plugin-workflow-spec.md) defines a tracker-neutral rule engine and adapter contract.
