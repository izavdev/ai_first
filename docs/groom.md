# How to groom a request

Use `groom` to turn a raw ask or tracker item into an approval-ready brief. Its output is planning material and tracker labels; code implementation and decomposition happen later.

## Before you start

Run [setup-ai-first](setup-ai-first.md). The skill requires `.ai-first/README.md`, `terminology.md`, `ai-first-schema.md`, and `tracker.md`, plus access to the target tracker. Bring the source request, relevant document links, and any known constraints.

## Start with an item or a raw ask

For an existing item:

```text
$groom #123
Use the linked product spec and ADRs to prepare the brief.
```

For a raw ask:

```text
$groom
Request: Add CSV export to the internal inventory page.
Source: <link to the original request>
Constraint: Preserve the existing filters and column order.
```

Raw requests are triaged before grooming:

| Outcome | What happens |
|---|---|
| Investigation | A bounded research pass answers whether work is needed; no item is created initially. Any remaining work is triaged again. |
| Small | An item is created and handed off for explicit classification in single-item mode. It must have one outcome, one touched surface, machine-checkable completion, and zero judgment calls. |
| Large | Split into regular items first and groom each separately. |
| Regular | An item is created and grooming proceeds. |

Created items retain the source ask verbatim and link the original thread when available. An existing `groomed` item requires a re-grooming decision; re-grooming clears existing approval and requires fresh approval.

## Work through the brief

The skill checks the item and linked documentation before asking focused questions in this order:

1. **Destination:** describe the finished outcome in one or two sentences.
2. **Constraints:** identify deadlines, compatibility requirements, budgets, and relevant standards.
3. **Touched surfaces:** name services, contracts, data, and especially public APIs, authentication, and migrations.
4. **Definition of done:** provide concrete criteria and identify which are machine-checkable.
5. **Out of scope and human-only work:** state exclusions and any work a human must execute.

Unresolved judgment calls are recorded as open decisions with the person who should decide. Resolve them before decomposition. If more than five remain, split the work into regular items. If the destination cannot be stated, grooming stops and records what is known.

## Check the result

The item description, or its linked brief document, should contain Destination, Constraints, Touched surfaces, Definition of done, Out of scope, Human-only list, and Open decisions. The item also receives:

- A schema block with `kind: brief`, the brief location, grooming date, and actual open-decision count.
- The `ai-first` and `groomed` labels.
- A comment naming a suggested approver and explaining the approval gate.

## Obtain human approval

Have a human review the brief and resolve all open decisions before approving. By default, the approver must differ from the item creator. If setup configured your solo identity, you may review and approve your own brief using that account. See [solo setup](setup-ai-first.md#work-as-a-solo-developer). The skill never applies `brief-approved`.

- **GitHub:** the approver applies `brief-approved`. Classification checks the latest matching label event's actor.
- **Azure DevOps:** the approver adds the `brief-approved` tag. Classification checks the work-item revision that added it.
- **Linear:** the approver adds `brief-approved` and posts a comment containing the literal marker `[ai-first] APPROVED`. Both are required.

Then explicitly invoke [decompose-and-classify](decompose-and-classify.md) with the item ID.

## Troubleshoot

| Situation | Next step |
|---|---|
| Required configuration is missing | Run setup in this repository. |
| Item fetch fails | Correct the ID or restore tracker access before retrying. |
| Request is an obvious one-line fix | Use classification's single-item mode when the small-item conditions hold. |
| Definition of done says only “works well” | Replace it with observable criteria and identify a verification method. |
| Brief is approved but must change | Re-groom explicitly, then obtain fresh approval under the project policy. |

Source: [groom/SKILL.md](../skills/groom/SKILL.md).
