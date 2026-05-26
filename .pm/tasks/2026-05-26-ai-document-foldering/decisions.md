# Decisions — 2026-05-26-ai-document-foldering

## Locked (from brainstorm design)

| # | Question | Decision |
|---|----------|----------|
| D1 | Folder model | Custom `tx10.document.folder` (self-ref parent_id/child_ids/parent_path), per-project. Enterprise DMS absent in Community. |
| D2 | Enterprise bridge | Seam now (classify ↔ filer separation), actual bridge deferred as separate task. |
| D3 | Upload entry point | Synchronous wizard on `project.project`. Engine in service for later Discuss reuse. |
| D4 | Classification method | Deterministic keyword rules ported from Subbotik24 (SuperTEO). No LLM in MVP. |
| D5 | File types | PDF/DOCX/XLSX/text via extraction; images → PHOTO by extension. No OCR. |
| D6 | Taxonomy | TEO_Solar folder tree as truth. `document_type_id` made optional via `_inherit`. `solar_project` not touched. |

## Resolved in spec gray-zone cascade (2026-05-26)

| # | Question | Decision | Rationale |
|---|----------|----------|-----------|
| Q1 | pypdf availability | PyPDF2/PyPDF already in requirements.txt; use `try pypdf → PyPDF2` fallback (SuperTEO pattern) | Confirmed in requirements.txt |
| Q2 | document_type_id migration | No DB migration needed; Many2one required=True is ORM-level only, not NOT NULL constraint | Odoo ORM convention |
| Q3 | Wizard UX (preview vs post-file) | Auto-file first, then show summary (Option B — YAGNI, consistent with "автоматически") | Simpler wizard state |
| Q4 | File size limit | Use Odoo standard ir.attachment upload limits; no custom limit in MVP | Defer custom limits |
| Q5 | Zip bomb protection | Check content size ≤ 50MB before zipfile parsing; failure → needs_review | Security hygiene |
| Q6 | ACL | project.group_project_user = read folders; project.group_project_manager = CRUD folders + upload | Mirrors solar.document pattern |
| Q7 | Branch name | `feat/tx10-ai-foldering` | Convention: feat/<slug> |
| Q8 | complete_name separator | ` / ` | TEO_Solar path convention |
| Q9 | Duplicate detection | Compare ir.attachment.name + file_size among existing solar.documents in project | SuperTEO pattern |
| Q10 | Folder names language | Ukrainian (TEO_Solar convention, domain product) | Reference project |
