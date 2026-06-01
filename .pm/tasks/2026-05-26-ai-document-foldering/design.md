# TeamX10 AI — Auto-foldering: загрузка и автоклассификация документов проекта

## Context

Развиваем бота **TeamX10 AI** (модуль `custom_addons/tx10_ai`, Odoo 19.0 Community). Нужен самый базовый и главный кусок функционала по образцу проектов Subbotik24 (`SuperTEO`, `TEO_Solar`): **пользователь загружает один или несколько файлов в проект → классификатор определяет, что это за документ, и кладёт файл в правильную папку дерева проекта; нераспознанное падает в папку «Нераспознанное» и помечается на ручную проверку.**

Почему сейчас реально и недорого: модель данных уже наполовину построена в зависимости `solar_project` (`solar.document` с `attachment_id` + `ai_classified` + `ai_extracted_data`, метод-заглушка `_run_ai_classify` ждёт контракт `classify_document_text(text) → {document_type_code, confidence}`), а LLM-клиент `tx10.ai.service` (OpenRouter) уже есть. Недостаёт трёх звеньев: (1) дерево папок, (2) приём файлов, (3) классификатор + раскладка. Готовый детерминированный классификатор и дерево папок берём из Subbotik24 — не изобретаем.

---

## Locked decisions (зафиксировано с пользователем)

| # | Решение | Обоснование |
|---|---------|-------------|
| 1 | **Своя лёгкая модель папок** `tx10.document.folder` (self-ref `parent_id`/`child_ids`/`parent_path`), per-project, дерево сидируется из шаблона | Enterprise-модуль `documents` (DMS) в Community-сборке **отсутствует**; в ядре Odoo нет концепции «папки» для `ir.attachment`. Стандартный паттерн ядра. |
| 2 | **Шов сейчас, Enterprise-мост потом**: классификация (storage-agnostic) отделена от раскладки (filer). MVP — только Community-filer | YAGNI. Enterprise-мост (`documents.document`) = аддон-адаптер на ~50–100 строк позже, без переписывания фичи. |
| 3 | **Точка входа — синхронный wizard на `project.project`** (кнопка «Загрузить документы» → мультизагрузка → классификация → сводка). Движок вынесен в сервис | Существующий чат `tx10_ai` асинхронный (cron, задержка до минуты). Wizard детерминирован, тестируем. Бот в Discuss подключится к тому же движку позже. |
| 4 | **Классификатор — детерминированный, портируется из Subbotik24** (keyword-правила + формула `confidence = 0.65 + 0.1·min(score,3)`, floor 0.8 при наличии текста; порог **70%**). Без LLM в MVP | Пользователь: «правила берём из Subbotik24». SuperTEO даёт готовый код. Реализуем как `classify_document_text(...)` — совпадает с уже ожидаемым контрактом. LLM-fallback — будущее. |
| 5 | **Типы файлов из Subbotik24**: PDF/DOCX/XLSX/текст через извлечение (DOCX/XLSX — zip+XML, PDF — pypdf, первые 3 страницы); картинки → PHOTO по расширению; **OCR не делаем** | В SuperTEO OCR явно `OCR_NOT_IMPLEMENTED`. Минимум внешних зависимостей. |
| 6 | **Дерево TEO_Solar = источник истины** для категорий/папок. `solar.document.folder_id` — основная ось. `solar.document.type` делаем **необязательным** (через `_inherit` в `tx10_ai`, `solar_project` не трогаем) | Дерево, выбранное пользователем (оборудование-центричное: Модулі/Інвертори/Акумулятори/BMS/BOS), не покрывается 12 lifecycle-кодами из БД. Одна ось категоризации, минимум дублирования. |

Авто-решения (низкий риск, по верности референсу — можно оспорить на ревью плана): порог 70% (TEO_Solar); дубликаты (имя+размер) → `skipped`; дерево сидируется **идемпотентно по требованию** (при первой загрузке / по кнопке), не для всех проектов скопом; из дерева TEO_Solar берём только ветки, релевантные раскладке входящих документов (см. ниже) — `80_AI_WORKBENCH/`, `02_АНАЛІЗ/` и т.п. (MD-воркбенч) **не сидируем**.

