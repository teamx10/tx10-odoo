# IMPLEMENTED: iSolar MVP — Solar Site presales-контур

**Date:** 2026-05-31
**Branch:** feat/isolar-solar-site-mvp
**Plan:** elegant-seeking-lobster.md

## Goal

Новий Odoo 19 модуль `solar_site` — presales-контур CRM Lead → Solar Site → Remote Assessment → Qualify Site → Ready for Proposal для клієнта iSolar.

## Files Created

```
custom_addons/solar_site/
├── __manifest__.py
├── __init__.py
├── models/
│   ├── __init__.py
│   ├── solar_site.py          # solar.site: 20+ fields, 9 action-методів, compute потенціалу
│   ├── solar_roof_plane.py    # solar.roof.plane: площини даху з shading risk
│   ├── crm_lead.py            # _inherit crm.lead: Create/Link/Open Site, дубль-чек
│   └── res_config_settings.py # 7 config_parameter defaults
├── wizard/
│   ├── __init__.py
│   └── link_solar_site.py     # solar.site.link.wizard
├── data/
│   ├── crm_stage_data.xml     # 8 CRM стадій + ir.sequence SS#####
│   └── config_params.xml      # defaults: 580Вт/2.6м²/60%/1100 kWh
├── security/ir.model.access.csv
├── views/
│   ├── solar_site_views.xml
│   ├── solar_roof_plane_views.xml
│   ├── crm_lead_views.xml     # inherit + Solar Site tab + smart button
│   ├── res_config_settings_views.xml
│   ├── link_solar_site_views.xml
│   └── menus.xml
├── demo/solar_site_demo.xml   # Петренко Іван — Буча §22
├── i18n/uk.po
└── tests/test_solar_site_flow.py  # 7 acceptance тестів
```

**docker-compose.yml** — додано `solar_site` до install-списку.

## Key Patterns Established

- `solar.site` — standalone модель (не fsm.location), inherits mail.thread + mail.activity.mixin
- Sequence `SS#####` через `ir.sequence.next_by_code`
- Compute-поля потенціалу: `floor(usable_area * utilization / panel_area)` → panels → DC kWp → kWh/year
- Shading risk = max() по площинах (через SHADING_ORDER dict)
- Sync лідів: `_sync_lead_stage(xmlid)` — оновлює стадії linked leads
- Activity автоматизація в `action_qualify_site` та `action_engineer_visit_needed`

## Deviations from Plan

| # | Планувалось | Зроблено | Причина |
|---|------------|----------|---------|
| 1 | `probability` в crm.stage | Видалено | В Odoo 19 поле відсутнє |
| 2 | `right_column` xpath в CRM form | Solar Site tab в notebook | `right_column` не існує в Odoo 19 |
| 3 | `%(action_id)d` в stat button | `action_view_crm_leads()` метод | Forward reference error при завантаженні XML |
| 4 | `expand="0"` в search group | `colspan="16"` | Odoo 19 синтаксис |

## Verification Evidence

### Tests (7/7 passed)
```
odoo.tests.result: 0 failed, 0 error(s) of 7 tests
solar_site: 9 tests 0.25s 503 queries
```

### UI Smoke §22 — всі кроки пройдено
| Крок | Результат | Скріншот |
|------|-----------|---------|
| Створити лід Петренко — Буча | ✅ | smoke-solar-02-new-lead.png |
| Create Solar Site → Remote Assessment | ✅ | smoke-solar-03-site-created.png |
| Open Satellite View (URL відкрито) | ✅ | smoke-solar-04-satellite-buttons.png |
| Add Roof Plane 80/55/SW/25°/Medium | ✅ | — |
| Recalculate: 12 panels / 6.96 kWp / 7,656 kWh | ✅ | smoke-solar-05-potential.png |
| Qualify Site → Ready for Proposal | ✅ | smoke-solar-06-qualified.png |
| Lead в стадії Ready for Proposal | ✅ | smoke-solar-07-lead-ready-for-proposal.png |

### Gates
- `ruff check custom_addons/solar_site/` → **All checks passed**
- `gitnexus_detect_changes` → **Risk: LOW**, 0 affected existing processes
