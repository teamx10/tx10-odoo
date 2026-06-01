# Tasks: TeamX10 AI — Auto-foldering

> Task: `2026-05-26-ai-document-foldering`
> Branch: `feat/tx10-ai-foldering`
> Module: `custom_addons/tx10_ai`
> Date: 2026-05-26
> Size: M

---

## Execution Order

### Phase 0: Pre-flight
- [ ] **T01** — `gitnexus_impact` на `solar.document` и `tx10.ai.service` перед любыми правками (~0.2h)
- [ ] **T02** — Подтвердить наличие pypdf в requirements.txt: `grep -i pypdf requirements.txt` (~0.05h)
- [ ] **T03** — Создать feature branch: `git checkout develop && git pull && git checkout -b feat/tx10-ai-foldering` (~0.05h)

### Phase 1: T1 — Data Layer
- [ ] **T04** — `models/tx10_document_folder.py`: модель `tx10.document.folder` + `FOLDER_TEMPLATE` (24 узла) + `_ensure_tree()` + `get_folder_by_code()` (~1.5h)
- [ ] **T05** — `models/solar_document.py`: `_inherit = "solar.document"` — добавить `folder_id`, `needs_review`; override `document_type_id → required=False`; `@api.constrains` cross-project check (~0.5h)
- [ ] **T06** — `security/ir.model.access.csv`: 4 новые строки (folder × 2 группы + wizard × 1 группа + result_line × 1 группа) (~0.2h)
- [ ] **T07** — `models/__init__.py`: регистрация `tx10_document_folder`, `tx10_document_classifier`, `solar_document` (~0.1h)
- [ ] **T08** — `views/tx10_document_folder_views.xml`: tree-view + form-view для `tx10.document.folder`; smart-button «Папки» на `project.project` form (~0.75h)
- [ ] **T09** — `__manifest__.py`: добавить security CSV и folder views в `data`; version bump → `19.0.1.2.0` (~0.15h)
- [ ] **T10** — `tests/test_tx10_document_folder.py`: `TestTx10DocumentFolderTree` — 6 тестов (24 folders, idempotency, isolation, complete_name, get_by_code, unknown code) (~0.75h)
- [ ] **T11** — Прогон тестов T1: `./odoo-bin -d <db> --test-tags tx10_ai --stop-after-init` (только тесты дерева) (~0.25h)

### Phase 2: T2 — Classifier + Wizard _(стартует после T11)_
- [ ] **T12** — `models/tx10_document_classifier.py`: `KEYWORD_RULES` (8 категорий, EN/UA), `PHOTO_EXTENSIONS`, `CATEGORY_TO_FOLDER_CODE`, `extract_text()`, `classify()`, `_extract_pdf/docx/xlsx()` + zip bomb guard (~2.0h)
- [ ] **T13** — `wizard/tx10_document_upload_wizard.py` + `wizard/tx10_document_result_line.py`: `tx10.document.upload.wizard` (TransientModel), `action_classify_and_file()`, result line model (~1.5h)
- [ ] **T14** — `wizard/__init__.py`: import wizard models (~0.05h)
- [ ] **T15** — `__init__.py`: добавить `from . import wizard` (~0.05h)
- [ ] **T16** — `views/tx10_document_upload_wizard_views.xml`: wizard form (upload step + summary step); кнопка «Загрузити документи» на `project.project` form; inherit view для `solar.document` list (колонка folder) (~1.0h)
- [ ] **T17** — `__manifest__.py`: добавить wizard views и uk.po entries (~0.1h)
- [ ] **T18** — `models/tx10_ai_service.py`: добавить `classify_document_text()` метод-обёртку (~0.2h)
- [ ] **T19** — `i18n/uk.po`: новые переводы для wizard строк (~0.25h)
- [ ] **T20** — `tests/test_tx10_document_classifier.py`: `TestTx10DocumentClassifier` — ~18 unit-тестов (без DB) (~1.0h)
- [ ] **T21** — `tests/test_tx10_document_upload.py`: `TestTx10DocumentUpload` — ~9 integration-тестов (E2E wizard) (~1.0h)
- [ ] **T22** — Прогон всех тестов: `./odoo-bin -d <db> --test-tags tx10_ai --stop-after-init` (~0.5h)

