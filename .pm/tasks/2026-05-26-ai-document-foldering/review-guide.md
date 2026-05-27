# Review Guide — 2026-05-26-ai-document-foldering

**Task:** TeamX10 AI — Auto-foldering: загрузка и автоклассификация документов проекта
**Branch:** `feat/tx10-ai-foldering` (base: `develop`)
**PR:** [#4](https://github.com/teamx10/tx10-odoo/pull/4) → `develop`

> **Iteration 2 — architecture pivot.** PR #4 originally built a custom folder
> DMS (`tx10.document.folder` tree) + a deterministic keyword classifier. That
> approach was rejected: don't re-implement an absent Enterprise DMS. This
> iteration **replaces** it with LLM classification onto the existing
> `solar.document.type` axis + native group-by as the "folder" UX.

---

## What changed vs PR #4 (the pivot)

| Removed (keyword/DMS era) | Added (LLM era) |
|---------------------------|-----------------|
| `tx10.document.folder` model + `FOLDER_TEMPLATE` (24 nodes) | — (no custom DMS) |
| `tx10.document.classifier` (KEYWORD_RULES, confidence formula) | `tx10_ai_service.classify_document_text` → OpenRouter LLM |
| `tx10.document.result.line` + sync wizard summary | Upload-only wizard (async) |
| Folder tree/form views + "Папки" smart button | "Документи" smart button → group-by `document_type_id` |
| `folder_id` field on `solar.document` | `needs_review` field + list column/filter |

Text extractors (`pdf/docx/xlsx/txt`, zip-bomb guard) were **kept** — renamed to
`tx10_document_extractor.py`. They're a utility, not a DMS.

---

## Architecture (async: upload → pending → cron → LLM → type/needs_review)

```
project.project form
  ├─ "Завантажити документи" → upload wizard (multi-file)
  │     └─ action_upload: per attachment (savepoint-isolated)
  │           create solar.document(ai_classified=False, no type)   ← "pending"
  │           dedupe by attachment name + file_size
  └─ "Документи" → solar.document list, default group-by document_type_id  ← "folders"

ir.cron (1 min)  solar.document._cron_classify_pending_documents()
  search([ai_classified=False, attachment_id!=False], limit=20)
    → rec._run_ai_classify()  (override of solar_project stub, per-record try)
        1. extract_text(attachment)         (tx10_document_extractor)
        2. tx10.ai.service.classify_document_text(text, filename, active_types)
             → OpenRouter chat → JSON {document_type_code, confidence, reasons}
        3. confidence ≥ 0.70 and code≠unknown → document_type_id = type(code)
           else → type="unknown" (Нерозпізнане) + needs_review=True + mail.activity
```

---

## Where to look (files)

| File | Role |
|------|------|
| `models/solar_document.py` | `_run_ai_classify` override + `_cron_classify_pending_documents` |
| `models/tx10_ai_service.py:classify_document_text` | LLM prompt (dynamic types) + JSON parse/fallback |
| `models/tx10_document_extractor.py` | text extraction, defusedxml, **streamed** zip-bomb guard |
| `wizard/tx10_document_upload_wizard.py` | upload-only, savepoint per attachment |
| `views/tx10_document_upload_wizard_views.xml` | wizard form, 2 smart buttons, search view (groupby) |
| `data/solar_document_type_tx10_data.xml` | seeds `unknown` type (Нерозпізнане) |
| `data/ir_cron.xml` | classify cron (1 min) |
| `migrations/19.0.1.3.0/pre-migration.py` | unlinks PR #4 orphan views/actions before load |

---

## Reviewer checklist

### Classification flow
- [ ] `_run_ai_classify`: per-record try/except — one LLM failure doesn't abort the batch
- [ ] confidence boundary is `>= 0.70` (tested at 0.70 and 0.69)
- [ ] LLM error / parse error / `unknown` → `needs_review=True` + activity scheduled
- [ ] `classify_document_text`: strips markdown fences, rejects non-numeric confidence → `unknown`/0.0
- [ ] types passed as pre-fetched recordset (no N+1 in cron batch)

### Security
- [ ] zip-bomb guard **streams** `z.open().read(MAX+1)` — does NOT trust `info.file_size` header
- [ ] `defusedxml` is a declared `external_dependency`; stdlib fallback only on Py3.10+ (expat 2.4+ safe)
- [ ] cron uses `sudo()` (system job); wizard respects ACLs (project_user)
- [ ] no secrets — OpenRouter key from `ir.config_parameter`

### Data / migration
- [ ] `folder_id` fully removed (verified: gone from registry + DB column dropped)
- [ ] pre-migration unlinks 5 orphan xmlids before new views load (fixes view-validation crash)
- [ ] `document_type_id` required=False (pending docs have no type)

### Tests (93 pass against live `isolar` DB)
- [ ] `TestTx10DocumentExtractor` (11) — now `TransactionCase`+`@tagged` so CI collects it
- [ ] zip-bomb: header-check path AND streaming-cap path (mocked oversized stream)
- [ ] `TestTx10DocumentUpload` — wizard pending create, dedupe, savepoint isolation, cron paths
- [ ] `TestTx10ClassifyDocumentText` (7) — JSON parse, fences, missing/string confidence, error

---

## Critical Few (attend to first)

1. **LLM cost/latency** — one OpenRouter call per document. Mitigated: async cron, batch limit 20, only text tokens. Watch real-world UA/EN accuracy.
2. **`unknown` type seed** — `needs_review` fallback depends on the `unknown` (Нерозпізнане) `solar.document.type` existing. Seeded via data file; verify it survives on prod update.
3. **pre-migration scope** — runs only on update from <19.0.1.3.0. Fresh installs skip it (no orphans to clean) — confirm that's correct for prod.

---

## Verification evidence

- **93 tests pass** (`./odoo-bin -d isolar --test-enable -i/-u tx10_ai`, 0 failed/0 error).
- **IT-team consensus gate:** iter1 (5 MAJOR) → iter2 fixes → **PASS (0/0/0)**.
- **Live UI smoke** (fresh session): both smart buttons render, upload wizard opens,
  documents list default-grouped by type, `needs_review` column present.
  Screenshots: `smoke-iter2-upload-wizard.png`, `smoke-iter2-docs-grouped.png`.

---

## Open risks / follow-up

| Risk | Status | Follow-up |
|------|--------|-----------|
| LLM accuracy on real isolar docs | Open | tune prompt; `reasons` logged in `ai_extracted_data` for audit |
| LLM JSON robustness | Mitigated | strict prompt + parse fallback → `unknown`+needs_review |
| 12 seed types are lifecycle- not equipment-centric | By design (D4) | admin adds types via UI (dynamic prompt, zero code) |
| No multimodal (image→LLM) | Deferred | same `_run_ai_classify` seam; photos → no text → needs_review |
