# Technical: TeamX10 AI — Auto-foldering

> Task: `2026-05-26-ai-document-foldering`
> Date: 2026-05-26

---

## Implementation Order

### T1 — Data Layer

**T01: `models/tx10_document_folder.py`**

```python
from odoo import models, fields, api

FOLDER_TEMPLATE = [
    # (path_parts_list, folder_code)
    (["01_Вхідні_дані"], "root_input"),
    (["01_Вхідні_дані", "01_Опитувальний_лист"], "survey"),
    (["01_Вхідні_дані", "01_Опитувальний_лист", "01_Оригінал"], "survey_orig"),
    (["01_Вхідні_дані", "01_Опитувальний_лист", "02_Додатки"], "survey_attachments"),
    (["01_Вхідні_дані", "02_Технічні_каталоги"], "catalogs"),
    (["01_Вхідні_дані", "02_Технічні_каталоги", "01_Сонячні_модулі"], "01_Сонячні_модулі"),
    (["01_Вхідні_дані", "02_Технічні_каталоги", "02_Інвертори"], "02_Інвертори"),
    (["01_Вхідні_дані", "02_Технічні_каталоги", "03_Акумулятори"], "03_Акумулятори"),
    (["01_Вхідні_дані", "02_Технічні_каталоги", "04_BMS_PDU"], "04_BMS_PDU"),
    (["01_Вхідні_дані", "02_Технічні_каталоги", "05_BOS_обладнання"], "05_BOS_обладнання"),
    (["01_Вхідні_дані", "02_Технічні_каталоги", "06_Інше_обладнання"], "06_Інше_обладнання"),
    (["01_Вхідні_дані", "03_Матеріали_від_замовника"], "customer_materials"),
    (["01_Вхідні_дані", "03_Матеріали_від_замовника", "01_Фото"], "01_Фото"),
    (["01_Вхідні_дані", "03_Матеріали_від_замовника", "02_Схеми"], "02_Схеми"),
    (["01_Вхідні_дані", "03_Матеріали_від_замовника", "03_Споживання_та_рахунки"], "03_Споживання_та_рахунки"),
    (["01_Вхідні_дані", "03_Матеріали_від_замовника", "04_ТУ_договори_облік"], "04_ТУ_договори_облік"),
    (["01_Вхідні_дані", "03_Матеріали_від_замовника", "05_Інше"], "05_Інше"),
    (["03_Розрахунки"], "root_calculations"),
    (["03_Розрахунки", "02_PVsyst"], "pvsyst"),
    (["03_Розрахунки", "02_PVsyst", "01_Reports"], "pvsyst_reports"),
    (["03_Розрахунки", "02_PVsyst", "02_Project_Files"], "pvsyst_projects"),
    (["03_Розрахунки", "02_PVsyst", "03_Export"], "pvsyst_export"),
    (["03_Розрахунки", "04_SolarEdge_Designer"], "solaredge"),
    (["03_Розрахунки", "05_K2"], "k2"),
]

class Tx10DocumentFolder(models.Model):
    _name = "tx10.document.folder"
    _description = "Document Folder"
    _parent_name = "parent_id"
    _parent_store = True
    _rec_name = "complete_name"
    _order = "complete_name"

    name = fields.Char(required=True)
    project_id = fields.Many2one("project.project", required=True, ondelete="cascade", index=True)
    parent_id = fields.Many2one("tx10.document.folder", ondelete="cascade", index=True)
    child_ids = fields.One2many("tx10.document.folder", "parent_id")
    parent_path = fields.Char(index=True)
    complete_name = fields.Char(compute="_compute_complete_name", store=True, recursive=True)
    folder_code = fields.Char(index=True)
    document_ids = fields.One2many("solar.document", "folder_id")

    @api.depends("name", "parent_id.complete_name")
    def _compute_complete_name(self):
        for folder in self:
            if folder.parent_id:
                folder.complete_name = f"{folder.parent_id.complete_name} / {folder.name}"
            else:
                folder.complete_name = folder.name

    @api.model
    def _ensure_tree(self, project):
        # Build idempotent folder tree for project using FOLDER_TEMPLATE
        # Uses sudo() because project_user may not have create rights
        Folder = self.sudo()
        cache = {}  # path_tuple → folder record

        for path_parts, folder_code in FOLDER_TEMPLATE:
            key = tuple(path_parts)
            parent_key = tuple(path_parts[:-1]) if len(path_parts) > 1 else None
            parent = cache.get(parent_key) if parent_key else None

            domain = [("project_id", "=", project.id), ("name", "=", path_parts[-1])]
            if parent:
                domain.append(("parent_id", "=", parent.id))
            else:
                domain.append(("parent_id", "=", False))

            folder = Folder.search(domain, limit=1)
            if not folder:
                vals = {"name": path_parts[-1], "project_id": project.id, "folder_code": folder_code}
                if parent:
                    vals["parent_id"] = parent.id
                folder = Folder.create(vals)
            elif not folder.folder_code:
                folder.folder_code = folder_code

            cache[key] = folder

        return cache

    @api.model
    def get_folder_by_code(self, project, code):
        return self.sudo().search(
            [("project_id", "=", project.id), ("folder_code", "=", code)], limit=1
        )
```

