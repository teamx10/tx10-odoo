# Security: TeamX10 AI — Auto-foldering

> Task: `2026-05-26-ai-document-foldering`
> Date: 2026-05-26

---

## Threat Surface

| # | Вектор | Компонент | Митигация |
|---|--------|-----------|-----------|
| S1 | Zip bomb (DOCX/XLSX) | `tx10_document_classifier._extract_docx/xlsx` | Проверка `ZipInfo.file_size` per member ПЕРЕД `.read()` (не len сжатых данных) |
| S2 | XML injection / XXE | `_extract_docx`, `_extract_xlsx` (stdlib ET) | Python `xml.etree.ElementTree` по умолчанию не обрабатывает external entities — безопасен |
| S3 | Path traversal | ZIP-архивы DOCX/XLSX | Открываем только конкретный путь (`"word/document.xml"`, `"xl/sharedStrings.xml"`) — без `extractall()` |
| S4 | Overflow binary | PDF парсер | pypdf читает первые 3 страницы; исключение catches all |
| S5 | Cross-project data leak | `solar.document`, `tx10.document.folder` | Все записи несут `project_id`; ACL и `domain` всегда фильтруют по проекту |
| S6 | Privilege escalation | `_ensure_tree()` вызывает `sudo()` | Scope минимален: только create `tx10.document.folder` для текущего проекта; никаких других операций с sudo |
| S7 | Arbitrary file read | text extraction — только `content_bytes` из wizard | Байты передаются явно; нет обращений к файловой системе (всё через `ir.attachment.datas`) |
| S8 | Large file DoS | Загрузка огромных файлов | Используем стандартный лимит Odoo `ir.attachment`; никакого кастомного лимита не вводим (решение Q4) |

---

## Zip Bomb Guard (S1) — детали реализации

Классический zip-bomb — это небольшой сжатый файл (<<50 МБ), который разворачивается в гигабайты при распаковке. Проверка `len(content_bytes)` на входе **НЕ защищает** от этого вектора.

Правильная защита — проверять несжатый размер каждого члена zip через `ZipInfo.file_size` **перед** вызовом `.read()`:

```python
MAX_MEMBER_BYTES = 50 * 1024 * 1024  # 50 MB per member, uncompressed

def _safe_read_zip_member(z: zipfile.ZipFile, name: str) -> bytes:
    info = z.getinfo(name)
    if info.file_size > MAX_MEMBER_BYTES:
        raise ValueError(f"Member {name!r} uncompressed size {info.file_size} exceeds limit")
    return z.read(name)

# В _extract_docx():
with zipfile.ZipFile(io.BytesIO(content_bytes)) as z:
    with io.BytesIO(_safe_read_zip_member(z, "word/document.xml")) as f:
        ...

# В _extract_xlsx():
with zipfile.ZipFile(io.BytesIO(content_bytes)) as z:
    if "xl/sharedStrings.xml" in z.namelist():
        data = _safe_read_zip_member(z, "xl/sharedStrings.xml")
        ...
```

Входной `len(content_bytes) > 50MB` можно оставить как fast-reject для явно больших файлов, но основная защита — `ZipInfo.file_size`.

---

## XML / XXE Analysis (S2)

Python `xml.etree.ElementTree`:
- **Не загружает** external DTD и external entities (XXE-safe).
- **Уязвим** к DoS через exponential entity expansion («billion laughs»). Файлы DOCX/XLSX являются пользовательским input — злоумышленник может загрузить crafted DOCX с вредоносным `word/document.xml`.
- Python's `expat` (используется внутри ET) начиная с версии 2.4.0 имеет встроенную защиту от billion-laughs через `XML_FEATURE_BILLION_LAUGHS_ATTACK_PROTECTION`. Python 3.10+ включает её. **Рекомендуется проверить версию expat при деплое**: `python -c "import pyexpat; print(pyexpat.EXPAT_VERSION)"`.
- **Альтернатива для hardened-окружений:** `defusedxml` — drop-in замена ET с явной защитой от всех XML-атак. Достаточно заменить `import xml.etree.ElementTree as ET` на `import defusedxml.ElementTree as ET`. Пакет не входит в stdlib — требует добавления в `requirements.txt`.
- В MVP: stdlib ET приемлемо при Python 3.10+ (expat 2.4.0+). Весь parse в `try/except` — ошибка → `""` → `needs_review`.

---

## PDF Parser Safety (S4)

