---
name: service-data-visualization
description: Create or change ServiceManagementApp dashboards, KPI cards, chart encodings and record drill-downs while preserving CRM source meaning and saved evaluation criteria.
---

# Service data visualization

Read the root AGENTS.md, [design system](../../../docs/design-system.md), [visual workspace](../../../docs/visual-workspace.md), and the relevant feature specification. For configurable widgets also read [personal dashboards](../../../docs/personal-dashboards.md); for evaluation read [criteria](../../../docs/criteria.md).

Trace each displayed value from source selection and scope through filters and aggregation to its template. Inspect `planning/templatetags/dashboard_visuals.py`, `templates/visuals/` and the relevant view/service. Reuse the existing chart representation and local rendering; a chart library is not required to add a chart.

State the unit, denominator, time meaning, source, receipt freshness and coverage. Distinguish Issue, Backlog, customer and local action counts. A missing receipt, an empty successful receipt, partial notes and a genuine zero are different states. Do not infer historical workload from creation dates of the current snapshot.

Categorical `--series-*` and `--viz-*` colors distinguish categories, not employee performance. Use labels and a text/list alternative. Do not invent progress, closure rates or rankings when evidence is missing. CRM Done is not customer-confirmed resolution; elapsed case age is not actual work. Any evaluation threshold, activation or grouping must come from saved criteria, not CSS or JavaScript.

Keep charts and linked records on the same filter/source scope; preserve filters in drill-down URLs. Use actual links/buttons for interactive marks and a keyboard-accessible legend or record list. Keep saved widget keys, allowed chart types, revisions, ownership and publication permissions stable when restyling.

Validate empty/all-zero, unknown category, long Persian labels, many categories, partial data and changed filters with synthetic fixtures. Run the matching chart/presentation tests from the design system, then inspect both themes and narrow layouts in a browser when rendering changes. Report any untested browser or accessibility behavior explicitly.
