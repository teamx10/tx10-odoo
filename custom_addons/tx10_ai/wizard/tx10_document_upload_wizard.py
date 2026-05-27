from odoo import _, fields, models


class Tx10DocumentUploadWizard(models.TransientModel):
    _name = "tx10.document.upload.wizard"
    _description = "Upload Documents"

    project_id = fields.Many2one("project.project", required=True, readonly=True)
    attachment_ids = fields.Many2many(
        "ir.attachment",
        string="Files",
        help="Files to upload. Duplicates (same name + size) are silently skipped.",
    )

    def action_upload(self):
        SolarDoc = self.env["solar.document"]
        for attachment in self.attachment_ids:
            existing = SolarDoc.search(
                [
                    ("project_id", "=", self.project_id.id),
                    ("attachment_id.name", "=", attachment.name),
                    ("attachment_id.file_size", "=", attachment.file_size),
                ],
                limit=1,
            )
            if not existing:
                SolarDoc.create({
                    "name": attachment.name,
                    "project_id": self.project_id.id,
                    "attachment_id": attachment.id,
                    "ai_classified": False,
                })
        return {
            "type": "ir.actions.act_window",
            "name": _("Documents"),
            "res_model": "solar.document",
            "view_mode": "list,form",
            "domain": [("project_id", "=", self.project_id.id)],
        }
