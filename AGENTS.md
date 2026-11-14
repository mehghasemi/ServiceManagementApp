# Development contract

- Read README.md, docs/user-requirements.md, docs/design-v1.md and relevant feature specifications before changes.
- This is a new independent product; do not copy the old application wholesale. Reuse only reviewed, tested and compatible logic.
- Product purpose is service quality improvement and fair evidence-based review. Missing data is not employee failure. Never equate elapsed case time with actual work or CRM Done with customer-confirmed resolution.
- Preserve user changes. Inspect git status first. No commit or push without explicit user instruction.
- Keep code, UI, business rules, integrations and persistence separated. Enforce both operation permissions and object scope on the server.
- All user-visible UI is professional Persian, RTL, accessible by keyboard, with local Vazirmatn assets and contextual help. Follow the complete user requirements, not only this summary.
- No production data, customer records, credentials, tokens, exports or backups in this public repository. Use synthetic fixtures.
- Update feature help, affected contracts and append-only release history with behavior changes. Run relevant checks; report what actually ran and what did not.
- Do not claim WCAG or ASVS compliance without documented verification. Keep pending criteria explicit.
- CRM is read-only in the first release. Local planning decisions must survive synchronization.
- Business evaluation rules must use the shared saved criteria mechanism: user-selectable activation, conditions, thresholds, priority and grouping. Do not add hardcoded business classifications; preserve source-identity and security invariants. See docs/criteria.md.
- Local preview and read-only CRM View integration are implemented. Read docs/crm-planning.md for current scope and docs/preview.md for the earlier synthetic prototype. Authenticated limited LAN pilot is implemented in run_lan.py; see docs/network.md. Never expose passwordless run_preview.py to the LAN. Team scoping, PostgreSQL and HTTPS remain pending. CRM records and local actions stay under ignored private/.

- Develop using runtime.py development (isolated DB/port). Never edit private/releases or stop the user's stable server for development. Preparing a release does not activate it; see docs/development-runtime.md.

## Project UI guidance

- For UI work, read [the design system](docs/design-system.md) and the affected feature specification. Inspect the current template, CSS cascade and JavaScript before editing. README.md and current feature specifications describe implementation; docs/design-v1.md also contains historical proposals, not completed features.
- Keep the existing Django templates, plain JavaScript, local CSS and local fonts. Do not introduce a frontend framework, CDN or build pipeline solely to restyle a page.
- Use the relevant repository skill; paths are relative to this repository, not a personal skills installation:
  - [.agents/skills/service-interface-design/SKILL.md](.agents/skills/service-interface-design/SKILL.md): page composition, components, typography, themes and responsive layouts.
  - [.agents/skills/service-data-visualization/SKILL.md](.agents/skills/service-data-visualization/SKILL.md): charts, KPI meaning, source coverage and drill-downs.
  - [.agents/skills/service-interface-review/SKILL.md](.agents/skills/service-interface-review/SKILL.md): keyboard, RTL, help, states and visual regression verification.
- Reuse existing semantic tokens and shared components. Keep light/dark themes, saved grid/dashboard layouts, source identity, permissions and filter scope intact. New visual colors must not introduce evaluation rules.
- Use the targeted checks and manual acceptance matrix in docs/design-system.md. Report actual results and remaining gaps; passing template tests does not establish browser accessibility.
- Setup and invocation examples are in [docs/codex-project-guide.md](docs/codex-project-guide.md).

### Focused design skills

Select the smallest relevant skill set; do not load every UI skill for every change. The existing service-* skills remain valid implementation guides. These focused skills share docs/design-system.md rather than defining competing standards:

- [.agents/skills/enterprise-ui-design/SKILL.md](.agents/skills/enterprise-ui-design/SKILL.md): enterprise page hierarchy, shared components and interaction states.
- [.agents/skills/dashboard-design/SKILL.md](.agents/skills/dashboard-design/SKILL.md): dashboard composition and chart selection.
- [.agents/skills/persian-rtl/SKILL.md](.agents/skills/persian-rtl/SKILL.md): Persian typography, bidirectional content, dates and RTL interaction.
- [.agents/skills/data-table-design/SKILL.md](.agents/skills/data-table-design/SKILL.md): dense tables, column preferences, sorting and pagination.
- [.agents/skills/ui-quality-audit/SKILL.md](.agents/skills/ui-quality-audit/SKILL.md): evidence-based UI acceptance and regression review.

Design-system targets are acceptance requirements for affected work, not proof that every existing page already complies. Documentation or skill installation alone does not authorize page redesign or production activation.

For every change affecting a user workflow, including save errors and return navigation, apply the [Persian desktop workflow criteria](docs/design-system.md#desktop-workflow). Identify the user task and verify the affected acceptance scenario before delivery. The owner requires an explicit release request before issuing a new version or activating production.
