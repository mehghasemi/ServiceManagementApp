---
name: service-interface-design
description: Design or refine ServiceManagementApp Django pages, shared components, typography, light/dark themes and responsive Persian RTL layouts. Use for interface implementation, not backend-only changes.
---

# Service interface design

Read the root AGENTS.md, [design system](../../../docs/design-system.md), and affected feature specification. All source paths below are relative to the repository root.

Start from the user's action: identify the decision, evidence, primary action and empty/error behavior. Inspect the actual page and its shared includes before choosing layout. Preserve the compact service-management workspace and progressive disclosure of record evidence.

Extend `templates/base.html` and reuse `.page-heading`, `.panel`, `.button`, `.filters`, `.notice`, `.table-wrap` and the shared help dialog when appropriate. Inspect `static/app.css`, `workspace.css`, `dashboard-design.css`, `visual-workspace.css` and the feature stylesheet in load order; later rules override earlier defaults. Do not add a parallel theme or a second tooltip system.

Use existing semantic custom properties for surfaces, text, borders and actions. Check both `[data-theme=dark]` and light mode. Prefer logical CSS properties and scoped selectors. Keep Vazirmatn local, Persian labels professional and identifiers isolated with `bdi` or `dir="ltr"`. Do not mirror data axes or numbers just because the surrounding page is RTL.

Keep Django escaping and CSRF protection. Use existing external scripts and CSP-compatible patterns; do not weaken CSP for inline event handlers or chart styles. Presentation must not calculate new business classifications or grant permissions.

Implement the smallest coherent change. Verify the acceptance scenarios in the design system, including saved layouts and narrow screens where relevant. With behavior changes, update feature help, the affected specification and append-only release history. Report changes, evidence and untested cases; never activate a stable release as part of visual iteration.
