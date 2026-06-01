# Architecture: TeamX10 AI — Auto-foldering

> Task: `2026-05-26-ai-document-foldering`
> Date: 2026-05-26

---

## Component Map

### Файлы к СОЗДАНИЮ (`custom_addons/tx10_ai/`)

```
models/
  tx10_document_folder.py      — Model tx10.document.folder + FOLDER_TEMPLATE + _ensure_tree
  tx10_document_classifier.py  — Pure-Python classifier (no ORM): KEYWORD_RULES, extract_text, classify
  solar_document.py            — _inherit solar.document: folder_id, needs_review, document_type_id→optional

wizard/
  __init__.py
  tx10_document_upload_wizard.py   — TransientModel tx10.document.upload.wizard
  tx10_document_result_line.py     — TransientModel tx10.document.result.line (сводка)

views/
  tx10_document_folder_views.xml        — tree/form views для tx10.document.folder
  tx10_document_upload_wizard_views.xml — wizard form + кнопка на project.project

security/
  ir.model.access.csv  — ACL: folder + wizard × 2 группы (дополнение к существующему файлу)

tests/
  test_tx10_document_classifier.py  — Unit tests (no DB)
  test_tx10_document_folder.py      — Integration: дерево
  test_tx10_document_upload.py      — Integration: E2E wizard
```

### Файлы к ИЗМЕНЕНИЮ

```
models/__init__.py         — +tx10_document_folder, +tx10_document_classifier, +solar_document
__init__.py                — +from . import wizard
__manifest__.py            — data: +security CSV, +новые views; version bump
models/tx10_ai_service.py  — +classify_document_text() тонкая обёртка (опциональная)
```

### Файлы НЕ ТРОГАТЬ

```
custom_addons/solar_project/*   — document_type_id override только через _inherit в tx10_ai
```

---

## Data Model

```
tx10.document.folder
 ├─ id              Integer PK (auto)
 ├─ name            Char (required)
 ├─ project_id      Many2one project.project (required, ondelete=cascade)
 ├─ parent_id       Many2one self (ondelete=cascade)
 ├─ child_ids       One2many self (inverse parent_id)
 ├─ parent_path     Char (index=True)          ← _parent_store=True
 ├─ complete_name   Char (computed, store=True) ← "Root / Sub / Leaf" с разделителем " / "
 ├─ folder_code     Char                        ← стабильный routing-ключ (напр. "02_Інвертори")
 └─ document_ids    One2many solar.document (inverse folder_id)

solar.document (расширение через _inherit)
 ├─ folder_id       Many2one tx10.document.folder (ondelete=set null, новое поле)
 ├─ needs_review    Boolean (default False, новое поле)
 └─ document_type_id → required=False (override атрибута; DB без изменений)

tx10.document.upload.wizard (TransientModel)
 ├─ project_id      Many2one project.project (required)
 ├─ file_data       Binary (multi-upload via attachment_ids в view)
 ├─ attachment_ids  Many2many ir.attachment (temp holding)
 └─ result_line_ids One2many tx10.document.result.line

tx10.document.result.line (TransientModel)
 ├─ wizard_id    Many2one tx10.document.upload.wizard
 ├─ filename     Char
 ├─ folder_id    Many2one tx10.document.folder
 ├─ confidence   Float
 ├─ status       Selection: done/needs_review/skipped/error
 └─ message      Char
```

---

## Interaction Flow

```
User
  │ click «Загрузити документи»
  ▼
project.project (form)
  │ action_open_upload_wizard() → {type: ir.actions.act_window, res_model: tx10.document.upload.wizard}
  ▼
tx10.document.upload.wizard
  │ user attaches files
  │ user clicks «Класифікувати»
  │
  ├─► _ensure_tree(project)           ← tx10.document.folder: idempotent seed
  │
  │   for each attachment:
  ├─► extract_text(filename, bytes)   ← tx10_document_classifier (pure Python)
  ├─► classify(text, filename)        ← returns {category, confidence, reasons, document_type_code}
  │
  │   if dup (name+size in project):
  │     → result_line status=skipped
  │
  │   elif confidence < 0.70:
  │     → folder = get_folder_by_code(project, "05_Інше")
  │     → solar.document(folder_id=folder, needs_review=True, ai_classified=True)
  │     → result_line status=needs_review
  │
  │   else:
  │     → folder = get_folder_by_code(project, category)
  │     → solar.document(folder_id=folder, ai_classified=True)
  │     → result_line status=done
  │
  ▼
wizard summary view (result_line_ids table)
```

---

## Classify-Filer Seam

```
┌─────────────────────────────────────────────────────────────┐
│  CLASSIFIER (storage-agnostic pure Python)                   │
│  tx10_document_classifier.py                                 │
│  IN:  text: str, filename: str                               │
│  OUT: {category: str, confidence: float,                     │
│         reasons: list, document_type_code: str}              │
└─────────────────────────────┬───────────────────────────────┘
                              │ category (folder_code string)
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  FILER — Community backend (knows ORM)                       │
│  tx10.document.upload.wizard.action_classify_and_file()      │
│  IN:  project_id, category, confidence, attachment           │
│  OUT: solar.document record                                  │
└─────────────────────────────────────────────────────────────┘
                              │
           future Enterprise bridge:
                              │
┌─────────────────────────────────────────────────────────────┐
│  FILER — Enterprise backend (tx10_ai_documents addon)        │
│  Same category input → documents.document record            │
└─────────────────────────────────────────────────────────────┘
```

