from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SolarDocumentTx10(models.Model):
    _inherit = "solar.document"

    folder_id = fields.Many2one(
        "tx10.document.folder",
        string="Folder",
        ondelete="set null",
    )
    needs_review = fields.Boolean(default=False)
    document_type_id = fields.Many2one(required=False)

    @api.constrains("folder_id", "project_id")
    def _check_folder_project(self):
        for rec in self:
            if rec.folder_id and rec.folder_id.project_id != rec.project_id:
                raise ValidationError(
                    _("Folder %(folder)s belongs to a different project.", folder=rec.folder_id.name),
                )
