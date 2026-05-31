from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSolarSiteFlow(TransactionCase):
    """Acceptance flow tests for solar_site module (§21)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({
            "name": "Тестовий Клієнт",
            "city": "Буча",
            "street": "вул. Тестова, 1",
        })
        cls.lead = cls.env["crm.lead"].create({
            "name": "Тестовий лід — СЕС",
            "partner_id": cls.partner.id,
            "street": "вул. Тестова, 1",
            "city": "Буча",
        })

    def test_create_solar_site_from_lead(self):
        """Create Solar Site from CRM lead — site created, linked, stage updated."""
        self.lead.action_create_solar_site()

        self.assertTrue(self.lead.solar_site_id, "solar_site_id should be set after creation")
        site = self.lead.solar_site_id
        self.assertEqual(site.solar_status, "remote_assessment")
        self.assertEqual(site.owner_partner_id, self.partner)
        self.assertEqual(site.street, "вул. Тестова, 1")
        self.assertEqual(site.city, "Буча")
        # Lead should be linked back
        self.assertIn(self.lead, site.crm_lead_ids)

    def test_duplicate_detection(self):
        """Create Solar Site twice — second call reuses existing site."""
        self.lead.action_create_solar_site()
        site1 = self.lead.solar_site_id

        lead2 = self.env["crm.lead"].create({
            "name": "Дублікат лід",
            "partner_id": self.partner.id,
            "street": "вул. Тестова, 1",
            "city": "Буча",
        })
        lead2.action_create_solar_site()
        self.assertEqual(lead2.solar_site_id, site1, "Duplicate site should be reused")

    def test_roof_planes_sum(self):
        """Roof planes sum correctly on the site."""
        site = self.env["solar.site"].create({
            "owner_partner_id": self.partner.id,
            "solar_status": "remote_assessment",
        })
        self.env["solar.roof.plane"].create([
            {"solar_site_id": site.id, "name": "South", "total_area_m2": 80, "usable_area_m2": 55, "shading_risk": "medium"},
            {"solar_site_id": site.id, "name": "North", "total_area_m2": 40, "usable_area_m2": 20, "shading_risk": "low"},
        ])
        self.assertAlmostEqual(site.estimated_total_roof_area_m2, 120.0)
        self.assertAlmostEqual(site.estimated_total_usable_area_m2, 75.0)
        self.assertEqual(site.overall_shading_risk, "medium")

    def test_recalculate_potential(self):
        """Recalculate potential produces non-zero values with usable area."""
        site = self.env["solar.site"].create({
            "owner_partner_id": self.partner.id,
            "solar_status": "remote_assessment",
            "panel_wattage_wp": 580,
            "panel_area_m2": 2.6,
            "area_utilization_pct": 60,
            "specific_yield_kwh_kwp": 1100,
        })
        self.env["solar.roof.plane"].create({
            "solar_site_id": site.id,
            "name": "Main",
            "total_area_m2": 80,
            "usable_area_m2": 55,
            "shading_risk": "low",
        })
        site.action_recalculate_potential()
        self.assertGreater(site.estimated_panel_count, 0)
        self.assertGreater(site.estimated_dc_kw, 0)
        self.assertGreater(site.estimated_annual_generation_kwh, 0)

    def test_qualify_site_ready_for_proposal(self):
        """Qualify Site sets status, ready flag, and moves lead to Ready for Proposal."""
        self.lead.action_create_solar_site()
        site = self.lead.solar_site_id

        site.action_qualify_site()

        self.assertEqual(site.solar_status, "qualified")
        self.assertTrue(site.ready_for_preliminary_proposal)
        # Lead status should reflect
        self.assertTrue(self.lead.ready_for_preliminary_proposal)

    def test_qualify_site_creates_chatter_message(self):
        """Qualify Site writes a chatter message."""
        self.lead.action_create_solar_site()
        site = self.lead.solar_site_id
        msg_count_before = len(site.message_ids)

        site.action_qualify_site()

        self.assertGreater(len(site.message_ids), msg_count_before)

    def test_reject_site(self):
        """Reject Site sets status to rejected and clears ready flag."""
        self.lead.action_create_solar_site()
        site = self.lead.solar_site_id
        site.action_reject_site()
        self.assertEqual(site.solar_status, "rejected")
        self.assertFalse(site.ready_for_preliminary_proposal)