### Phase 3: Verification
- [ ] **T23** — `gitnexus_detect_changes()` перед коммитом: убедиться, что blast radius = только `tx10_ai` (~0.1h)
- [ ] **T24** — [MANUAL] UI verification (~0.5h):
  - Открыть проект → кнопка «Загрузити документи» видна
  - Загрузить PDF-даташит → `02_Інвертори`, confidence ≥ 0.75, done
  - Загрузить XLSX → `03_Споживання_та_рахунки`, done
  - Загрузить .jpg → `01_Фото`, done
  - Загрузить нераспознанный TXT → `05_Інше`, needs_review
  - Повторная загрузка → skipped
  - Smart-button «Папки» → дерево с документами
- [ ] **T25** — Regression: `./odoo-bin -d <db> --test-tags solar_project --stop-after-init` (~0.25h)
- [ ] **T26** — Implementation log: `docs/plans/2026-05-26-ai-document-foldering-IMPLEMENTED.md` (~0.25h)

---

## Parallel Opportunities

```
T01 ──► T04 ──► T05 ──► T06 ──► T07 ──► T08 ──► T09 ──► T10 ──► T11
T02 ──/                                                              \
T03 ──/                                                               ──► T12 ──► T13 ──► T14
                                                                                          T15 ──► T16 ──► T17 ──► T18 ──► T19 ──► T20 ──► T21 ──► T22 ──► T23 ──► T24 ──► T25 ──► T26
```

- T01, T02, T03 можно запустить параллельно (pre-flight независимы).
- T04–T11 = T1 (data layer) — строго последовательно.
- T12–T22 = T2 (classifier + wizard) — стартует после T11.
- T23–T26 = verification — после T22.

---

## Manual Steps

| Task | Почему вручную | Pre-condition |
|------|---------------|---------------|
| T24 | Browser UI + загрузка реальных файлов | Docker stack up, `-u tx10_ai` выполнен |

---

## Estimated Effort

| Task | Est. |
|------|------|
| T01 | 0.20h |
| T02 | 0.05h |
| T03 | 0.05h |
| T04 | 1.50h |
| T05 | 0.50h |
| T06 | 0.20h |
| T07 | 0.10h |
| T08 | 0.75h |
| T09 | 0.15h |
| T10 | 0.75h |
| T11 | 0.25h |
| T12 | 2.00h |
| T13 | 1.50h |
| T14 | 0.05h |
| T15 | 0.05h |
| T16 | 1.00h |
| T17 | 0.10h |
| T18 | 0.20h |
| T19 | 0.25h |
| T20 | 1.00h |
| T21 | 1.00h |
| T22 | 0.50h |
| T23 | 0.10h |
| T24 | 0.50h |
| T25 | 0.25h |
| T26 | 0.25h |
| **Total** | **~11.25h** |

Size: **M** (1.5–2 dev days, учитывая manual steps и итерацию keyword-правил)

---

## Files Touched (summary)

| File | Change |
|------|--------|
| `models/tx10_document_folder.py` | **CREATE** — folder model + tree |
| `models/tx10_document_classifier.py` | **CREATE** — classifier + extractors |
| `models/solar_document.py` | **CREATE** — _inherit extension |
| `wizard/__init__.py` | **CREATE** |
| `wizard/tx10_document_upload_wizard.py` | **CREATE** — wizard + result line |
| `views/tx10_document_folder_views.xml` | **CREATE** |
| `views/tx10_document_upload_wizard_views.xml` | **CREATE** |
| `tests/test_tx10_document_classifier.py` | **CREATE** |
| `tests/test_tx10_document_folder.py` | **CREATE** |
| `tests/test_tx10_document_upload.py` | **CREATE** |
| `security/ir.model.access.csv` | **MODIFY** (+4 rows) |
| `models/__init__.py` | **MODIFY** (+3 imports) |
| `__init__.py` | **MODIFY** (+wizard) |
| `__manifest__.py` | **MODIFY** (+data, version) |
| `models/tx10_ai_service.py` | **MODIFY** (+classify wrapper) |
| `i18n/uk.po` | **MODIFY** (+wizard strings) |
