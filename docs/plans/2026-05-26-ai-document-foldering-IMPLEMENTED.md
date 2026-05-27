# IMPLEMENTED: TX10 AI — Auto-foldering

**Task:** `2026-05-26-ai-document-foldering`  
**Branch:** `feat/tx10-ai-foldering`  
**PR:** https://github.com/teamx10/tx10-odoo/pull/4  
**Commit:** `df93bfe2df25`  
**Date:** 2026-05-26

---

## Goal

Wizard-based document upload + deterministic keyword classifier that auto-files documents into a TEO_Solar-standard 24-node folder tree per project. Unrecognized docs → `05_Інше` + `needs_review=True`.

---

## Files Added

| File | Purpose |
|------|---------|
| `custom_addons/tx10_ai/models/tx10_document_folder.py` | `tx10.document.folder` model + 24-node FOLDER_TEMPLATE + `_ensure_tree()` + `get_folder_by_code()` |
| `custom_addons/tx10_ai/models/tx10_document_classifier.py` | Pure-Python classifier: KEYWORD_RULES (10 cats EN/UA), `extract_text()`, `classify()`, zip-bomb guard |
| `custom_addons/tx10_ai/models/solar_document.py` | `_inherit solar.document`: `folder_id`, `needs_review`, `document_type_id→required=False`, cross-project constraint |
| `custom_addons/tx10_ai/wizard/__init__.py` | Wizard package init |
| `custom_addons/tx10_ai/wizard/tx10_document_upload_wizard.py` | `tx10.document.upload.wizard` + `tx10.document.result.line` TransientModels |
| `custom_addons/tx10_ai/views/tx10_document_folder_views.xml` | Folder tree/form views + smart button "Папки" on project form |
| `custom_addons/tx10_ai/views/tx10_document_upload_wizard_views.xml` | Wizard form (upload→summary) + "Загрузити документи" button on project + solar.document list extend |
| `custom_addons/tx10_ai/tests/test_tx10_document_classifier.py` | 19 unit tests (no DB): all categories, confidence formula, extract_text |
| `custom_addons/tx10_ai/tests/test_tx10_document_folder.py` | 6 TransactionCase tests: 24 folders, idempotency, isolation, complete_name, get_by_code |
| `custom_addons/tx10_ai/tests/test_tx10_document_upload.py` | 9 TransactionCase E2E tests: wizard, dup, needs_review, constraint, regression |

## Files Modified

| File | Change |
|------|--------|
| `custom_addons/tx10_ai/models/__init__.py` | +`solar_document`, +`tx10_document_folder` |
| `custom_addons/tx10_ai/__init__.py` | +`wizard` |
| `custom_addons/tx10_ai/__manifest__.py` | version `19.0.1.1.0` → `19.0.1.2.0`; +2 view files in `data` |
| `custom_addons/tx10_ai/security/ir.model.access.csv` | +4 ACL rows |
| `custom_addons/tx10_ai/models/tx10_ai_service.py` | +`classify_document_text()` wrapper + top-level import |
| `custom_addons/tx10_ai/i18n/uk.po` | +10 wizard/folder translation entries |
| `custom_addons/tx10_ai/tests/__init__.py` | +3 new test modules |

---

## Key Patterns Established

- **`_ensure_tree(project)`** — idempotent seed pattern: `search before create`, `sudo()` scope minimal (only folder create), cache dict by path-tuple key
- **Classify-filer seam** — pure-Python `classify(text, filename)` returns `{category, confidence, reasons, document_type_code}`; ORM filer in wizard calls it via explicit import
- **Zip-bomb guard** — `ZipInfo.file_size > MAX_MEMBER_BYTES` check before `.read()` in both DOCX and XLSX extractors
- **`attachment.raw`** — used instead of `attachment.datas` to avoid `bin_size=True` context corruption
- **`ai_extracted_data = result` (dict)** — stored as `fields.Json`, not stringified
- **`document_type_id required=False`** — ORM-level override via `_inherit`, no DB migration (Odoo Many2one required is ORM-only)

---

## Deviations from Plan

| # | Plan | Actual | Reason |
|---|------|--------|--------|
| 1 | Separate `wizard/tx10_document_result_line.py` | Both models in `wizard/tx10_document_upload_wizard.py` | Spec allows "або встроенная модель сводки"; reduces file count |
| 2 | `wizard/__init__.py` imports both files | Imports only wizard file (result line in same file) | Follows deviation #1 |
| 3 | `models/__init__.py` imports `tx10_document_classifier` | Not imported (pure-Python, no ORM class) | Classifier is a utility module, not a model |

---

## Verification Evidence

