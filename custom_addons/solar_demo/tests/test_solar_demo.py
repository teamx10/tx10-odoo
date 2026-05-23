from psycopg2 import IntegrityError

from odoo.tests import TransactionCase, loaded_demo_data, tagged
from odoo.tools import mute_logger


@tagged("solar_demo", "post_install", "-at_install")
class TestSolarDemoBranding(TransactionCase):
    def setUp(self):
        super().setUp()
        if not loaded_demo_data(self.env):
            self.skipTest("Branding assertions require demo data (run with --with-demo)")

    def test_company_name(self):
        company = self.env.ref("base.main_company")
        self.assertEqual(company.name, "iSolar Energy")

    def test_company_primary_color(self):
        company = self.env.ref("base.main_company")
        self.assertEqual(company.primary_color, "#1f6e43")

    def test_company_secondary_color(self):
        company = self.env.ref("base.main_company")
        self.assertEqual(company.secondary_color, "#f5a623")

    def test_company_logo_set(self):
        partner = self.env.ref("base.main_partner")
        self.assertTrue(partner.image_1920, "Company logo should be set")


@tagged("solar_demo", "post_install", "-at_install")
class TestSolarDemoData(TransactionCase):
    def setUp(self):
        super().setUp()
        if not loaded_demo_data(self.env):
            self.skipTest("Demo records require demo data (run with --with-demo)")

    def test_demo_partners_exist(self):
        """All three demo clients must resolve by xmlid."""
        for xmlid in (
            "solar_demo.solar_demo_partner_sonnenhaus",
            "solar_demo.solar_demo_partner_greenvalley",
            "solar_demo.solar_demo_partner_riverside",
        ):
            self.env.ref(xmlid)  # ValueError if not found = demo load failed

    def test_demo_projects_exist(self):
        """Three demo projects must cover exactly survey/installation/handover."""
        projects = [
            self.env.ref("solar_demo.solar_demo_project_residential"),
            self.env.ref("solar_demo.solar_demo_project_commercial"),
            self.env.ref("solar_demo.solar_demo_project_groundmount"),
        ]
        stages = {p.solar_stage for p in projects}
        self.assertEqual(stages, {"survey", "installation", "handover"})

    def test_demo_project_solar_fields_populated(self):
        residential = self.env.ref("solar_demo.solar_demo_project_residential")
        self.assertGreater(residential.solar_kw_capacity, 0)
        self.assertGreater(residential.solar_budget_usd, 0)

    def test_demo_documents_exist(self):
        """All six demo documents must resolve by xmlid."""
        for xmlid in (
            "solar_demo.solar_demo_doc_residential_bill",
            "solar_demo.solar_demo_doc_residential_roof",
            "solar_demo.solar_demo_doc_commercial_permit",
            "solar_demo.solar_demo_doc_commercial_sld",
            "solar_demo.solar_demo_doc_groundmount_handover",
            "solar_demo.solar_demo_doc_groundmount_commissioning",
        ):
            self.env.ref(xmlid)

    def test_demo_documents_varied_states(self):
        """Demo docs must span at least 3 distinct states."""
        xmlids = [
            "solar_demo.solar_demo_doc_residential_bill",
            "solar_demo.solar_demo_doc_residential_roof",
            "solar_demo.solar_demo_doc_commercial_permit",
            "solar_demo.solar_demo_doc_commercial_sld",
            "solar_demo.solar_demo_doc_groundmount_handover",
            "solar_demo.solar_demo_doc_groundmount_commissioning",
        ]
        states = {self.env.ref(x).state for x in xmlids}
        self.assertGreaterEqual(len(states), 3, f"Expected ≥3 distinct states, got: {states}")

    def test_demo_checklist_items_exist(self):
        """All six demo checklist items must resolve by xmlid."""
        for xmlid in (
            "solar_demo.solar_demo_check_survey_1",
            "solar_demo.solar_demo_check_survey_2",
            "solar_demo.solar_demo_check_survey_3",
            "solar_demo.solar_demo_check_install_1",
            "solar_demo.solar_demo_check_install_2",
            "solar_demo.solar_demo_check_install_3",
        ):
            self.env.ref(xmlid)


@tagged("solar_demo", "post_install", "-at_install")
class TestSolarDemoConstraints(TransactionCase):
    """Constraint tests: independent of demo data, verify required-field enforcement."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project = cls.env["project.project"].create({"name": "_constraint_test"})

    @mute_logger("odoo.sql_db")
    def test_document_requires_type(self):
        with self.assertRaises(IntegrityError):
            self.env["solar.document"].create({
                "name": "Doc Without Type",
                "project_id": self.project.id,
                # document_type_id intentionally absent
            })
            self.env.flush_all()

    @mute_logger("odoo.sql_db")
    def test_checklist_requires_task(self):
        with self.assertRaises(IntegrityError):
            self.env["solar.checklist.item"].create({
                "name": "Item Without Task",
                # task_id intentionally absent
            })
            self.env.flush_all()
