# Spec: TeamX10 AI — Auto-foldering

> Task: `2026-05-26-ai-document-foldering`
> Branch: `feat/tx10-ai-foldering`
> Module: `custom_addons/tx10_ai/`
> Date: 2026-05-26

---

## Problem Statement

Пользователи проектов `isolar` загружают документы вручную и хранят их произвольно — нет единой структуры папок, нет автоматической классификации. Проекты Subbotik24 (TEO_Solar, SuperTEO) решили эту проблему детерминированным классификатором + стандартным деревом TEO_Solar.

В `tx10_ai` нужно воспроизвести этот MVP: кнопка на проекте → wizard → загрузка файлов → классификация → раскладка в правильные папки → сводка.

---

## Acceptance Criteria

### AC-1: Дерево папок создаётся для проекта

**Given** `project.project` запись существует  
**When** пользователь нажимает «Загрузить документы» (или метод `_ensure_tree()` вызывается)  
**Then** создаётся полное дерево `tx10.document.folder` для проекта: 24 узла согласно `FOLDER_TEMPLATE`

### AC-2: Идемпотентность дерева

**Given** `_ensure_tree(project)` уже был вызван для проекта  
**When** он вызывается снова  
**Then** число папок не меняется — дубликатов нет, ни один существующий узел не перезаписывается

### AC-3: Изоляция деревьев по проектам

**Given** проекты P1 и P2 существуют  
**When** для каждого вызван `_ensure_tree()`  
**Then** папки P1 не видны из P2 (все `tx10.document.folder` имеют `project_id`)

### AC-4: Права доступа к папкам

**Given** пользователь в группе `project.group_project_user`  
**Then** он может читать записи `tx10.document.folder` (через `ir.model.access`)

**Given** пользователь в группе `project.group_project_manager`  
**Then** он может создавать, редактировать, удалять `tx10.document.folder`

### AC-5: `document_type_id` необязателен

**Given** модуль `tx10_ai` установлен  
**When** создаётся `solar.document` без `document_type_id`  
**Then** запись сохраняется без ошибки (ORM-override `required=False` действует)

**Then** `solar_project` не содержит DB-миграций — ограничение только ORM-уровня

### AC-6: Wizard доступен из проекта

**Given** пользователь открыл `project.project` form  
**Then** видна кнопка «Загрузити документи»

**When** кнопка нажата  
**Then** открывается wizard `tx10.document.upload.wizard` с предзаполненным `project_id`

### AC-7: Загрузка и классификация файлов

**Given** wizard открыт для проекта  
**When** пользователь прикрепляет один или несколько файлов и нажимает «Класифікувати»  
**Then** для каждого файла:
  - извлекается текст (PDF/DOCX/XLSX/text → содержимое; изображения → по расширению → PHOTO)
  - вызывается `classify()` из `tx10_document_classifier`
  - создаётся `solar.document` с `folder_id`, `attachment_id`, `ai_classified=True`, `ai_extracted_data`

### AC-8: Формула confidence и порог

**Given** документ классифицирован с `score = N` совпавших ключевых слов  
**Then** `confidence = 0.65 + 0.1 * min(score, 3)`

**Given** текст успешно извлечён (непустой)  
**Then** `confidence >= 0.80` (floor)

**Given** `confidence < 0.70`  
**Then** документ получает `category = "05_Інше"` (Нераспознанне) + флаг `needs_review = True`

### AC-9: Нераспознанные документы

**Given** классификатор вернул `confidence < 0.70`  
**When** wizard создаёт `solar.document`  
**Then** файл кладётся в папку `01_Вхідні_дані/03_Матеріали_від_замовника/05_Інше`  
**And** `solar.document.needs_review = True`  
**And** в сводке wizard статус = `needs_review`

### AC-10: Дубликаты пропускаются

**Given** в проекте уже есть `solar.document` с таким же `attachment.name` и `file_size`  
**When** пользователь загружает тот же файл  
**Then** новая запись не создаётся  
**And** в сводке wizard статус = `skipped` для этого файла

### AC-11: Сводка wizard

**Given** классификация завершена  
**Then** wizard показывает сводку: таблица `файл → папка / статус (done|needs_review|skipped|error) / confidence`

**Given** хотя бы один файл имеет статус `needs_review`  
**Then** в сводке есть предупреждение "Деякі файли потребують ручної перевірки"

### AC-12: Регрессия solar_project

**Given** `solar.document` создаётся с `document_type_id = False`  
**Then** `solar_project` views и compute-методы не падают (тест существующих тестов проходит)

**Given** `solar_project` устанавливается без `tx10_ai`  
**Then** `document_type_id` остаётся `required=True` (override применяется только при наличии `tx10_ai`)

### AC-13: Контракт классификатора (unit)

