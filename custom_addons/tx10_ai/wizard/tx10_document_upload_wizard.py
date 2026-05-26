from odoo import _, fields, models

from ..models.tx10_document_classifier import classify, extract_text


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
    has_needs_review = fields.Boolean(compute="_compute_has_needs_review")

    def _compute_has_needs_review(self):
        for wizard in self:
            wizard.has_needs_review = any(
                line.status == "needs_review" for line in wizard.result_line_ids
            )

    def action_classify_and_file(self):
        project = self.project_id
        Folder = self.env["tx10.document.folder"]
        SolarDoc = self.env["solar.document"]
        ResultLine = self.env["tx10.document.result.line"]

        Folder._ensure_tree(project)

        for attachment in self.attachment_ids:
            line_vals = self._process_attachment(attachment, project, Folder, SolarDoc)
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

    def _process_attachment(self, attachment, project, Folder, SolarDoc):
        filename = attachment.name
        try:
            return self._classify_and_create(attachment, filename, project, Folder, SolarDoc)
        except Exception as e:  # noqa: BLE001
            return {
                "filename": filename,
                "status": "error",
                "confidence": 0.0,
                "message": str(e)[:200],
            }

    def _classify_and_create(self, attachment, filename, project, Folder, SolarDoc):
        existing = SolarDoc.search([
            ("project_id", "=", project.id),
            ("attachment_id.name", "=", filename),
            ("attachment_id.file_size", "=", attachment.file_size),
        ], limit=1)
        if existing:
            return {
                "filename": filename,
                "status": "skipped",
                "confidence": 0.0,
                "message": _("Duplicate — already exists in project"),
            }

        content_bytes = attachment.raw or b""
        text = extract_text(filename, content_bytes)
        result = classify(text, filename)

        folder_code = result["category"]
        confidence = result["confidence"]
        needs_review = confidence < 0.70

        folder = Folder.get_folder_by_code(project, folder_code)
        if not folder:
            folder = Folder.get_folder_by_code(project, "05_Інше")
            needs_review = True

        SolarDoc.create({
            "name": filename,
            "project_id": project.id,
            "attachment_id": attachment.id,
            "folder_id": folder.id if folder else False,
            "needs_review": needs_review,
            "ai_classified": True,
            "ai_extracted_data": result,
        })

        return {
            "filename": filename,
            "folder_id": folder.id if folder else False,
            "confidence": confidence,
            "status": "needs_review" if needs_review else "done",
            "message": "",
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
