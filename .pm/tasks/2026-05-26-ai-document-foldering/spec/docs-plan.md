# Docs Plan: TeamX10 AI — Auto-foldering

> Task: `2026-05-26-ai-document-foldering`
> Date: 2026-05-26

---

## IMPLEMENTED.md Template

После завершения реализации создать:
`docs/plans/2026-05-26-ai-document-foldering-IMPLEMENTED.md`

### Структура документа

```markdown
# IMPLEMENTED: TeamX10 AI — Auto-foldering

## Goal
Пользователь загружает файлы в проект → детерминированный классификатор определяет тип
и кладёт файл в правильную папку дерева проекта (TEO_Solar-структура);
нераспознанное → «05_Інше» + needs_review.

## Files Created (11)
| File | Purpose |
|------|---------|
| models/tx10_document_folder.py | Model + FOLDER_TEMPLATE + _ensure_tree |
| models/tx10_document_classifier.py | Pure-Python classifier, extractor |
| models/solar_document.py | _inherit: folder_id, needs_review, type optional |
| wizard/__init__.py | Package init |
| wizard/tx10_document_upload_wizard.py | Upload + classify wizard |
| wizard/tx10_document_result_line.py | Result summary line |
| views/tx10_document_folder_views.xml | Folder tree/form views |
| views/tx10_document_upload_wizard_views.xml | Wizard + project button |
| tests/test_tx10_document_classifier.py | Unit tests (no DB) |
| tests/test_tx10_document_folder.py | Integration: folder tree |
| tests/test_tx10_document_upload.py | Integration: E2E wizard |

## Files Modified (5)
| File | Change |
|------|--------|
| models/__init__.py | +tx10_document_folder, +tx10_document_classifier, +solar_document |
| __init__.py | +from . import wizard |
| __manifest__.py | +data entries, version bump |
| security/ir.model.access.csv | +4 ACL rows |
| models/tx10_ai_service.py | +classify_document_text() wrapper |

## Key Patterns Established
- Classify-filer seam: pure-Python classify() + ORM filer (Enterprise-extensible)
- _parent_store=True tree model with idempotent _ensure_tree()
- _inherit override of required=False (ORM-only, no migration)
- Zip bomb guard (50MB before zipfile.ZipFile())

## Deviations from Plan
(fill in after implementation)

## Verification Evidence
- [ ] ./odoo-bin --test-tags tx10_ai --stop-after-init exits 0
- [ ] Manual UI walkthrough: project → upload → summary → folder tree

## Commits
(fill in after commits)

## PR
(fill in after PR created)
```

---

## AGENTSTATUS.md Updates

После реализации обновить `AGENTSTATUS.md` в корне проекта:

```markdown
## tx10_ai module

### Auto-foldering (feat/tx10-ai-foldering)
- Status: implemented / in PR review
- New models: tx10.document.folder, tx10.document.upload.wizard
- Modified: solar.document (_inherit: folder_id, needs_review, type optional)
- Classifier: deterministic keyword rules (port from SuperTEO/TEO_Solar)
- Entry point: project.project → «Загрузити документи» button → wizard
```

---

## Inline Comment Spec

### `KEYWORD_RULES` в `tx10_document_classifier.py`

Единственный допустимый комментарий перед константой:

```python
# Bilingual EN/UA keyword rules ported from SuperTEO (Subbotik24).
# Each category maps to a folder_code via CATEGORY_TO_FOLDER_CODE.
KEYWORD_RULES = { ... }
```

Не документировать каждую категорию отдельно — названия ключей самодокументированы.

### `FOLDER_TEMPLATE` в `tx10_document_folder.py`

```python
# TEO_Solar folder tree — input-data branches only.
# AI workbench (80_) and analysis (02_АНАЛІЗ/) branches are excluded.
FOLDER_TEMPLATE = [ ... ]
```

### `_ensure_tree()` в `tx10_document_folder.py`

```python
def _ensure_tree(self, project):
    # Uses sudo() because project_user has read-only ACL on tx10.document.folder.
    # Scope is limited to create operations for the given project only.
```

### `document_type_id` override в `solar_document.py`

```python
# Override required=False: M2o required is ORM-only validation, not a DB NOT NULL constraint.
# solar_project is not modified; this override is only active when tx10_ai is installed.
document_type_id = fields.Many2one(required=False)
```

---

## Документация НЕ нужна

- KEYWORD_RULES не нуждаются в отдельном README (таблица в architecture.md достаточна)
- FOLDER_TEMPLATE не нуждается в doc-файле (константа с комментарием + architecture.md)
- API-документация `classify()` не нужна (сигнатура + docstring достаточны)
- Нет нужды в отдельном .po для `ru` (только `uk.po` в MVP, per decision Q10)

---

## uk.po Entries (новые строки)

В `i18n/uk.po` добавить переводы для строк wizard:

```po
msgid "Upload and Classify Documents"
msgstr "Завантажити та класифікувати документи"

msgid "Files"
msgstr "Файли"

msgid "Upload"
msgstr "Завантаження"

msgid "Done"
msgstr "Готово"

msgid "Needs Review"
msgstr "Потребує перевірки"

msgid "Skipped"
msgstr "Пропущено"

msgid "Error"
msgstr "Помилка"

msgid "Duplicate — already exists in project"
msgstr "Дублікат — вже існує в проекті"

msgid "Some files require manual review"
msgstr "Деякі файли потребують ручної перевірки"

msgid "Upload Documents"
msgstr "Завантажити документи"

msgid "Document Folder"
msgstr "Папка документів"

msgid "Folder"
msgstr "Папка"
```
