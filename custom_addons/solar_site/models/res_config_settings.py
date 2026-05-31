from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    solar_default_qualification_engineer_id = fields.Many2one(
        comodel_name="res.users",
        string="Default Qualification Engineer",
        config_parameter="solar_site.default_qualification_engineer_id",
    )
    solar_default_panel_wattage = fields.Float(
        string="Default Panel Wattage (Wp)",
        default=580.0,
        config_parameter="solar_site.default_panel_wattage",
    )
    solar_default_panel_area = fields.Float(
        string="Default Panel Area (m²)",
        default=2.6,
        config_parameter="solar_site.default_panel_area",
    )
    solar_default_area_utilization = fields.Float(
        string="Default Area Utilisation (%)",
        default=60.0,
        config_parameter="solar_site.default_area_utilization",
    )
    solar_default_specific_yield = fields.Float(
        string="Default Specific Yield (kWh/kWp)",
        default=1100.0,
        config_parameter="solar_site.default_specific_yield",
    )
    solar_default_qualification_deadline = fields.Integer(
        string="Qualification Activity Deadline (days)",
        default=1,
        config_parameter="solar_site.default_qualification_deadline",
    )
    solar_default_proposal_deadline = fields.Integer(
        string="Proposal Activity Deadline (days)",
        default=1,
        config_parameter="solar_site.default_proposal_deadline",
    )
