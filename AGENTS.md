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
- Local preview and read-only CRM View integration are implemented. Read docs/crm-planning.md for current scope and docs/preview.md for the earlier synthetic prototype. Network deployment, organizational roles and PostgreSQL are not implemented; do not expose the preview to the LAN. CRM records and local actions stay under ignored private/.