---

## Архитектура (шов: classify → decide → file)

```
┌──────────────────────────────────────────────────────────────────────┐
│ project.project  [кнопка «Загрузить документы»]                        │
└───────────────┬──────────────────────────────────────────────────────┘
                │ открывает
                ▼
┌──────────────────────────────────────────────────────────────────────┐
│ tx10.document.upload.wizard  (TransientModel)                          │
│  • multi-file upload (ir.attachment)                                   │
│  • on confirm → для каждого файла:                                     │
└───────┬────────────────────────────────────────────────────────────────┘
        │ 1) extract text          2) classify             3) file
        ▼                          ▼                        ▼
┌────────────────┐      ┌────────────────────────┐   ┌────────────────────────┐
│ text extractor │      │ tx10.ai.service         │   │ filer (Community)       │
│ pdf/docx/xlsx  │─────▶│ .classify_document_text │──▶│ category → folder_id    │
│ /txt           │ text │  → {category,           │cat│ ensure tree exists      │
│ (SuperTEO порт)│      │     confidence,         │   │ create solar.document   │
└────────────────┘      │     document_type_code} │   │  (+ attachment + folder)│
                        │  (keyword rules, 70%)   │   └───────────┬─────────────┘
                        └────────────────────────┘               │
                                                                  ▼
                                              ┌────────────────────────────────┐
                                              │ tx10.document.folder (дерево)   │
                                              │  PRJ root → … → Нераспознанне   │
                                              └────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────────────────────────────────┐
│ Сводка в wizard: файл → папка, confidence, статус                      │
│  done / needs_review (<70% → Нераспознанное) / skipped(dup) / error    │
└──────────────────────────────────────────────────────────────────────┘
```

**Точка расширения под Enterprise (будущее):** filer — единственный слой, знающий про бэкенд. Аддон `tx10_ai_documents` подменит filer, чтобы класть в `documents.document`. Классификатор и wizard не меняются.

---

## Модель данных

```
tx10.document.folder                         solar.document  (расширяем через _inherit)
 ├─ name            Char                       ├─ folder_id   M2o tx10.document.folder  ← НОВОЕ
 ├─ project_id      M2o project.project        ├─ document_type_id  → required=False    ← ИЗМЕНЕНИЕ
 ├─ parent_id       M2o self                    │   (override атрибута в tx10_ai)
 ├─ child_ids       O2m self                    └─ (attachment_id, ai_classified,
 ├─ parent_path     Char (index, _parent_store)     ai_extracted_data — уже есть)
 ├─ complete_name   Char (computed, "A / B / C")
 ├─ folder_code     Char (стабильный ключ ветки дерева, для маппинга category→folder)
 └─ document_ids    O2m solar.document (inverse folder_id)
```

`_parent_name = "parent_id"`, `_parent_store = True` → стандартное дерево Odoo (как `res.partner.category`).

### Шаблон дерева (порт ветки входящих из `PROJECT_FOLDER_TREE.txt`, обрезанный до релевантного)
Питон-константа `FOLDER_TEMPLATE` (список путей с `folder_code`), материализуется на проект идемпотентно:
```
01_Вхідні_дані/01_Опитувальний_лист/{01_Оригінал, 02_Додатки}
01_Вхідні_дані/02_Технічні_каталоги/{01_Сонячні_модулі, 02_Інвертори, 03_Акумулятори,
                                      04_BMS_PDU, 05_BOS_обладнання, 06_Інше_обладнання}
01_Вхідні_дані/03_Матеріали_від_замовника/{01_Фото, 02_Схеми, 03_Споживання_та_рахунки,
                                           04_ТУ_договори_облік, 05_Інше ← «Нераспознанное»}
03_Розрахунки/02_PVsyst/{01_Reports, 02_Project_Files, 03_Export}
03_Розрахунки/04_SolarEdge_Designer
03_Розрахунки/05_K2
```

