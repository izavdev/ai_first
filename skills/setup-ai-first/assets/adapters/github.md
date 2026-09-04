# Tracker adapter: GitHub Issues

Resolves `ai-first-schema.md`'s tracker-neutral terms to GitHub Issues. Read this alongside the schema before a skill session writes anything to GitHub.

Prefer connected GitHub tools when they expose the required issue, event, and relationship operations. Otherwise use the `gh` CLI from the target repository. Infer the repository from its remote unless the user provides another repository explicitly.

## Vocabulary

| Schema term | GitHub concept |
|---|---|
| item | GitHub issue |
| label | GitHub issue label |
| linked document | Repository document, issue, discussion, or other stable URL |

Use the large, regular, and small names from `.ai-first/terminology.md`. They are workflow roles, not requirements for GitHub issue types. Use native issue types when the organization has configured suitable ones; otherwise all three roles may be plain GitHub issues distinguished by hierarchy and context.

## Fetching and creating items

- Fetch: `gh issue view <number> --json number,title,body,author,labels,url`.
- Create: `gh issue create --title <title> --body-file <file>`.
- Update the body without shell-quoting multiline Markdown: write it to a temporary file, then use `gh issue edit <number> --body-file <file>`.

Use equivalent GitHub MCP operations when available. Resolve a URL or `#123` to its repository and issue number before mutating it.

## Labels

GitHub label changes are additive and subtractive; they do not replace the full label set.

- Add: `gh issue edit <number> --add-label <label>`.
- Remove: `gh issue edit <number> --remove-label <label>`.

Read the current labels before enforcing the exactly-one-tier-label invariant.

## Linked documents

`brief-url:` may point to a versioned repository document, GitHub issue, GitHub discussion, or another stable document URL. Use `inline` when the brief lives in the issue body above the `[ai-first:v1]` block. Prefer a repository path or permalink over copying a document into the issue.

## Comments

Post comments with `gh issue comment <number> --body-file <file>` or the equivalent GitHub tool. Use a temporary file for multiline or machine-prefixed comments so shell interpolation cannot alter their contents.

## Hierarchy and dependencies

Create decomposed work as issues and link each one as a native sub-issue of the parent when sub-issues are available:

1. Create the child issue.
2. Fetch the child's numeric database ID with `gh api repos/{owner}/{repo}/issues/{child-number} --jq .id`.
3. Add it with `gh api --method POST repos/{owner}/{repo}/issues/{parent-number}/sub_issues -F sub_issue_id={child-database-id}`.

Represent blocking relationships with GitHub's native issue dependencies when available. Add a blocker with `gh api --method POST repos/{owner}/{repo}/issues/{blocked-number}/dependencies/blocked_by -F issue_id={blocker-database-id}`.

If the repository does not support either feature, use an explicit `Part of #<parent>` line and `Blocked by: #<number>` lines in issue bodies. Do not silently omit relationships.

## Approval-identity check

The current `brief-approved` label and its actor are verified from GitHub issue events:

1. Fetch the issue and confirm `brief-approved` is currently present. Record the creator from `author.login` (REST field: `user.login`).
2. Fetch all issue events with `gh api --paginate repos/{owner}/{repo}/issues/{number}/events` or an equivalent GitHub tool.
3. In chronological order, find events whose label name is `brief-approved` and whose event is `labeled` or `unlabeled`. The last matching event must be `labeled`.
4. Its `actor.login` is the approver. It must be present, must differ from the issue creator, and must represent an identifiable user. If the event is missing or cannot be attributed, approval is invalid.

On failure, post `[ai-first] BLOCKED:` with the exact remediation and stop. Never infer the approver from comments, assignees, reviewers, or the current viewer.

## Description block delimiter

GitHub issue Markdown preserves the schema's `---` delimiters. Write and parse the description block exactly as specified in schema section 2.3.

## Label bootstrap

GitHub labels must exist before they can be assigned. One-time repository setup creates:

`ai-first`, `groomed`, `brief-approved`, `ai-delegate`, `ai-pair`, `human-only`, `ai-escalated`.

List existing labels first and create only missing labels with `gh label create`. Label creation changes the repository and requires explicit approval immediately before execution.
