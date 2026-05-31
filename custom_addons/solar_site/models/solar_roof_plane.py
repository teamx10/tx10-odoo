from odoo import fields, models

ORIENTATION_SELECTION = [
    ("n", "North"),
    ("ne", "Northeast"),
    ("e", "East"),
    ("se", "Southeast"),
    ("s", "South"),
    ("sw", "Southwest"),
    ("w", "West"),
    ("nw", "Northwest"),
    ("flat", "Flat"),
]

SHADING_SELECTION = [
    ("none", "None"),
    ("low", "Low (<10%)"),
    ("medium", "Medium (10–30%)"),
    ("high", "High (>30%)"),
    ("critical", "Critical (obstructed)"),
]


class SolarRoofPlane(models.Model):
    _name = "solar.roof.plane"
    _description = "Solar Roof Plane"
    _order = "sequence, id"

    solar_site_id = fields.Many2one(
        comodel_name="solar.site",
        string="Solar Site",
        required=True,
        ondelete="cascade",
    )
    sequence = fields.Integer(default=10)
    name = fields.Char(string="Plane Name", required=True, default="Roof Plane")

    total_area_m2 = fields.Float(string="Total Area (m²)", digits=(10, 2))
    usable_area_m2 = fields.Float(string="Usable Area (m²)", digits=(10, 2))
    orientation = fields.Selection(
        selection=ORIENTATION_SELECTION,
        string="Orientation",
        default="s",
    )
    pitch_degrees = fields.Float(string="Pitch (°)", digits=(5, 1))
    shading_risk = fields.Selection(
        selection=SHADING_SELECTION,
        string="Shading Risk",
        default="none",
    )
    notes = fields.Text(string="Notes")
