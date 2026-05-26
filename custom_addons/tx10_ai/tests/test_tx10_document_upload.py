import base64

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestTx10DocumentUpload(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project = cls.env["project.project"].create({"name": "Upload Test Project"})

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

    def test_wizard_creates_solar_document(self):
        att = self._make_attachment("inverter_datasheet.pdf", b"fronius inverter technical specification")
        wizard = self._open_wizard([att.id])
        wizard.action_classify_and_file()
        self.assertEqual(wizard.state, "done")
        docs = self.env["solar.document"].search([
            ("project_id", "=", self.project.id),
            ("name", "=", "inverter_datasheet.pdf"),
        ])
        self.assertEqual(len(docs), 1)
        self.assertTrue(docs.ai_classified)

    def test_wizard_photo_goes_to_photo_folder(self):
        att = self._make_attachment("site_photo.jpg", b"")
        wizard = self._open_wizard([att.id])
        wizard.action_classify_and_file()
        doc = self.env["solar.document"].search([
            ("project_id", "=", self.project.id),
            ("name", "=", "site_photo.jpg"),
        ], limit=1)
        self.assertTrue(doc)
        self.assertEqual(doc.folder_id.folder_code, "01_Фото")
        self.assertFalse(doc.needs_review)

    def test_wizard_unknown_gets_needs_review(self):
        att = self._make_attachment("random_notes.txt", b"completely unrelated text about cats and dogs")
        wizard = self._open_wizard([att.id])
        wizard.action_classify_and_file()
        doc = self.env["solar.document"].search([
            ("project_id", "=", self.project.id),
            ("name", "=", "random_notes.txt"),
        ], limit=1)
        self.assertTrue(doc)
        self.assertTrue(doc.needs_review)

    def test_wizard_duplicate_skipped(self):
        att = self._make_attachment("dup_file.pdf", b"content")
        # First upload
        w1 = self._open_wizard([att.id])
        w1.action_classify_and_file()
        # Second upload same attachment
        att2 = self._make_attachment("dup_file.pdf", b"content")
        w2 = self._open_wizard([att2.id])
        w2.action_classify_and_file()

        skipped = w2.result_line_ids.filtered(lambda line: line.status == "skipped")
        self.assertTrue(skipped)
        self.assertEqual(skipped[0].filename, "dup_file.pdf")

    def test_wizard_result_lines_created(self):
        att = self._make_attachment("spec.pdf", b"solar module monocrystalline jinko 400W")
        wizard = self._open_wizard([att.id])
        wizard.action_classify_and_file()
        self.assertTrue(wizard.result_line_ids)
        line = wizard.result_line_ids[0]
        self.assertEqual(line.filename, "spec.pdf")
        self.assertIn(line.status, ["done", "needs_review", "skipped", "error"])

    def test_solar_document_without_document_type_id(self):
        doc = self.env["solar.document"].create({
            "name": "no_type_doc.pdf",
            "project_id": self.project.id,
            "ai_classified": True,
        })
        self.assertFalse(doc.document_type_id)

    def test_cross_project_folder_constraint(self):
        project2 = self.env["project.project"].create({"name": "Other Project"})
        Folder = self.env["tx10.document.folder"]
        Folder._ensure_tree(project2)
        folder_p2 = Folder.get_folder_by_code(project2, "01_Фото")
        with self.assertRaises(ValidationError):
            self.env["solar.document"].create({
                "name": "wrong_project.pdf",
                "project_id": self.project.id,
                "folder_id": folder_p2.id,
            })

    def test_ensures_tree_on_classify(self):
        att = self._make_attachment("panel_spec.pdf", b"solar panel photovoltaic monocrystalline")
        wizard = self._open_wizard([att.id])
        wizard.action_classify_and_file()
        Folder = self.env["tx10.document.folder"]
        count = Folder.search_count([("project_id", "=", self.project.id)])
        self.assertEqual(count, 24)

    def test_xlsx_consumption_category(self):
        att = self._make_attachment("consumption.xlsx", b"")
        # Override attachment name to trigger extension check only, set keywords in name
        att.write({"name": "споживання_рахунок.xlsx"})
        wizard = self._open_wizard([att.id])
        wizard.action_classify_and_file()
        doc = self.env["solar.document"].search([
            ("project_id", "=", self.project.id),
            ("name", "=", "споживання_рахунок.xlsx"),
        ], limit=1)
        self.assertTrue(doc)
