# Test Plan: TeamX10 AI — Auto-foldering

> Task: `2026-05-26-ai-document-foldering`
> Date: 2026-05-26

---

## Test Files Overview

| Файл | Тип | DB | Теги Odoo |
|------|-----|----|-----------|
| `tests/test_tx10_document_classifier.py` | Unit (pure Python) | нет | `tx10_ai` |
| `tests/test_tx10_document_folder.py` | Integration | да | `tx10_ai` |
| `tests/test_tx10_document_upload.py` | Integration (E2E wizard) | да | `tx10_ai` |

Run command:
```bash
./odoo-bin -d <db> --test-tags tx10_ai --stop-after-init
```

---

## File 1: `tests/test_tx10_document_classifier.py`

```python
"""Unit tests for tx10_document_classifier — no DB required."""
from odoo.tests import tagged
from odoo.addons.tx10_ai.models.tx10_document_classifier import classify, extract_text

@tagged("tx10_ai", "-at_install")
class TestTx10DocumentClassifier(unittest.TestCase):
```

### Test Methods

| Method | Input | Expected output |
|--------|-------|----------------|
| `test_solar_panel_by_keyword` | text="monocrystalline panel longi solar" | category="01_Сонячні_модулі", confidence≥0.70 |
| `test_inverter_by_keyword` | text="fronius string inverter datasheet" | category="02_Інвертори", confidence≥0.70 |
| `test_battery_by_keyword` | text="lifepo4 pylontech battery storage" | category="03_Акумулятори", confidence≥0.70 |
| `test_bms_by_keyword` | text="bms battery management system" | category="04_BMS_PDU", confidence≥0.70 |
| `test_pvsyst_by_keyword` | text="pvsyst simulation yield report" | category="pvsyst_reports", confidence≥0.70 |
| `test_consumption_by_keyword` | text="electricity bill consumption kwh" | category="03_Споживання_та_рахунки", confidence≥0.70 |
| `test_photo_by_extension` | filename="site_photo.jpg", text="" | category="01_Фото", confidence=1.0 |
| `test_photo_by_extension_png` | filename="panel.png", text="" | category="01_Фото", confidence=1.0 |
| `test_unknown_low_confidence` | text="random document text", filename="doc.txt" | confidence<0.70, category="05_Інше" |
| `test_confidence_formula_score1` | 1 keyword match, no text | confidence=0.75 (0.65+0.10) |
| `test_confidence_formula_score3` | 3 keyword matches, no text | confidence=0.95 (0.65+0.30) |
| `test_confidence_floor_with_text` | 1 keyword, text non-empty | confidence≥0.80 |
| `test_threshold_70_percent` | confidence=0.69 (0 full matches) | category="05_Інше" |
| `test_reasons_populated` | inverter keywords matched | result["reasons"] non-empty list |
| `test_doctype_code_returned` | inverter text | result["document_type_code"] = "inverter" |
| `test_extract_text_plain_txt` | b"hello world" + "doc.txt" | returns "hello world" |
| `test_extract_text_empty_image` | any bytes + "img.jpg" | returns "" |
| `test_extract_text_50mb_docx_rejected` | 51MB fake docx | returns "" (zip bomb guard) |

---

## File 2: `tests/test_tx10_document_folder.py`

```python
from odoo.tests import TransactionCase, tagged

@tagged("tx10_ai", "post_install", "-at_install")
class TestTx10DocumentFolderTree(TransactionCase):
```

### Setup

```python
@classmethod
def setUpClass(cls):
    super().setUpClass()
    cls.project = cls.env["project.project"].create({"name": "Test Solar Project"})
```

### Test Methods

