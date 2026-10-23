# Worker prompt template

Copy for a new worker. Keep it short: the questions live in the dossier, not here.

```markdown
# <id> worker

**Owns:** `hardware/<id>/` (write). Everything else is read-only.
**Phase:** <n>. **Kernel worktree:** yes/no.

## Mission
<one paragraph: what "done" means for this component>

## Start
1. Read `hardware/<id>/README.md` and `component.toml`.
2. Read the dossiers you depend on (`depends_on`).
3. Work the open questions in the dossier in order, following `agents/protocol.md` §9.

## Specific leads
- <files, functions, ACPI devices, upstream series to look at first>

## Deliver
- <patches, test plan, evidence files expected>

## Do not
- <component-specific limits, safety rules>
```