---

## Классификатор (порт из Subbotik24)

- **Где:** чистый helper `custom_addons/tx10_ai/models/tx10_document_classifier.py` (функции, легко юнит-тестировать) + тонкая обёртка-метод `tx10.ai.service.classify_document_text(text, filename="")`.
- **Контракт (совместим с тем, что ждёт `solar_project._run_ai_classify`):**
  `classify_document_text(text, filename) → {"category": <folder_code>, "confidence": float, "reasons": [...], "document_type_code": <legacy best-effort | "unknown">}`
- **Логика (порт `SuperTEO/document_classifier.py`):** картинки по расширению → PHOTO (Фото); иначе keyword-скоринг по `" {filename} {text} "` (casefold), `KEYWORD_RULES` (билингва EN/UA из SuperTEO + дизамбигуация hybrid/grid-инвертора из TEO_Solar); `confidence = 0.65 + 0.1·min(score,3)`, floor 0.8 если текст извлечён; **< 0.70 → category = Нераспознанне (05_Інше) + needs_review**.
- **Маппинг `category → folder_code`** = routing-таблица TEO_Solar (Solar module → 01_Сонячні_модулі, Inverter → 02_Інвертори, и т.д.; Unknown/<70% → 05_Інше).
- **Извлечение текста (порт `read_text_preview`):** txt/csv/json/xml/yaml — прямо; docx — zip + `word/document.xml`; xlsx — zip + `sharedStrings`/worksheets; pdf — pypdf (первые 3 стр.). Без текста (картинки/скан-pdf) → метаданные + needs_review/PHOTO.

---

## UI / command surface

| Поверхность | Где | Поведение |
|-------------|-----|-----------|
| Кнопка «Загрузить документы» | `project.project` form (`tx10_ai/views/project_project_views.xml`) | открывает wizard, прокидывает `project_id` |
| Wizard загрузки | `tx10.document.upload.wizard` + view | мультизагрузка → «Классифицировать» → сводка с таблицей файл/папка/уверенность/статус |
| Дерево папок | tree-view `tx10.document.folder` (smart-button «Папки» на проекте) | навигация по дереву, видны вложенные `solar.document` |
| Колонка «Папка» | list/form `solar.document` (через `_inherit` view) | показывает `folder_id` |

---

## Файлы (создать / изменить) — всё в `custom_addons/tx10_ai`

**Создать:**
- `models/tx10_document_folder.py` — модель `tx10.document.folder` + `FOLDER_TEMPLATE` + `_ensure_tree(project)` (идемпотентно) + `get_folder_by_code(project, code)`.
- `models/tx10_document_classifier.py` — `KEYWORD_RULES`, `CATEGORY_TO_FOLDER_CODE`, `classify()`, экстракторы текста (порт SuperTEO).
- `models/solar_document.py` — `_inherit = "solar.document"`: `folder_id`, `document_type_id` → `required=False`, хелпер постановки файла.
- `wizard/__init__.py`, `wizard/tx10_document_upload_wizard.py` — `tx10.document.upload.wizard` (поля: `project_id`, `attachment_ids`/строки; `action_classify()` → создаёт `solar.document` + filer; возвращает сводку).
- `views/tx10_document_folder_views.xml`, `views/tx10_document_upload_wizard_views.xml`.
- `security/ir.model.access.csv` — доступы к `tx10.document.folder` + wizard (роль `project.group_project_user`/`_manager`, как у остального tx10_ai).
- `tests/test_tx10_document_classifier.py` (юнит, порт кейсов SuperTEO), `tests/test_tx10_document_upload.py` (интеграция wizard + дерево + needs_review), `tests/test_tx10_document_folder.py` (идемпотентность дерева).

