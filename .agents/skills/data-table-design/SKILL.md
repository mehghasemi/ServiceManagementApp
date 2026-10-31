---
name: data-table-design
description: Design or refine ServiceManagementApp data grids with compact rows, separate business columns, persisted column preferences, sorting and pagination.
---

# Data table design

## Workflow
1. Read [design system](../../../docs/design-system.md), affected feature specification and existing static/grid.js, static/grid.css and grid preference handlers.
2. Define separate columns for customer, title, status, dates and relevant source fields. Avoid stacking unrelated fields into one cell. Keep stable column identifiers.
3. Use compact consistent row heights and ellipsis for long values with an accessible full-value path. Keep action names available to assistive technology; use buttons for refresh and links for navigation.
4. Preserve sorting, search and filters across pagination. Verify whether sorting is server-wide or only page-local; do not present page-local ordering as complete-dataset ordering.
5. Preserve resize, visibility and order preferences per user/table. New columns need safe defaults; resetting preferences must be explicit. Provide keyboard alternatives to drag-only controls.
6. Check empty/loading/error states, long Persian values, mixed IDs, narrow viewports and preference persistence with synthetic records.

## Acceptance
- Customer and title are separate; long text does not arbitrarily inflate row height.
- Headers describe data, sorted direction is accessible, filters survive paging.
- Resizing/reordering/hiding persists without corrupting other users or tables.
- Essential record actions and full text remain reachable by keyboard.
- Horizontal overflow is contained in the table, not the whole document.