**T02: `models/solar_document.py`** (inherit extension)

```python
from odoo import models, fields

class SolarDocumentTx10(models.Model):
    _inherit = "solar.document"

    folder_id = fields.Many2one(
        "tx10.document.folder",
        string="Folder",
        ondelete="set null",
    )
    needs_review = fields.Boolean(default=False)

    # Override to make document_type_id optional when tx10_ai is installed
    document_type_id = fields.Many2one(required=False)
```

**T03: `security/ir.model.access.csv`** (добавить строки)

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_tx10_document_folder_user,tx10.document.folder user,model_tx10_document_folder,project.group_project_user,1,0,0,0
access_tx10_document_folder_manager,tx10.document.folder manager,model_tx10_document_folder,project.group_project_manager,1,1,1,1
access_tx10_document_upload_wizard_user,tx10.document.upload.wizard user,model_tx10_document_upload_wizard,project.group_project_user,1,1,1,1
access_tx10_document_result_line_user,tx10.document.result.line user,model_tx10_document_result_line,project.group_project_user,1,1,1,1
```

---

### T2 — Classifier + Wizard

**T04: `models/tx10_document_classifier.py`**

```python
import io
import zipfile
import xml.etree.ElementTree as ET

# Bilingual EN/UA keyword rules (port from SuperTEO + TEO_Solar disambiguation)
KEYWORD_RULES = {
    "SOLAR_MODULE": [
        "solar panel", "solar module", "pv module", "photovoltaic",
        "сонячна панель", "сонячний модуль", "фотоелектричний", "pv panel",
        "монокристал", "полікристал", "monocrystalline", "polycrystalline",
        "jinko", "longi", "canadian solar", "ja solar", "risen",
    ],
    "INVERTER": [
        "inverter", "інвертор", "grid-tie", "string inverter",
        "sma", "fronius", "huawei luna", "solaredge", "growatt",
        "on-grid", "off-grid",
        # disambiguation: hybrid must come before bare "grid" check
        "hybrid inverter", "гібридний інвертор", "гібрид",
    ],
    "BATTERY": [
        "battery", "акумулятор", "акумуляторна батарея", "lithium",
        "lifepo4", "byd", "pylontech", "battery storage", "накопичувач енергії",
        "energy storage", "ємність акумулятора",
    ],
    "BMS": [
        "bms", "battery management", "pdu", "управління акумулятором",
        "балансування", "balance", "charge controller",
    ],
    "BOS": [
        "mounting", "структура кріплення", "рейка", "rail", "cable",
        "connector", "mc4", "combiner box", "disconnect switch",
        "захисний пристрій", "bos",
    ],
    "CONSUMPTION": [
        "consumption", "invoice", "рахунок", "споживання", "тариф",
        "electricity bill", "рахунок за електроенергію", "kwh",
        "лічильник", "meter", "навантаження", "load profile",
    ],
    "PERMIT": [
        "permit", "contract", "договір", "ту", "технічні умови",
        "agreement", "технічне завдання", "дозвіл", "обліковий",
        "meter agreement", "підключення до мережі",
    ],
    "SCHEME": [
        "scheme", "schematic", "схема", "wiring diagram", "однолінійна",
        "single line", "plan", "план", "layout", "розташування",
    ],
    "PVSYST": [
        "pvsyst", "pv syst", "simulation", "yield", "pr ratio",
        "performance ratio", "годовий виробіток", "annual yield",
        "pvgis", "метеодані", "irradiance",
    ],
    "SURVEY": [
        "questionnaire", "опитувальний лист", "survey", "анкета",
        "технічне завдання клієнта", "вимоги замовника",
    ],
}

PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".heic", ".tif", ".tiff"}

CATEGORY_TO_FOLDER_CODE = {
    "SOLAR_MODULE": "01_Сонячні_модулі",
    "INVERTER":     "02_Інвертори",
    "BATTERY":      "03_Акумулятори",
    "BMS":          "04_BMS_PDU",
    "BOS":          "05_BOS_обладнання",
    "PHOTO":        "01_Фото",
    "SCHEME":       "02_Схеми",
    "CONSUMPTION":  "03_Споживання_та_рахунки",
    "PERMIT":       "04_ТУ_договори_облік",
    "PVSYST":       "pvsyst_reports",
    "SURVEY":       "survey_orig",
    "UNKNOWN":      "05_Інше",
}