---

## FOLDER_TEMPLATE Structure (24 узла)

```python
FOLDER_TEMPLATE = [
    # (path_parts, folder_code)
    (["01_Вхідні_дані"],                                                   "root_input"),
    (["01_Вхідні_дані", "01_Опитувальний_лист"],                           "survey"),
    (["01_Вхідні_дані", "01_Опитувальний_лист", "01_Оригінал"],            "survey_orig"),
    (["01_Вхідні_дані", "01_Опитувальний_лист", "02_Додатки"],             "survey_attachments"),
    (["01_Вхідні_дані", "02_Технічні_каталоги"],                           "catalogs"),
    (["01_Вхідні_дані", "02_Технічні_каталоги", "01_Сонячні_модулі"],      "01_Сонячні_модулі"),
    (["01_Вхідні_дані", "02_Технічні_каталоги", "02_Інвертори"],           "02_Інвертори"),
    (["01_Вхідні_дані", "02_Технічні_каталоги", "03_Акумулятори"],         "03_Акумулятори"),
    (["01_Вхідні_дані", "02_Технічні_каталоги", "04_BMS_PDU"],             "04_BMS_PDU"),
    (["01_Вхідні_дані", "02_Технічні_каталоги", "05_BOS_обладнання"],      "05_BOS_обладнання"),
    (["01_Вхідні_дані", "02_Технічні_каталоги", "06_Інше_обладнання"],     "06_Інше_обладнання"),
    (["01_Вхідні_дані", "03_Матеріали_від_замовника"],                     "customer_materials"),
    (["01_Вхідні_дані", "03_Матеріали_від_замовника", "01_Фото"],          "01_Фото"),
    (["01_Вхідні_дані", "03_Матеріали_від_замовника", "02_Схеми"],         "02_Схеми"),
    (["01_Вхідні_дані", "03_Матеріали_від_замовника", "03_Споживання_та_рахунки"], "03_Споживання_та_рахунки"),
    (["01_Вхідні_дані", "03_Матеріали_від_замовника", "04_ТУ_договори_облік"],     "04_ТУ_договори_облік"),
    (["01_Вхідні_дані", "03_Матеріали_від_замовника", "05_Інше"],          "05_Інше"),
    (["03_Розрахунки"],                                                    "root_calculations"),
    (["03_Розрахунки", "02_PVsyst"],                                       "pvsyst"),
    (["03_Розрахунки", "02_PVsyst", "01_Reports"],                         "pvsyst_reports"),
    (["03_Розрахунки", "02_PVsyst", "02_Project_Files"],                   "pvsyst_projects"),
    (["03_Розрахунки", "02_PVsyst", "03_Export"],                          "pvsyst_export"),
    (["03_Розрахунки", "04_SolarEdge_Designer"],                           "solaredge"),
    (["03_Розрахунки", "05_K2"],                                           "k2"),
]
```

---

## Category → Folder Routing Table

| Category keyword | folder_code | Путь в дереве |
|-----------------|-------------|---------------|
| SOLAR_MODULE / solar_panel | `01_Сонячні_модулі` | ...02_Технічні_каталоги/01_Сонячні_модулі |
| INVERTER | `02_Інвертори` | ...02_Технічні_каталоги/02_Інвертори |
| BATTERY | `03_Акумулятори` | ...02_Технічні_каталоги/03_Акумулятори |
| BMS | `04_BMS_PDU` | ...02_Технічні_каталоги/04_BMS_PDU |
| BOS | `05_BOS_обладнання` | ...02_Технічні_каталоги/05_BOS_обладнання |
| PHOTO (by extension) | `01_Фото` | ...03_Матеріали_від_замовника/01_Фото |
| SCHEME / DRAWING | `02_Схеми` | ...03_Матеріали_від_замовника/02_Схеми |
| CONSUMPTION / INVOICE | `03_Споживання_та_рахунки` | ...03_Матеріали_від_замовника/03_Споживання_та_рахунки |
| PERMIT / CONTRACT | `04_ТУ_договори_облік` | ...03_Матеріали_від_замовника/04_ТУ_договори_облік |
| PVSYST | `pvsyst_reports` | ...03_Розрахунки/02_PVsyst/01_Reports |
| SURVEY / QUESTIONNAIRE | `survey_orig` | ...01_Опитувальний_лист/01_Оригінал |
| Unknown / confidence<70% | `05_Інше` | ...03_Матеріали_від_замовника/05_Інше |

---

## Build Sequence

```
T1 (Data Layer):
  1. tx10_document_folder.py    (model + FOLDER_TEMPLATE + _ensure_tree)
  2. solar_document.py          (_inherit: folder_id, needs_review, type optional)
  3. security/ir.model.access.csv  (4 new rows)
  4. models/__init__.py         (register new models)
  5. views/tx10_document_folder_views.xml  (tree/form + smart-button)
  6. __manifest__.py            (register data)
  7. tests/test_tx10_document_folder.py

T2 (Classify + Wizard):
  1. tx10_document_classifier.py  (KEYWORD_RULES, extract_text, classify)
  2. wizard/tx10_document_upload_wizard.py
  3. wizard/tx10_document_result_line.py
  4. wizard/__init__.py
  5. __init__.py               (+from . import wizard)
  6. views/tx10_document_upload_wizard_views.xml  (+кнопка на project)
  7. __manifest__.py           (register wizard views)
  8. tests/test_tx10_document_classifier.py
  9. tests/test_tx10_document_upload.py
```
