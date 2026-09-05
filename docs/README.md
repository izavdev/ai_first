# Skill how-to guides

Use these guides in the repository where you want to manage delivery. Install the skills using the [installation instructions](../README.md#install-with-the-cross-agent-wizard) first.

| Guide | When to use it |
|---|---|
| [Set up AI-first](setup-ai-first.md) | Configure the tracker, terminology, and project contract files. |
| [Update AI-first capabilities](update-ai-first-capabilities.md) | Register and review tools, validators, resources, skills, or agents that may affect classification. |
| [Groom a request](groom.md) | Turn an ask into a brief ready for human approval under the project policy. |
| [Decompose and classify](decompose-and-classify.md) | Turn an approved brief into execution items, classify a small item, or reclassify after a failure. |

## Follow the workflow

1. Run `setup-ai-first` once in the target repository.
2. Use `update-ai-first-capabilities` when the team has capabilities to register. This is optional: the default empty manifest supports classification on raw scores.
3. Explicitly invoke `groom` with a request or tracker item.
4. Resolve open decisions and obtain human approval: another person by default, or yourself when setup has configured your solo identity.
5. Explicitly invoke `decompose-and-classify` with the approved item.
6. Execute each resulting item according to its tier and contract. Use reclassify mode after a failed verification cycle.

For a small, low-blast-radius change with one outcome and a machine-checkable definition of done, use the [single-item path](decompose-and-classify.md#classify-a-small-item-directly).

## Invoke a skill

The examples use Codex syntax. Replace placeholder IDs, paths, and commands with values from your project.

| Client | Example |
|---|---|
| Codex | `$groom #123` |
| Claude Code | `/groom #123` |
| GitHub Copilot | `Use the groom skill on issue #123.` |

`groom` and `decompose-and-classify` require explicit human invocation. Their handoffs do not automatically start the next skill.

## Project configuration is authoritative

The workflow reads the target repository's `.ai-first/` files. Its configured large, regular, and small terms replace generic examples such as Epic, Issue, and Sub-issue. Display names do not change the machine schema.

The guides explain usage; the [skill sources](../skills/) define behavior. The installed `.ai-first/ai-first-schema.md`, `tracker.md`, and capability manifest govern each project. Setup installs contract files and can bootstrap labels; tracker enforcement and PR pipeline integration are separate work. See the [enforcement specification](../assets_ai_first/plugin-workflow-spec.md).