CONFIDENCE_THRESHOLD = 0.70


def extract_text(filename: str, content_bytes: bytes) -> str:
    """Extract text preview from file bytes. Returns empty string on failure."""
    ext = _get_ext(filename)

    if ext in PHOTO_EXTENSIONS:
        return ""

    if ext == ".pdf":
        return _extract_pdf(content_bytes)

    if ext == ".docx":
        return _extract_docx(content_bytes)

    if ext in (".xlsx", ".xls"):
        return _extract_xlsx(content_bytes)

    # Plain text formats
    if ext in (".txt", ".csv", ".json", ".xml", ".yaml", ".yml", ".md"):
        try:
            return content_bytes[:10000].decode("utf-8", errors="replace")
        except Exception:
            return ""

    return ""


def classify(text: str, filename: str) -> dict:
    """
    Classify document by keyword scoring.
    Returns: {category, confidence, reasons, document_type_code}
    """
    ext = _get_ext(filename)

    if ext in PHOTO_EXTENSIONS:
        return {
            "category": "PHOTO",
            "confidence": 1.0,
            "reasons": ["photo by extension"],
            "document_type_code": "photo",
        }

    corpus = f" {filename} {text} ".casefold()
    has_text = bool(text.strip())

    scores = {}
    reasons_map = {}

    for category, keywords in KEYWORD_RULES.items():
        score = 0
        matched = []
        for kw in keywords:
            if kw.casefold() in corpus:
                score += 1
                matched.append(kw)
        if score > 0:
            scores[category] = score
            reasons_map[category] = matched

    if not scores:
        confidence = 0.65 if not has_text else 0.65
        return {
            "category": "UNKNOWN",
            "confidence": confidence,
            "reasons": [],
            "document_type_code": "unknown",
        }

    best_cat = max(scores, key=lambda c: scores[c])
    best_score = scores[best_cat]

    confidence = 0.65 + 0.1 * min(best_score, 3)
    if has_text:
        confidence = max(confidence, 0.80)

    if confidence < CONFIDENCE_THRESHOLD:
        best_cat = "UNKNOWN"

    folder_code = CATEGORY_TO_FOLDER_CODE.get(best_cat, "05_Інше")

    return {
        "category": folder_code,
        "confidence": confidence,
        "reasons": reasons_map.get(best_cat, []),
        "document_type_code": best_cat.lower(),
    }


def _get_ext(filename: str) -> str:
    import os
    return os.path.splitext(filename.lower())[1]


def _extract_pdf(content_bytes: bytes) -> str:
    try:
        try:
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(content_bytes))
        except ImportError:
            import PyPDF2 as pypdf
            reader = pypdf.PdfReader(io.BytesIO(content_bytes))

        pages = reader.pages[:3]
        return " ".join(p.extract_text() or "" for p in pages)
    except Exception:
        return ""


_MAX_ZIP_MEMBER_BYTES = 50 * 1024 * 1024  # 50 MB uncompressed per member


def _safe_zip_read(z: zipfile.ZipFile, member_name: str) -> bytes:
    info = z.getinfo(member_name)
    if info.file_size > _MAX_ZIP_MEMBER_BYTES:
        raise ValueError(f"Member {member_name!r} uncompressed size exceeds limit")
    return z.read(member_name)


def _extract_docx(content_bytes: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(content_bytes)) as z:
            data = _safe_zip_read(z, "word/document.xml")
            tree = ET.fromstring(data)
            ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
            texts = [t.text or "" for t in tree.findall(".//w:t", ns)]
            return " ".join(texts)[:10000]
    except Exception:
        return ""


def _extract_xlsx(content_bytes: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(content_bytes)) as z:
            parts = []
            if "xl/sharedStrings.xml" in z.namelist():
                data = _safe_zip_read(z, "xl/sharedStrings.xml")
                tree = ET.fromstring(data)
                texts = [t.text or "" for t in tree.findall(".//{*}t")]
                parts.extend(texts[:500])
            return " ".join(parts)[:10000]
    except Exception:
        return ""
```

**T05: `wizard/tx10_document_upload_wizard.py`**

```python
import base64
from odoo import models, fields, api, _
from ..models.tx10_document_classifier import extract_text, classify

