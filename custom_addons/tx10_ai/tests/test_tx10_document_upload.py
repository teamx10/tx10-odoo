import base64
from unittest.mock import patch

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestTx10DocumentUpload(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project = cls.env["project.project"].create({"name": "Upload Test Project"})
        cls.unknown_type = cls.env["solar.document.type"].search(
            [("code", "=", "unknown")], limit=1,
        )
        cls.bill_type = cls.env["solar.document.type"].search(
            [("code", "=", "bill_electricity")], limit=1,
        )

    def _make_attachment(self, name, content=b"test content"):
        return self.env["ir.attachment"].create({
            "name": name,
            "datas": base64.b64encode(content),
            "res_model": "project.project",
            "res_id": self.project.id,
        })

    def _open_wizard(self, attachment_ids=None):
        return self.env["tx10.document.upload.wizard"].create({
            "project_id": self.project.id,
            "attachment_ids": [(6, 0, attachment_ids or [])],
        })

    # --- Wizard upload ---

    def test_wizard_creates_pending_solar_document(self):
        att = self._make_attachment("invoice.pdf", b"electricity bill content")
        wizard = self._open_wizard([att.id])
        wizard.action_upload()
        doc = self.env["solar.document"].search([
            ("project_id", "=", self.project.id),
            ("name", "=", "invoice.pdf"),
        ], limit=1)
        self.assertTrue(doc)
        self.assertFalse(doc.ai_classified, "Document should be pending (not yet classified)")
        self.assertFalse(doc.document_type_id, "Pending doc must not require a type")

    def test_wizard_dedupe_skips_duplicate(self):
        att = self._make_attachment("dup.pdf", b"some content")
        wizard = self._open_wizard([att.id])
        wizard.action_upload()
        wizard2 = self._open_wizard([att.id])
        wizard2.action_upload()
        count = self.env["solar.document"].search_count([
            ("project_id", "=", self.project.id),
            ("name", "=", "dup.pdf"),
        ])
        self.assertEqual(count, 1, "Duplicate upload should be skipped")

    def test_wizard_returns_document_list_action(self):
        att = self._make_attachment("plan.pdf", b"site plan")
        wizard = self._open_wizard([att.id])
        action = wizard.action_upload()
        self.assertEqual(action["res_model"], "solar.document")
        self.assertEqual(action["type"], "ir.actions.act_window")

    # --- Cron classification ---

    def _create_pending_doc(self, filename, content=b"text content"):
        att = self._make_attachment(filename, content)
        return self.env["solar.document"].create({
            "name": filename,
            "project_id": self.project.id,
            "attachment_id": att.id,
            "ai_classified": False,
        })

    def test_cron_classifies_with_high_confidence(self):
        doc = self._create_pending_doc("electricity_bill.xlsx")
        good_result = {
            "document_type_code": "bill_electricity",
            "confidence": 0.92,
            "reasons": ["invoice", "kwh"],
        }
        with patch.object(
            type(self.env["tx10.ai.service"]), "classify_document_text",
            return_value=good_result,
        ):
            self.env["solar.document"]._cron_classify_pending_documents()

        doc.invalidate_recordset()
        self.assertTrue(doc.ai_classified)
        if self.bill_type:
            self.assertEqual(doc.document_type_id, self.bill_type)
        self.assertFalse(doc.needs_review)

    def test_cron_low_confidence_sets_needs_review(self):
        doc = self._create_pending_doc("mystery.pdf")
        low_result = {
            "document_type_code": "unknown",
            "confidence": 0.40,
            "reasons": [],
        }
        with patch.object(
            type(self.env["tx10.ai.service"]), "classify_document_text",
            return_value=low_result,
        ):
            self.env["solar.document"]._cron_classify_pending_documents()

        doc.invalidate_recordset()
        self.assertTrue(doc.ai_classified)
        self.assertTrue(doc.needs_review)
        if self.unknown_type:
            self.assertEqual(doc.document_type_id, self.unknown_type)

    def test_cron_llm_error_sets_needs_review(self):
        doc = self._create_pending_doc("error_case.pdf")
        error_result = {
            "document_type_code": "unknown",
            "confidence": 0.0,
            "reasons": ["no_api_key"],
        }
        with patch.object(
            type(self.env["tx10.ai.service"]), "classify_document_text",
            return_value=error_result,
        ):
            self.env["solar.document"]._cron_classify_pending_documents()

        doc.invalidate_recordset()
        self.assertTrue(doc.ai_classified)
        self.assertTrue(doc.needs_review)

    def test_cron_idempotent_skips_already_classified(self):
        self._create_pending_doc("already.pdf")
        good_result = {
            "document_type_code": "bill_electricity",
            "confidence": 0.91,
            "reasons": ["invoice"],
        }
        call_count = [0]

        def counting_classify(*args, **kwargs):
            call_count[0] += 1
            return good_result

        with patch.object(
            type(self.env["tx10.ai.service"]), "classify_document_text",
            side_effect=counting_classify,
        ):
            self.env["solar.document"]._cron_classify_pending_documents()
            self.env["solar.document"]._cron_classify_pending_documents()

        self.assertEqual(call_count[0], 1, "Second cron run must skip already-classified doc")

    def test_cron_does_not_fail_entire_batch_on_one_error(self):
        doc1 = self._create_pending_doc("ok_doc.pdf")
        doc2 = self._create_pending_doc("bad_doc.pdf")
        good_result = {"document_type_code": "bill_electricity", "confidence": 0.88, "reasons": []}

        def flaky_classify(text, filename="", types=None):
            if "bad" in (filename or ""):
                raise RuntimeError  # noqa: TRY301
            return good_result

        with patch.object(
            type(self.env["tx10.ai.service"]), "classify_document_text",
            side_effect=flaky_classify,
        ):
            self.env["solar.document"]._cron_classify_pending_documents()

        doc1.invalidate_recordset()
        doc2.invalidate_recordset()
        self.assertTrue(doc1.ai_classified, "Good doc should be classified despite peer failure")
        self.assertTrue(doc2.ai_classified, "Bad doc should be marked classified (needs_review)")
        self.assertTrue(doc2.needs_review)

    # --- Regression: pending doc without type is valid ---

    def test_pending_document_no_type_is_valid(self):
        att = self._make_attachment("pending.pdf", b"content")
        doc = self.env["solar.document"].create({
            "name": "pending.pdf",
            "project_id": self.project.id,
            "attachment_id": att.id,
            "ai_classified": False,
        })
        self.assertFalse(doc.document_type_id, "Pending doc must have no type (required=False)")
        self.assertEqual(doc.state, "draft")