| Method | Что проверяем |
|--------|--------------|
| `test_ensure_tree_creates_24_folders` | После `_ensure_tree(project)` — ровно 24 записи `tx10.document.folder` для проекта |
| `test_ensure_tree_idempotent` | Второй вызов `_ensure_tree(project)` → число папок не изменилось |
| `test_project_isolation` | P1 и P2 после `_ensure_tree` — папки P1 не видны из запроса с `project_id=P2.id` |
| `test_complete_name_path` | `get_folder_by_code(project, "02_Інвертори")` → `complete_name = "01_Вхідні_дані / 02_Технічні_каталоги / 02_Інвертори"` |
| `test_get_folder_by_code_returns_correct` | `get_folder_by_code(project, "05_Інше")` → folder.name = "05_Інше" |
| `test_get_folder_by_code_unknown_returns_empty` | `get_folder_by_code(project, "nonexistent")` → falsy (browse([]).id is False) |

---

## File 3: `tests/test_tx10_document_upload.py`

```python
import base64
from odoo.tests import TransactionCase, tagged

@tagged("tx10_ai", "post_install", "-at_install")
class TestTx10DocumentUpload(TransactionCase):
```

### Setup

```python
@classmethod
def setUpClass(cls):
    super().setUpClass()
    cls.project = cls.env["project.project"].create({"name": "Upload Test Project"})
    cls.manager = cls.env.ref("base.user_admin")
```

### Test Methods

| Method | Сценарий | Ожидаемый результат |
|--------|----------|-------------------|
| `test_upload_inverter_pdf_classified` | Загрузить PDF с текстом "fronius string inverter" | `solar.document.folder_id.folder_code = "02_Інвертори"`, `ai_classified=True`, `needs_review=False` |
| `test_upload_consumption_xlsx_classified` | Загрузить XLSX с текстом "electricity bill kwh" | `folder_code = "03_Споживання_та_рахунки"` |
| `test_upload_photo_jpg_classified` | Загрузить .jpg файл | `folder_code = "01_Фото"`, `needs_review=False` |
| `test_upload_unknown_txt_needs_review` | Загрузить TXT "random unrelated text" | `folder_code = "05_Інше"`, `needs_review=True`, result_line status=`needs_review` |
| `test_duplicate_skipped` | Загрузить тот же файл дважды | Второй вызов: result_line status=`skipped`, число `solar.document` = 1 |
| `test_error_handling` | Загрузить повреждённый файл | result_line status=`error`, приложение не падает |
| `test_wizard_state_transitions` | Вызвать `action_classify_and_file()` | `wizard.state = "done"`, `result_line_ids` непустые |
| `test_document_type_id_optional` | Создать `solar.document` без `document_type_id` | Запись создаётся без исключения |
| `test_solar_project_regression` | Создать `solar.document` обычным способом с `document_type_id` | `solar_project` тесты не нарушены |

---

## Regression Test Coverage

После реализации запустить:

```bash
# Все тесты tx10_ai
./odoo-bin -d <db> --test-tags tx10_ai --stop-after-init

# solar_project тесты (regression check)
./odoo-bin -d <db> --test-tags solar_project --stop-after-init
```

### Ключевые regression-сценарии

1. **`solar.document` с `document_type_id=False`** → нет `IntegrityError` (NOT NULL) — подтверждает Q2
2. **Существующие тесты `tx10_ai`** → все проходят (классификатор не меняет сервис/агент/чат)
3. **`solar_project` без `tx10_ai`** → `document_type_id` остаётся required (override только когда оба установлены)

---

## Mock Strategy

| Компонент | Стратегия |
|-----------|-----------|
| PDF content | Использовать `base64.b64encode(b"fake pdf content fronius inverter")` — pypdf падает gracefully, текст берётся из filename |
| DOCX/XLSX | Создать минимальный zip-байты с нужным XML или использовать mock `extract_text()` через `unittest.mock.patch` |
| ir.attachment | Создавать реальные записи в TransactionCase (нет mocking — полная интеграция) |
| LLM (`tx10.ai.service`) | НЕ задействован в этой фиче — mock не нужен |

---

## Test Sizing

| Файл | Методов | Тип | Время |
|------|---------|-----|-------|
| `test_tx10_document_classifier.py` | ~18 | unit (no DB) | ~5s |
| `test_tx10_document_folder.py` | ~6 | integration | ~15s |
| `test_tx10_document_upload.py` | ~9 | integration E2E | ~30s |
| **Total** | **~33** | | **~50s** |