class Tx10DocumentUploadWizard(models.TransientModel):
    _name = "tx10.document.upload.wizard"
    _description = "Upload and Classify Documents"

    project_id = fields.Many2one("project.project", required=True, readonly=True)
    attachment_ids = fields.Many2many(
        "ir.attachment",
        string="Files",
        help="Attach files to classify and file into project folders",
    )
    result_line_ids = fields.One2many("tx10.document.result.line", "wizard_id", readonly=True)
    state = fields.Selection([("upload", "Upload"), ("done", "Done")], default="upload")

    def action_classify_and_file(self):
        project = self.project_id
        Folder = self.env["tx10.document.folder"]
        SolarDoc = self.env["solar.document"]
        lines = []

        Folder._ensure_tree(project)

        for attachment in self.attachment_ids:
            filename = attachment.name
            try:
                # Use attachment.raw — safe in any env context (bin_size=True returns "48 kB" from .datas)
                content_bytes = attachment.raw or b""

                # Duplicate check: same name + size in project
                existing = SolarDoc.search([
                    ("project_id", "=", project.id),
                    ("attachment_id.name", "=", filename),
                    ("attachment_id.file_size", "=", attachment.file_size),
                ], limit=1)
                if existing:
                    lines.append({
                        "filename": filename,
                        "status": "skipped",
                        "confidence": 0.0,
                        "message": _("Duplicate — already exists in project"),
                    })
                    continue

                text = extract_text(filename, content_bytes)
                result = classify(text, filename)

                folder_code = result["category"]
                confidence = result["confidence"]
                needs_review = confidence < 0.70 or folder_code == "05_Інше"

                folder = Folder.get_folder_by_code(project, folder_code)
                if not folder:
                    folder = Folder.get_folder_by_code(project, "05_Інше")
                    needs_review = True

                doc = SolarDoc.create({
                    "name": filename,
                    "project_id": project.id,
                    "attachment_id": attachment.id,
                    "folder_id": folder.id,
                    "needs_review": needs_review,
                    "ai_classified": True,
                    # ai_extracted_data is fields.Json — must be dict/list, not str
                    "ai_extracted_data": result,
                })

                lines.append({
                    "filename": filename,
                    "folder_id": folder.id,
                    "confidence": confidence,
                    "status": "needs_review" if needs_review else "done",
                    "message": "",
                })

            except Exception as e:
                lines.append({
                    "filename": filename,
                    "status": "error",
                    "confidence": 0.0,
                    "message": str(e)[:200],
                })

        ResultLine = self.env["tx10.document.result.line"]
        for line_vals in lines:
            line_vals["wizard_id"] = self.id
            ResultLine.create(line_vals)

        self.state = "done"
        return {
            "type": "ir.actions.act_window",
            "res_model": "tx10.document.upload.wizard",
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }


class Tx10DocumentResultLine(models.TransientModel):
    _name = "tx10.document.result.line"
    _description = "Upload Result Line"

    wizard_id = fields.Many2one("tx10.document.upload.wizard", ondelete="cascade")
    filename = fields.Char()
    folder_id = fields.Many2one("tx10.document.folder")
    confidence = fields.Float(digits=(5, 2))
    status = fields.Selection([
        ("done", "Done"),
        ("needs_review", "Needs Review"),
        ("skipped", "Skipped"),
        ("error", "Error"),
    ])
    message = fields.Char()
```

---

## `tx10.ai.service` wrapper (опциональный, для совместимости с legacy contract)

В `models/tx10_ai_service.py` добавить метод в класс `Tx10AiService`:

```python
def classify_document_text(self, text, filename=""):
    """Thin wrapper around pure-Python classifier for ORM-model callers."""
    from .tx10_document_classifier import classify
    return classify(text, filename)
```

---

## Связывание с solar_project._run_ai_classify (будущее)

`solar.document._run_ai_classify()` вызывает `solar.ai.service` (отсутствует). В MVP этот путь спящий — точка входа = wizard. Реанимация через override `_run_ai_classify` в `solar_document.py`:

```python
def _run_ai_classify(self):
    # Override to use tx10.ai.service instead of absent solar.ai.service
    service = self.env["tx10.ai.service"]
    attachment = self.attachment_id
    if not attachment:
        return
    # Use attachment.raw — safe in any env context (bin_size=True breaks attachment.datas)
    content_bytes = attachment.raw or b""
    from .tx10_document_classifier import extract_text
    text = extract_text(attachment.name, content_bytes)
    result = service.classify_document_text(text, attachment.name)
    self.ai_classified = True
    # ai_extracted_data is fields.Json — must be dict, not str
    self.ai_extracted_data = result
```

Это F1 — в MVP не реализуем, но архитектура позволяет добавить без переписывания.
