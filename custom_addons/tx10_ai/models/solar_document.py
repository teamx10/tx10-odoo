import logging

from odoo import _, api, fields, models

from .tx10_document_extractor import extract_text as _extract_text

_logger = logging.getLogger(__name__)

_CONFIDENCE_THRESHOLD = 0.70


class SolarDocumentTx10(models.Model):
    _inherit = "solar.document"

    needs_review = fields.Boolean(default=False)
    document_type_id = fields.Many2one(required=False)

    def _run_ai_classify(self):
        """Override solar_project stub: classify via LLM using tx10.ai.service."""
        service = self.env["tx10.ai.service"].sudo()
        active_types = self.env["solar.document.type"].sudo().search([("active", "=", True)])
        unknown_type = active_types.filtered(lambda t: t.code == "unknown")[:1]

        for rec in self:
            rec._classify_one(service, active_types, unknown_type)

    def _classify_one(self, service, active_types, unknown_type):
        try:
            self._do_classify(service, active_types, unknown_type)
        except Exception:
            _logger.exception("tx10_ai: _run_ai_classify failed for document %s", self.id)
            if unknown_type:
                self.document_type_id = unknown_type.id
            self.needs_review = True
            self.ai_classified = True

    def _do_classify(self, service, active_types, unknown_type):
        attachment = self.attachment_id
        text = ""
        if attachment and attachment.raw:
            text = _extract_text(attachment.name or "", attachment.raw)

        result = service.classify_document_text(
            text,
            filename=attachment.name if attachment else "",
            types=active_types,
        )

        code = result.get("document_type_code", "unknown")
        confidence = float(result.get("confidence", 0.0))
        doc_type = active_types.filtered(lambda t, c=code: t.code == c)[:1]

        if doc_type and code != "unknown" and confidence >= _CONFIDENCE_THRESHOLD:
            self.document_type_id = doc_type.id
            self.needs_review = False
        else:
            if unknown_type:
                self.document_type_id = unknown_type.id
            self.needs_review = True
            self.activity_schedule(
                "mail.mail_activity_data_todo",
                summary=_("Перевірити тип документа"),
                note=_("AI confidence: %(c)s — manual classification required.", c=f"{confidence:.0%}"),
            )

        self.ai_classified = True
        self.ai_extracted_data = result

    @api.model
    def _cron_classify_pending_documents(self):
        pending = self.sudo().search(
            [("ai_classified", "=", False), ("attachment_id", "!=", False)],
            limit=20,
        )
        pending._run_ai_classify()
