---
name: service-interface-review
description: Review and validate ServiceManagementApp UI changes for Persian RTL, keyboard interaction, contextual help, responsive states and preservation of existing grids and dashboards.
---

# Service interface review

Read the root AGENTS.md and [design system acceptance matrix](../../../docs/design-system.md). Inspect the diff and distinguish pre-existing user changes from this task's edits. Use synthetic records for reproducible checks; never export operational screenshots or customer data into tracked files.

Choose affected routes and user roles from the actual change. For forms check labels, required fields, retained input, inline errors and server denial. For navigation and dialogs check Tab/Shift+Tab, visible focus, Enter/Space, Escape and return focus. Check the skip link and accessible names of icon buttons. Hiding a control does not prove server authorization.

For help, reuse `data-help` and the single `#help-dialog`; verify one explanation per control, accurate criteria, viewport fit and focus restoration. For charts, check keyboard drill-down and an equivalent labeled list. For grids and dashboards, check sorting, filters, pagination, saved layout and keyboard alternatives to dragging only where affected.

Exercise the design system's states at desktop, tablet and narrow mobile widths in both themes. Measure contrast before claiming it passes. Check zoom, reduced motion and long Persian/mixed-direction content. Record route, viewport, theme and reproduction steps for a defect, with expected and observed behavior.

Run targeted Django tests with the isolated settings described in the design system. A render test checks server output, not actual CSS layout, focus trapping or screen-reader announcements. If a browser or suitable synthetic environment is unavailable, mark those checks untested rather than exercising sensitive actions on the stable server.

Return actionable findings with file locations, impact and evidence. When asked to fix issues, make focused corrections and rerun affected checks. Do not claim full WCAG/ASVS compliance from this review.