**Изменить:**
- `models/__init__.py`, `__init__.py` (+ `wizard`) — регистрация.
- `views/project_project_views.xml` (или новый) — кнопка + smart-button.
- `__manifest__.py` — добавить wizard/views/security в `data`; добавить `tx10.ai.service.classify_document_text` (новый метод, существующий файл `models/tx10_ai_service.py` опц. как обёртка).

**НЕ трогаем:** `custom_addons/solar_project/*` (изменение `required` — через override в `tx10_ai`).

---

## Декомпозиция (ответ на «нужно ли разбивать?»)

Да, разбить. Рекомендуемое деление **MVP на 2 задачи** + явно отложенные:

| Задача | Содержание | Зависит от |
|--------|-----------|-----------|
| **T1 — Data layer** | `tx10.document.folder` + `FOLDER_TEMPLATE` + идемпотентное `_ensure_tree` + `solar.document.folder_id` + `document_type_id`→optional + security + tree/smart-button views + тесты дерева | — |
| **T2 — Classify + Wizard** | порт классификатора + экстракторы + filer (category→folder) + upload-wizard + сводка + needs_review/dup + тесты классификатора и wizard | T1 |
| ~~F1~~ (отложено) | Discuss-бот: приём вложений в чате → тот же движок | T1,T2 |
| ~~F2~~ (отложено) | LLM-fallback для low-confidence (через `tx10.ai.service`) | T2 |
| ~~F3~~ (отложено) | OCR/vision для сканов и фото | T2 |
| ~~F4~~ (отложено) | Enterprise-мост `tx10_ai_documents` (filer → `documents.document`) | T2 |

T1+T2 = «самый базовый и главный функционал». Реалистично; основной риск — точность портированных keyword-правил на реальных документах (детерминированно → легко тюнить).

---

## Verification

1. **Юнит-классификатор:** `./odoo-bin -d <db> --test-tags :TestTx10DocumentClassifier --stop-after-init` — кейсы из SuperTEO (panel/inverter/battery/pvsyst/invoice/photo/unknown), проверка confidence и порога 70%.
2. **Идемпотентность дерева:** дважды вызвать `_ensure_tree(project)` → число папок не меняется, дубликатов нет.
3. **E2E wizard (HttpCase/Form):** создать проект → wizard с 3–4 файлами (распознаваемый PDF-даташит, xlsx-потребление, картинка, мусорный txt) → проверить: даташит в `02_Інвертори`, потребление в `03_Споживання`, картинка в `01_Фото`, мусор в `05_Інше` с `needs_review`; повтор того же файла → `skipped`.
4. **Ручная проверка UI:** запустить `./odoo-bin -d <db> -u tx10_ai --dev=all`, открыть проект → «Загрузить документы» → загрузить файлы → увидеть сводку и дерево с разложенными документами.
5. **Регрессия:** прогон существующих тестов `--test-tags tx10_ai`; убедиться, что `solar_project` не сломан (документы без `document_type_id` создаются).
6. **GitNexus:** `gitnexus_impact` на изменяемых символах (`solar.document`), `gitnexus_detect_changes()` перед коммитом.

---

## Open risks

- **Точность keyword-правил** на реальных UA/EN документах isolar — основной продуктовый риск; митигируется тюнингом таблиц и (позже) LLM-fallback (F2).
- **`document_type_id` → optional** меняет инвариант `solar_project`; проверить, что его views/логика не падают на пустом типе (тест #5).
- **pypdf в окружении** — подтвердить наличие либы (есть в SuperTEO-стеке); при отсутствии PDF-текста файл уходит в needs_review (graceful).
- **`solar.ai.service` vs `tx10.ai.service`**: legacy `_run_ai_classify` зовёт `solar.ai.service` (его нет) — в MVP путь остаётся спящим (entry point = wizard). Реанимация — опционально позже.

---

## Next (после утверждения)

Plan mode ON → выйти из plan mode, в свежей сессии: `/tx2:create-task <этот plan-файл>`. Не чейнить create-task в этой сессии.
