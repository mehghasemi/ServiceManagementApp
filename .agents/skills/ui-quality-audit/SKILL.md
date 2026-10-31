---
name: ui-quality-audit
description: Audit ServiceManagementApp interface changes for visual consistency, responsive Persian RTL, accessibility and grid/dashboard regressions with reproducible evidence.
---

# UI quality audit

## Workflow
1. Read root AGENTS.md and [design system](../../../docs/design-system.md). Inspect git diff; separate pre-existing changes from the current task.
2. Select affected routes, roles, shared components and states. Review actual rendering in isolated development when available; never use production mutations as test setup.
3. Check 360/768/1440 widths, both themes, 200% zoom, keyboard focus, accessible names, dialog return focus and reduced motion. Measure contrast rather than inferring it from screenshots.
4. For charts check text equivalents, scope and drill-down counts. For tables check sorting/paging and saved preferences. For forms check retained input, labels, errors and server permission denial where affected.
5. Report each defect with severity, route/file, reproduction, expected/actual result and impact. Fix only when requested or included in the task; rerun affected checks after corrections.

## Acceptance
- Findings are reproducible and distinguish measured failures from suspected risks.
- Test report separates automated rendering from browser/keyboard verification.
- Untested states and unavailable tools are explicit; no blanket WCAG/ASVS claim.
- Synthetic evidence only in tracked files; no customer records or credentials.
- An audit does not itself authorize release activation or unrelated redesign.
