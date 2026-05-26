# Review Guide — 2026-05-26-ai-document-foldering

**Task:** TeamX10 AI — Auto-foldering: загрузка и автоклассификация документов проекта  
**Branch:** `feat/tx10-ai-foldering` (base: `develop`)  
**PR target:** `develop`

---

## Spec Gate Summary

| Document | Gate | Iterations | Status |
|----------|------|-----------|--------|
| spec.md | spec-reviewer | 1 | ✅ PASS |
| architecture.md | spec-reviewer | 1 | ✅ PASS |
| technical.md | spec-reviewer | 3 | ✅ PASS (2 fixes: attachment.raw, ai_extracted_data dict) |
| security.md | spec-reviewer | 2 | ✅ PASS (3 fixes: zip bomb, XXE, sudo TOCTOU) |
| test-plan.md | spec-reviewer | 1 | ✅ PASS |
| docs-plan.md | spec-reviewer | 1 | ✅ PASS |
| tasks.md | spec-reviewer | 1 | ✅ PASS |

---

## Key Decisions (for reviewer context)

| # | Решение |
|---|---------|
| D1 | Своя модель `tx10.document.folder` (_parent_store=True) — Enterprise DMS отсутствует |
| D2 | Classify-filer seam: pure-Python classify + ORM filer, Enterprise-bridge deferred |
| D3 | Entry point: синхронный wizard на project.project |
| D4 | Детерминированный классификатор (keyword rules), порог 70%, без LLM |
| D5 | PDF/DOCX/XLSX/text через extraction; images → PHOTO by extension; OCR not in MVP |
| D6 | TEO_Solar tree — источник истины; document_type_id → optional via _inherit |
| Q5 | Zip bomb guard: ZipInfo.file_size per member before .read() |
| Q6 | ACL: project_user=read folder; project_manager=CRUD; both=wizard |

---

## Reviewer Checklist (при ревью PR)

### Data Layer (T1)
- [ ] `tx10.document.folder`: `_parent_store=True`, `_parent_name="parent_id"`, `complete_name` computed с `recursive=True`
- [ ] `_ensure_tree()`: идемпотентно (search before create), `sudo()` scope ограничен
- [ ] `solar_document.py`: `folder_id` ondelete=set null, `document_type_id` required=False, `@api.constrains` cross-project
- [ ] ACL: 4 строки в ir.model.access.csv (folder×2 + wizard×1 + result_line×1)

### Classifier (T2)
- [ ] `KEYWORD_RULES`: билингва EN/UA, 8+ категорий
- [ ] Confidence formula: `0.65 + 0.1*min(score,3)`, floor 0.80 с текстом, порог 0.70
- [ ] `_safe_zip_read()`: ZipInfo.file_size > MAX_MEMBER_BYTES перед .read()
- [ ] Extractors: PDF через pypdf/PyPDF2 (fallback), DOCX/XLSX через zip+ET.fromstring

### Wizard (T2)
- [ ] `attachment.raw or b""` — НЕ `attachment.datas`
- [ ] `ai_extracted_data = result` (dict) — НЕ `str(result[...])`
- [ ] Duplicate check: name + file_size в проекте
- [ ] `needs_review=True` при confidence < 0.70 или folder = 05_Інше

### Tests
- [ ] Classifier unit tests без DB: формула, threshold, photo, unknown
- [ ] Folder tree: идемпотентность x2, изоляция проектов
- [ ] Wizard E2E: 4 типа файлов, dup, error, document_type_id=False regression

---

## Open Risks (follow-up после MVP)

| Риск | Статус | Follow-up |
|------|--------|-----------|
| Точность keyword-rules на реальных UA-документах | Открыт | F2: LLM-fallback (будущая задача) |
| solar_project views на пустом document_type_id | Покрыт тестом | Регрессия при `solar_project` update |
| pypdf доступность в production | Подтверждена (requirements.txt) | — |
| defusedxml для billion-laughs hardening | Необязательно для MVP | F-security task при изменении threat model |
| Enterprise DMS bridge | Архитектура готова | F4: tx10_ai_documents addon |
