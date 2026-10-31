---
name: enterprise-ui-design
description: Design ServiceManagementApp enterprise page hierarchy, shared components and interaction states when composing or refining management screens and forms.
---

# Enterprise UI design

## Workflow
1. Read root AGENTS.md, [design system](../../../docs/design-system.md), and the affected feature specification. Inspect the actual Django template, includes, CSS load order and external JavaScript.
2. Define the user's decision, primary action and supporting evidence. Prefer a compact summary followed by optional detail; avoid duplicated toolbars and explanatory paragraphs.
3. Reuse existing panels, forms, navigation and help dialog. Keep local Vazirmatn, semantic tokens, both themes and progressive enhancement. Scope selectors; do not introduce a second component framework.
4. Specify loading, empty, unknown, partial, error, success and no-access states before implementation. Preserve input after errors and provide keyboard-operable controls.
5. Validate affected routes in isolated development using the design-system acceptance matrix. Document remaining gaps; retain existing preferences and authorization boundaries.

## Acceptance
- Primary action and source status remain visible without dominating the page.
- At 360, 768 and 1440 pixels and 200% zoom, essential controls remain usable; no document-level horizontal overflow.
- Light/dark surfaces and focus are readable; labels and error recovery work with keyboard.
- No changes to business meaning, APIs, source scope or production runtime solely for styling.
- Changes reuse the current stack and include actual verification evidence.