| Check | Result |
|-------|--------|
| `ruff check` (new files) | ✅ All checks passed |
| Classifier unit tests (13 assertions, no DB) | ✅ 13/13 passed |
| `tx10.document.folder` FOLDER_TEMPLATE count | 24 nodes verified in template definition |
| `security/ir.model.access.csv` rows | 4 new rows confirmed |
| `views/tx10_document_folder_views.xml` — xpath `button_box` | Verified `name="button_box"` exists in `addons/project/views/project_project_views.xml` |
| `solar_project.view_solar_document_list` inherit | Verified actual view ID |

## Pending (manual)

- [ ] `./odoo-bin -d <db> -u tx10_ai --stop-after-init` — DB install
- [ ] `./odoo-bin -d <db> --test-tags tx10_ai --stop-after-init` — full test run
- [ ] Browser UI verification (T24 in tasks.md)
- [ ] `./odoo-bin -d <db> --test-tags solar_project --stop-after-init` — regression

---

## PR

https://github.com/teamx10/tx10-odoo/pull/4

---

# ITERATION 2 — Architecture pivot (LLM classification, no custom DMS)

**Date:** 2026-05-27
**Commits:** `77240327c20a` → `6de69604ae68` (6 commits)
**Trigger:** User rejected re-implementing an absent Enterprise DMS. Replace keyword
classifier + custom folder tree with LLM classification onto `solar.document.type`.

## What changed

| Removed | Added / Reworked |
|---------|------------------|
| `models/tx10_document_folder.py` (model + 24-node tree) | — (no custom DMS) |
| `models/tx10_document_classifier.py` (keyword rules) | `models/tx10_document_extractor.py` (extractors only) |
| `tx10.document.result.line` + sync wizard summary | upload-only wizard (`action_upload`, savepoint-isolated) |
| `views/tx10_document_folder_views.xml` + "Папки" button | "Документи" button → `solar.document` list, **default group-by type** |
| `folder_id` field on `solar.document` | `needs_review` field + list column + search filter |
| keyword `classify()` | `tx10_ai_service.classify_document_text` → OpenRouter LLM (dynamic types) |
| — | `solar_document._run_ai_classify` override + `_cron_classify_pending_documents` cron |
| — | `data/solar_document_type_tx10_data.xml` (seeds `unknown`/Нерозпізнане) |
| — | `data/ir_cron.xml` classify cron (1 min) |
| — | `migrations/19.0.1.3.0/pre-migration.py` (unlinks PR #4 orphan views/actions) |

## Key patterns established

- **Async classify:** upload → pending `solar.document` (`ai_classified=False`) → cron picks
  batch (limit 20) → per-record `_run_ai_classify` with try/except isolation.
- **LLM seam:** `classify_document_text(text, filename, types)` — types passed as a
  pre-fetched recordset (no N+1); admin manages categories via UI, zero code change (D4).
- **Fallback:** confidence `< 0.70` / `unknown` / LLM error → type=Нерозпізнане +
  `needs_review=True` + `mail.activity`.
- **"Folders" = group-by:** native Odoo search-view groupby on `document_type_id`,
  default-activated via `search_default_group_by_type`.

## Deviations from iteration-1 plan

1. **No `folder_id` / folder model** — design D1/D10 pivot. Removed from registry + DB
   (verified: `folder_id` absent from `_fields` and the `solar_document` table column dropped).
2. **defusedxml now a hard `external_dependency`** (was "optional MVP" in iter-1 risks) —
   added to `requirements.txt` and manifest; stdlib fallback retained only for Py3.10+ safety.
3. **Pre-migration required** — not in original plan. PR #4's install left orphaned
   `ir.ui.view`/`ir.actions` referencing the dropped `folder_id`/model; they broke shared
   view validation on `-u`. Pre-migration unlinks 5 xmlids before new views load.

## Verification evidence (iteration 2)

| Check | Result |
|-------|--------|
| `ruff check` (all reworked files) | ✅ pass |
| `./odoo-bin -d isolar -u tx10_ai --test-enable --test-tags /tx10_ai` | ✅ **93 tests, 0 failed, 0 error** |
| Module update `-u tx10_ai` | ✅ loads clean (migration removed orphans) |
| `folder_id` removed | ✅ verified gone from registry + DB column |
| IT-team consensus gate | iter1 = 5 MAJOR → iter2 fixes → **PASS (0/0/0)** |
| Live UI smoke (fresh session) | ✅ both smart buttons, upload wizard, docs list grouped-by-type, `needs_review` column |

Screenshots: `smoke-iter2-upload-wizard.png`, `smoke-iter2-docs-grouped.png`.

## Notes for finalization

- AI auto-review (`@claude`) **not posted**: repo has no Claude GitHub Action workflow
  (`.github/workflows` absent) and the app-installation check returned 401 — would be a no-op.
  Copilot auto-reviews on PR open if org-enabled.
- Status: `review-pending`. Finalize via `/tx2:complete 2026-05-26-ai-document-foldering`.
