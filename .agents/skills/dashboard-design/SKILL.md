---
name: dashboard-design
description: Compose ServiceManagementApp managerial dashboards and select chart types for KPIs, category comparisons and time series with consistent record drill-downs.
---

# Dashboard design

## Workflow
1. Read [design system](../../../docs/design-system.md), [visual workspace](../../../docs/visual-workspace.md) and [personal dashboards](../../../docs/personal-dashboards.md).
2. Trace each metric to its source, unique counting unit, filter, time meaning and coverage. Identify the management question before selecting a chart.
3. Use bars for comparisons, stacked bars only for compatible partitions, and line/area only for genuine ordered time observations. Limit pie/ring charts to a few meaningful parts of one total. A current snapshot grouped by creation month is not historical workload.
4. Compose compact KPIs, supporting charts and a drill-down list. Reuse server SVG templates and local chart scripts. Small widgets must expose a readable full view rather than shrink labels indefinitely.
5. Preserve saved keys, dimensions, chart options, revisions, ownership and shared publications. Check filters and totals against the record list with synthetic fixtures.

## Acceptance
- Every chart identifies its unit and scope; unknown data is distinct from zero.
- Totals and drill-down records agree under the same filters and permissions.
- Labels/text alternatives accompany colors; long Persian categories remain readable.
- No invented trends, automatic employee ranking or hardcoded evaluation thresholds.
- Empty, partial, many-category and small-widget states are verified in both themes.