**Given** функция `classify(text, filename)` из `tx10_document_classifier`  
**Then** возвращает словарь с ключами: `category` (str), `confidence` (float 0.0–1.0), `reasons` (list[str]), `document_type_code` (str)

**Given** filename = "inverter_datasheet.pdf", text содержит "інвертор"  
**Then** `category = "02_Інвертори"`, `confidence >= 0.70`

**Given** text = "", filename = "photo.jpg"  
**Then** `category = "01_Фото"`, `confidence = 1.0`

**Given** text = "random text no keywords", filename = "unknown.txt"  
**Then** `category = "05_Інше"`, `confidence < 0.70`

---

## Definition of Done

### Code

- [ ] `models/tx10_document_folder.py` — модель `tx10.document.folder`: `name`, `project_id`, `parent_id`, `child_ids`, `parent_path` (`_parent_store=True`), `complete_name` (computed с разделителем ` / `), `folder_code`, `document_ids`; методы `_ensure_tree(project)` (idempotent) и `get_folder_by_code(project, code)`
- [ ] `models/tx10_document_classifier.py` — `KEYWORD_RULES` (билингва EN/UA, 8+ категорий), `CATEGORY_TO_FOLDER_CODE` (routing-таблица), `extract_text(filename, content_bytes)` (PDF/DOCX/XLSX/text), `classify(text, filename)` → dict
- [ ] `models/solar_document.py` — `_inherit = "solar.document"`: поле `folder_id` (M2o `tx10.document.folder`, ondelete=set null), поле `needs_review` (Boolean), override `document_type_id` → `required=False`
- [ ] `wizard/tx10_document_upload_wizard.py` — `tx10.document.upload.wizard` (TransientModel): `project_id`, `file_ids` (Binary+Char поля или `attachment_ids`), `result_line_ids` (O2m сводки); `action_classify_and_file()` → вызывает extractor + classify + filer + создаёт `solar.document`; возвращает сводку
- [ ] `wizard/tx10_document_result_line.py` (или встроенная модель сводки) — `filename`, `folder_id`, `confidence`, `status` (selection: done/needs_review/skipped/error), `message`
- [ ] `views/tx10_document_folder_views.xml` — tree-view + form-view для `tx10.document.folder`; smart-button «Папки» на `project.project`
- [ ] `views/tx10_document_upload_wizard_views.xml` — form-view для wizard (шаги: загрузка → сводка); кнопка «Загрузити документи» на `project.project`
- [ ] `security/ir.model.access.csv` — 4 строки: `tx10.document.folder` × 2 группы + wizard × 2 группы
- [ ] `models/__init__.py` — регистрация новых моделей
- [ ] `wizard/__init__.py` — регистрация wizard
- [ ] `__init__.py` — добавить `from . import wizard`
- [ ] `__manifest__.py` — обновлённый список `data` (security, views); `tx10.ai.service` обёртка для `classify_document_text` (опциональная тонкая обёртка в `tx10_ai_service.py`)

### Tests

- [ ] `tests/test_tx10_document_classifier.py` — `TestTx10DocumentClassifier` (без DB): тесты для каждой категории keyword-правил, confidence formula, threshold, photo-by-extension, duplicate-safe
- [ ] `tests/test_tx10_document_folder.py` — `TestTx10DocumentFolderTree` (TransactionCase): идемпотентность дерева, изоляция проектов, complete_name, get_folder_by_code
- [ ] `tests/test_tx10_document_upload.py` — `TestTx10DocumentUpload` (TransactionCase): E2E wizard (4 типа файлов), needs_review, skipped dup, error handling
- [ ] Все существующие тесты `--test-tags tx10_ai` проходят без изменений
- [ ] `solar_project` тесты не нарушены: `solar.document` без `document_type_id` создаётся

### Manual Verification

- [ ] Открыть `project.project` → кнопка «Загрузити документи» видна
- [ ] Загрузить PDF-даташит инвертора → в сводке: `02_Інвертори`, `confidence ≥ 0.75`, статус `done`
- [ ] Загрузить XLSX с потреблением → `03_Споживання_та_рахунки`, статус `done`
- [ ] Загрузить .jpg → `01_Фото`, статус `done`
- [ ] Загрузить нераспознанный TXT → `05_Інше`, статус `needs_review`
- [ ] Повторная загрузка того же файла → статус `skipped`, новый `solar.document` не создан
- [ ] Smart-button «Папки» на проекте открывает дерево с папками и документами

---

## Out of Scope

- LLM-fallback для low-confidence (F2, отложено)
- OCR/vision для сканов (F3, отложено)
- Discuss-бот прием вложений (F1, отложено)
- Enterprise-мост `documents.document` (F4, отложено)
- `solar_project` изменения — только через `_inherit` в `tx10_ai`
- Русский и другие .po файлы кроме `uk.po`
- Кастомный лимит размера файла (используем Odoo standard)
