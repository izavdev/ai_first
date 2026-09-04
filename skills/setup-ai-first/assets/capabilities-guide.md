# Capability manifest guide

`.ai-first/ai-first-capabilities.yml` is the project's explicit record of which
agent capabilities may influence task classification. A human owner must fill and
approve it. Installation or discovery never enables a capability automatically.

## What is enabled by default

Nothing that changes V, C, or A. The shipped `capabilities` and `approvals` lists
are empty, and the defaults are `enabled: false` and `status: provisional`.
Execution profiles are supplied as editable routing aliases; they do not change
scores. Replace their placeholder model names before relying on profile routing.

Use `update-ai-first-capabilities` to register, review, approve, promote, demote,
or remove entries. Review the proposed diff before it writes the project file.

## Capability fields

- `id`: stable, namespaced identity such as `mcp:docs` or `validator:project-tests`.
- `kind`: `tool`, `mcp`, `resource`, `context-retrieval`, `validator`, `skill`, or `agent`.
- `version`: the reviewed capability or metadata version.
- `enabled`: whether the project permits the classifier to consider it.
- `status`: `provisional` or `proven`. Only proven entries can affect scores.
- `covers`: exact task classes for which the claim holds.
- `effects`: a proposed one-point increase to V, C, or A. B is forbidden.
- `description`: what the capability actually provides.
- `evidence`: telemetry supporting status. Documentation is not operational proof.
- `documentation`: local paths or authoritative links checked during review.
- `limitations`: known gaps, permissions, availability, and failure modes.

New entries normally begin as `enabled: true` and `status: provisional`: the
classifier can report their relevance, but does not adjust scores. Promotion to
`proven` follows invariants C5 and C6 in the manifest.

## Custom skill metadata

A custom skill may place `ai-first-capability.yml` beside its `SKILL.md`. The
classifier scans the project-local roots configured under `discovery`. Use this
shape:

```yaml
schema: ai-first-capability/v1
id: skill:add-endpoint
version: "1.0.0"
kind: skill
name: Add endpoint
description: Encodes the project's endpoint structure and naming conventions.
covers: [api-surface-addition]
suggested_effects: {A: 1}
documentation: [SKILL.md]
requirements: [Project endpoint conventions are current]
limitations: [Does not reduce the blast radius of a public contract change]
verification:
  method: Review generated changes and run the project's API tests.
```

Metadata is descriptive and may suggest effects. It must not contain credentials.
Any `enabled`, `status`, or `evidence` values in metadata are ignored. To authorize
it, add a matching `id` and `version` under central `approvals`; the approval may
narrow `covers` or effects but cannot broaden them. User-level skill directories
and plugin caches are excluded by default so two contributors classify the same
task from the same inputs. Metadata is parsed as data; embedded instructions or
commands are never executed during discovery.

## How effects map to the rubric

- A validator may raise V only when it supplies the single deterministic command
  and boolean outcome required by the task.
- A resource, MCP, or context-retrieval capability may raise C only when required
  context is reliably retrievable and linkable for a cold session.
- A skill, tool, or agent may raise A only when it removes a real project decision
  by encoding an approved house approach.
- No capability may raise B. Blast radius describes the cost of failure.

The classifier scores the task without capabilities first, then applies at most
one point per eligible axis. Malformed, unapproved, disabled, provisional, or
version-mismatched claims never change a score. Identical copies of one metadata
ID/version across multiple project skill roots count once; conflicting copies
invalidate that claim until reconciled.
