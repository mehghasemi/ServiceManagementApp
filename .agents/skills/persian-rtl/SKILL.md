---
name: persian-rtl
description: Implement or review Persian RTL presentation in ServiceManagementApp including mixed-direction identifiers, Jalali dates, typography and keyboard order.
---

# Persian RTL

## Workflow
1. Read [design system](../../../docs/design-system.md) and inspect templates/base.html, local font assets and existing service_ui formatters before introducing formatting.
2. Keep lang="fa-IR" and dir="rtl" at the document root. Use professional Persian labels, local Vazirmatn and logical CSS properties.
3. Isolate CRM identifiers, URLs and mixed-direction values using bdi or an explicit LTR span. Preserve raw IDs and sortable values; localize display separately.
4. Display dates through existing Jalali/timezone formatters. Do not modify stored timestamps, API contracts or source text to fix display.
5. Verify menus, dialogs, tables, long labels and chart axes with keyboard and narrow screens. Mirror directional navigation only when its meaning requires it; never blindly reverse numbers, time axes or icons.

## Acceptance
- Persian and Latin text coexist without punctuation/identifier reordering.
- Local font loads without a CDN; controls inherit the font.
- Dates use the existing Persian display contract, with time meaning intact.
- Visual order and focus order are coherent; no positive tabindex workaround.
- Long labels, 200% zoom and both themes remain usable.