- `pypdf` (и `PyPDF2`) работают в pure Python — нет C-расширений с memory corruption.
- Первые 3 страницы: ограничивает время парсинга.
- Весь вызов в `try/except` — malformed PDF → `""` → `needs_review`.

---

## ACL Design (S5, S6)

```
ir.model.access.csv (новые строки):

tx10.document.folder + group_project_user   → read only (1,0,0,0)
tx10.document.folder + group_project_manager → full CRUD (1,1,1,1)
tx10.document.upload.wizard + group_project_user  → full (1,1,1,1) — TransientModel, WizardModel
tx10.document.result.line   + group_project_user  → full (1,1,1,1) — TransientModel
```

Обоснование группировки:
- `group_project_user` = read folders — достаточно для просмотра структуры в smart-button.
- `group_project_manager` = CRUD folders — нужно для ручного создания/редактирования папок (соответствует паттерну `solar_project`).
- Wizard открывает только `group_project_user` (загружать документы может любой участник проекта).

---

## Cross-Project Constraint (S5)

В `models/solar_document.py` добавить constraint:

```python
@api.constrains("folder_id", "project_id")
def _check_folder_project(self):
    for rec in self:
        if rec.folder_id and rec.folder_id.project_id != rec.project_id:
            raise ValidationError(
                _("Folder %(folder)s belongs to a different project.", folder=rec.folder_id.name)
            )
```

Без этого constraint возможна ситуация, когда wizard по ошибке (или при race condition) присваивает папку другого проекта.

---

## `sudo()` Scope Justification (S6)

`_ensure_tree()` вызывается в контексте wizard, где у пользователя может быть только `group_project_user` (read-only для folder). Но seed дерева — операция инициализации, аналогичная `ir.config_parameter`.

Scope `sudo()` ограничен:
```python
Folder = self.sudo()
# только search() и create() на tx10.document.folder
# project_id явно передаётся, без возможности доступа к другим проектам
```

**TOCTOU анализ**: `project_id` в wizard — поле `Many2one project.project`. Odoo ORM:
1. Валидирует ссылку при записи через record rules (`base_setup.group_project_user` имеет read-доступ только к своим проектам)
2. `_ensure_tree(project)` получает `project` как реальный recordset (не ID строку), прошедший ORM-слой
3. Злоумышленник с `group_project_user` не может указать `project_id` произвольного чужого проекта, которого у него нет в домене — ORM проверит это при form submit

Таким образом, `sudo()` в `_ensure_tree()` не открывает TOCTOU: проверка доступа к проекту происходит на уровне wizard.project_id до вызова `_ensure_tree`. Scope корректен.

Альтернатива: дать `group_project_user` право create через ACL — но тогда пользователь сможет создавать папки вне wizard, что нежелательно. `sudo()` внутри `_ensure_tree` — корректный выбор.

---

## `document_type_id` → Optional: Risk Analysis

**Изменение:** `required=False` через `_inherit` в `tx10_ai` (ORM-only override).

**Риски:**
1. `solar_project` views с `mandatory="1"` на `document_type_id` — НЕ переопределяется через `_inherit`; view-level `mandatory` остаётся до явного `inherit_view`.
2. `solar_project` Python-код, обращающийся к `doc.document_type_id.code` без null-guard — может упасть с `AttributeError`.
3. Существующие `solar.document` в БД с `document_type_id IS NOT NULL` — не затронуты (поле остаётся nullable в БД).

**Тестовое покрытие:** `test_tx10_document_upload.py` создаёт `solar.document` без `document_type_id` и проверяет отсутствие исключений.

---

## Pre-merge Security Checklist

- [ ] `_safe_read_zip_member()` реализован и используется в `_extract_docx` и `_extract_xlsx` — проверяет `ZipInfo.file_size > MAX_MEMBER_BYTES` перед `.read()`
- [ ] `len(content_bytes) > 50MB` fast-reject присутствует как дополнительный первый барьер
- [ ] `except Exception: return ""` покрывает все extraction paths
- [ ] `_check_folder_project` constraint реализован в `solar_document.py`
- [ ] ACL CSV содержит 4 строки; нет строк с full access для `group_project_user` на folder model
- [ ] `sudo()` используется только в `_ensure_tree()`, не в wizard action
- [ ] `attachment.raw` используется вместо `attachment.datas` для получения байтов
- [ ] `ai_extracted_data` получает `result` (dict), не `str(result[...])`
- [ ] Python expat ≥ 2.4.0 в окружении (или `defusedxml` добавлен в requirements.txt)
