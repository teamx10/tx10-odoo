# iSolar Docker Demo Environment Implementation Plan — v2

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a `solar_demo` Odoo module + Docker Compose setup so anyone can run `docker compose up` and get Odoo 19 with iSolar branding, sample clients, projects, and documents pre-loaded — zero manual steps.

**Architecture:** A thin `solar_demo` addon (no models, only XML data) depends on `solar_project` + `solar_ai`. All side-effects — branding AND sample records — live in `demo/` so the module is a no-op on non-demo production installs. Docker extends the official `odoo:19` image with a pinned `httpx` layer. Secrets (DB password, admin password, OpenRouter key) stay outside version control in `.env`; docker-compose reads them via `${VAR}` interpolation and the official image's `HOST/USER/PASSWORD` env-var protocol. `docker-compose.yml` passes `-i solar_demo` so the DB self-seeds on first boot; subsequent boots are no-ops.

**Tech Stack:** Odoo 19.0 XML data files, `odoo.tests.TransactionCase`, Docker Compose v2, `postgres:17`, Python `Pillow` for logo generation (install in venv if missing).

**Changes from v1 (IT-team review fixes):**

| # | BLOCKER/MAJOR | Fix |
|---|--------------|-----|
| BLOCKER | Secrets committed to repo | `.env.example` + `.gitignore` + `${VAR}` in compose |
| M1 | DB manager exposed | `list_db = False`, `dbfilter = isolar` in `odoo.conf` |
| M2 | `browse(1)` in tests | `env.ref('base.main_company')` |
| M3 | No rollback procedure | Explicit rollback step in Task 8 |
| M4 | `noupdate=1` untested | Update-idempotency verify step added to Task 3 |
| M5 | Commit count mismatch | Fixed: 9 commits |
| M6 | Branding in `data/` | Moved to `demo/branding.xml`; manifest `data: []` |
| M7 | No `--without-demo=all` test | Bash verify step added to Task 6 |
| M8 | No negative-case tests | `TestSolarDemoConstraints` class with `assertRaises` |
| M9 | Unbounded `search([])` | All doc/checklist tests use `env.ref(xmlid)` per record |
| M10 | `test_demo_projects_exist` too broad | Uses `env.ref` per project + stage assertion |
| M11 | No OpenRouter API key path | Added to `.env.example` + compose environment |
| M12 | No odoo healthcheck; httpx unpinned | Odoo healthcheck added; `httpx>=0.27.0,<1.0.0` |

---

## Helper: test cycle command

Used in every task. Drop and recreate the test DB, install solar_demo, run tagged tests:

```bash
PATH="/opt/homebrew/Cellar/postgresql@17/17.9/bin:$PATH" dropdb --if-exists isolar_demo_test \
  && PATH="/opt/homebrew/Cellar/postgresql@17/17.9/bin:$PATH" createdb -O odoo isolar_demo_test \
  && .venv/bin/python odoo-bin \
       --addons-path=addons,odoo/addons,custom_addons \
       -d isolar_demo_test \
       --test-tags solar_demo \
       --stop-after-init \
       -i solar_demo
```

Why drop+create every time: Odoo loads `demo:` files **only on install**, not on `-u`. Without a fresh DB, data changes in the demo XML won't appear in subsequent test runs.

## Helper: no-demo install verify command

Used in Task 6. Verifies module installs cleanly with no demo data (required-field safety):

```bash
PATH="/opt/homebrew/Cellar/postgresql@17/17.9/bin:$PATH" dropdb --if-exists isolar_nodemo_test \
  && PATH="/opt/homebrew/Cellar/postgresql@17/17.9/bin:$PATH" createdb -O odoo isolar_nodemo_test \
  && .venv/bin/python odoo-bin \
       --addons-path=addons,odoo/addons,custom_addons \
       -d isolar_nodemo_test \
       --without-demo=all \
       --stop-after-init \
       -i solar_demo 2>&1 | grep -E "(ERROR|Modules loaded|error)"
```

Expected: `Modules loaded.` with zero ERROR lines.

---

### Task 1: Scaffold solar_demo module + all test stubs (most red)

**Files to create:**
- `custom_addons/solar_demo/__init__.py`
- `custom_addons/solar_demo/__manifest__.py`
- `custom_addons/solar_demo/data/img/.gitkeep`
- `custom_addons/solar_demo/demo/branding.xml` (empty stub)
- `custom_addons/solar_demo/demo/solar_demo_data.xml` (empty stub)
- `custom_addons/solar_demo/tests/__init__.py`
- `custom_addons/solar_demo/tests/test_solar_demo.py`

**Step 1: Create directory structure**

```bash
mkdir -p custom_addons/solar_demo/data/img \
         custom_addons/solar_demo/demo \
         custom_addons/solar_demo/tests
touch custom_addons/solar_demo/data/img/.gitkeep
```

**Step 2: Create `custom_addons/solar_demo/__init__.py`** (empty)

```python
```

**Step 3: Create `custom_addons/solar_demo/__manifest__.py`**

Note: `data: []` is empty — no unconditional side-effects. All branding + demo records are in `demo:` so they never load in production installs.

```python
{
    "name": "Solar Demo Data",
    "version": "19.0.1.0.0",
    "summary": "Branding and sample data for iSolar demo environment",
    "category": "Project",
    "depends": ["solar_project", "solar_ai"],
    "data": [],
    "demo": ["demo/branding.xml", "demo/solar_demo_data.xml"],
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
```

**Step 4: Create empty stub `custom_addons/solar_demo/demo/branding.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
</odoo>
```

**Step 5: Create empty stub `custom_addons/solar_demo/demo/solar_demo_data.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
</odoo>
```

**Step 6: Create `custom_addons/solar_demo/tests/__init__.py`** (empty)

```python
```

**Step 7: Create `custom_addons/solar_demo/tests/test_solar_demo.py`**

Key design decisions vs v1:
- Branding: `env.ref('base.main_company')` instead of `browse(1)` — stable across any DB init order.
- Demo records: `env.ref(xmlid)` per record instead of `search([])` — raises `ValueError` if demo failed to load.
- Projects: `env.ref` per project + exact stage set, not a loose count filter.
- Constraints: separate class `TestSolarDemoConstraints`, independent of demo data, using `assertRaises`.

```python
from odoo.tests import TransactionCase, tagged


@tagged("solar_demo", "post_install", "-at_install")
class TestSolarDemoBranding(TransactionCase):
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

    def test_document_requires_type(self):
        with self.assertRaises(Exception):
            self.env["solar.document"].create({
                "name": "Doc Without Type",
                "project_id": self.project.id,
                # document_type_id intentionally absent
            })

    def test_checklist_requires_task(self):
        with self.assertRaises(Exception):
            self.env["solar.checklist.item"].create({
                "name": "Item Without Task",
                # task_id intentionally absent
            })
```

**Step 8: Run tests — expected result**

Run the helper command from the top of this plan.

Expected:
```
TestSolarDemoBranding.*          — FAIL (branding not loaded yet)
TestSolarDemoData.*              — FAIL (no demo records, env.ref raises ValueError)
TestSolarDemoConstraints.*       — PASS (constraints already enforced by solar_project)
```

`TestSolarDemoConstraints` passes immediately — this is correct. Constraint enforcement lives in `solar_project`; these are regression tests confirming it works. If they FAIL, stop and investigate `solar_project` before continuing.

**Step 9: Commit scaffold**

```bash
git add custom_addons/solar_demo/
git commit -m "[ADD] solar_demo: scaffold module with empty data stubs and full test suite"
```

---

### Task 2: Generate placeholder logo PNG

**Files:**
- Create: `custom_addons/solar_demo/data/img/isolar_logo.png`
- Script (run once, not committed): generate the PNG via Python

**Step 1: Check Pillow, install if missing**

```bash
.venv/bin/python -c "import PIL; print('ok')" 2>/dev/null || .venv/bin/pip install Pillow
```

**Step 2: Generate `isolar_logo.png` via Python script**

Run this script (paste into terminal or save as `/tmp/gen_logo.py` and run):

```python
from PIL import Image, ImageDraw, ImageFont
import math, os

size = 256
img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# Green background circle
draw.ellipse([4, 4, size - 4, size - 4], fill="#1f6e43")

# Sun rays (8 lines from centre)
cx, cy, r_inner, r_outer = size // 2, size // 2, 50, 90
for i in range(8):
    angle = math.radians(i * 45)
    x1 = cx + r_inner * math.cos(angle)
    y1 = cy + r_inner * math.sin(angle)
    x2 = cx + r_outer * math.cos(angle)
    y2 = cy + r_outer * math.sin(angle)
    draw.line([(x1, y1), (x2, y2)], fill="#f5a623", width=6)

# Sun core
draw.ellipse([cx - 35, cy - 35, cx + 35, cy + 35], fill="#f5a623")

# "iSolar" text
try:
    font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 32)
except OSError:
    font = ImageFont.load_default()

text = "iSolar"
bbox = draw.textbbox((0, 0), text, font=font)
tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
draw.text(((size - tw) / 2, size - th - 20), text, fill="white", font=font)

out = "custom_addons/solar_demo/data/img/isolar_logo.png"
img.save(out, "PNG")
print(f"Saved: {out}  ({os.path.getsize(out)} bytes)")
```

Expected output: `Saved: custom_addons/solar_demo/data/img/isolar_logo.png  (XXXX bytes)`

**Step 3: Verify file exists and is a valid PNG**

```bash
file custom_addons/solar_demo/data/img/isolar_logo.png
```

Expected: `PNG image data, 256 x 256, ...`

**Step 4: Remove .gitkeep now that img/ has content**

```bash
rm custom_addons/solar_demo/data/img/.gitkeep
```

**Step 5: Commit**

```bash
git add custom_addons/solar_demo/data/img/isolar_logo.png
git commit -m "[ADD] solar_demo: add placeholder iSolar logo (256×256 PNG)"
```

---

### Task 3: Write demo/branding.xml → turn branding tests green

**Files to modify:**
- `custom_addons/solar_demo/demo/branding.xml`

**Why demo/ not data/:** `data/` loads unconditionally on every install in every environment, mutating the shared `base.main_company` singleton even in CI or production. `demo/` loads only when demo data is enabled (the default for Docker compose first boot and for the test helper command). This makes `solar_demo` a true zero-impact module in non-demo installs.

**Background:** `res.company.logo` is `related='partner_id.image_1920'` (`odoo/addons/base/models/res_company.py:47`). Set the logo via `base.main_partner`. The `primary_color` / `secondary_color` fields are on `res.company`.

**Step 1: Write `custom_addons/solar_demo/demo/branding.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
  <!-- Logo: res.company.logo is related to partner.image_1920 -->
  <record id="base.main_partner" model="res.partner">
    <field name="image_1920" type="base64" file="solar_demo/data/img/isolar_logo.png"/>
  </record>

  <!-- Company branding: name + report/UI colour palette -->
  <record id="base.main_company" model="res.company">
    <field name="name">iSolar Energy</field>
    <field name="primary_color">#1f6e43</field>
    <field name="secondary_color">#f5a623</field>
  </record>
</odoo>
```

**Step 2: Run tests — branding tests should now be GREEN**

Run the helper command.

Expected:
```
TestSolarDemoBranding.test_company_name            OK
TestSolarDemoBranding.test_company_primary_color   OK
TestSolarDemoBranding.test_company_secondary_color OK
TestSolarDemoBranding.test_company_logo_set        OK
TestSolarDemoData.*   still FAIL (no demo records yet)
TestSolarDemoConstraints.*   PASS
```

**Step 3: Verify branding survives module update (idempotency)**

Demo data loads only at install, not on `-u`. This step confirms values persist after an upgrade cycle:

```bash
.venv/bin/python odoo-bin \
    --addons-path=addons,odoo/addons,custom_addons \
    -d isolar_demo_test \
    --stop-after-init \
    -u solar_demo
```

Then re-run tests (without drop+create — same DB):

```bash
.venv/bin/python odoo-bin \
    --addons-path=addons,odoo/addons,custom_addons \
    -d isolar_demo_test \
    --test-tags solar_demo \
    --stop-after-init
```

Expected: same 4 branding tests pass. Branding values survive `-u` because they were written to the DB at install and demo is not re-run.

**Step 4: Commit**

```bash
git add custom_addons/solar_demo/demo/branding.xml
git commit -m "[ADD] solar_demo: demo/branding.xml — iSolar Energy company name, logo, and colours"
```

---

### Task 4: Write demo partners + projects → turn 3 tests green

**Files to modify:**
- `custom_addons/solar_demo/demo/solar_demo_data.xml`

**Background on fields (confirmed from models):**
- `project.project.solar_stage` Selection: survey/design/procurement/installation/handover/maintenance
- `project.project.solar_roof_type` Selection: metal/tile/flat/ground/other
- `project.project.solar_grid_type` Selection: on_grid/off_grid/hybrid
- `project.project.solar_kw_capacity`, `solar_battery_kwh` Float
- `project.project.solar_budget_usd` Monetary (uses company currency)

**Step 1: Add partners + projects to `demo/solar_demo_data.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>

  <!-- ─── Clients ─────────────────────────────────────── -->
  <record id="solar_demo_partner_sonnenhaus" model="res.partner">
    <field name="name">Sonnenhaus GmbH</field>
    <field name="is_company" eval="True"/>
    <field name="city">Berlin</field>
    <field name="country_id" ref="base.de"/>
  </record>

  <record id="solar_demo_partner_greenvalley" model="res.partner">
    <field name="name">Green Valley Farm</field>
    <field name="is_company" eval="True"/>
    <field name="city">Kyiv</field>
    <field name="country_id" ref="base.ua"/>
  </record>

  <record id="solar_demo_partner_riverside" model="res.partner">
    <field name="name">Riverside Logistics</field>
    <field name="is_company" eval="True"/>
    <field name="city">Odesa</field>
    <field name="country_id" ref="base.ua"/>
  </record>

  <!-- ─── Projects ─────────────────────────────────────── -->
  <record id="solar_demo_project_residential" model="project.project">
    <field name="name">Sonnenhaus — 8 kWp Residential</field>
    <field name="partner_id" ref="solar_demo_partner_sonnenhaus"/>
    <field name="solar_stage">survey</field>
    <field name="solar_roof_type">metal</field>
    <field name="solar_grid_type">on_grid</field>
    <field name="solar_kw_capacity">8.0</field>
    <field name="solar_budget_usd">12000</field>
    <field name="solar_address">Musterstraße 12, 10115 Berlin</field>
    <field name="solar_latitude">52.520008</field>
    <field name="solar_longitude">13.404954</field>
  </record>

  <record id="solar_demo_project_commercial" model="project.project">
    <field name="name">Green Valley — 50 kWp Agri-PV</field>
    <field name="partner_id" ref="solar_demo_partner_greenvalley"/>
    <field name="solar_stage">installation</field>
    <field name="solar_roof_type">flat</field>
    <field name="solar_grid_type">hybrid</field>
    <field name="solar_kw_capacity">50.0</field>
    <field name="solar_battery_kwh">30.0</field>
    <field name="solar_budget_usd">65000</field>
    <field name="solar_address">Boryspil district, Kyiv region</field>
  </record>

  <record id="solar_demo_project_groundmount" model="project.project">
    <field name="name">Riverside — 120 kWp Ground Mount</field>
    <field name="partner_id" ref="solar_demo_partner_riverside"/>
    <field name="solar_stage">handover</field>
    <field name="solar_roof_type">ground</field>
    <field name="solar_grid_type">on_grid</field>
    <field name="solar_kw_capacity">120.0</field>
    <field name="solar_budget_usd">140000</field>
    <field name="solar_address">Suvorovsʹkyy district, Odesa</field>
  </record>

</odoo>
```

**Step 2: Run tests — 3 more should be GREEN**

Run the helper command.

Expected:
```
TestSolarDemoData.test_demo_partners_exist         OK
TestSolarDemoData.test_demo_projects_exist         OK
TestSolarDemoData.test_demo_project_solar_fields   OK
TestSolarDemoData.test_demo_documents_exist        FAIL (no docs yet)
TestSolarDemoData.test_demo_documents_varied_*     FAIL
TestSolarDemoData.test_demo_checklist_items_exist  FAIL
```

**Step 3: Commit**

```bash
git add custom_addons/solar_demo/demo/solar_demo_data.xml
git commit -m "[ADD] solar_demo: demo partners (3 clients) and projects (survey/install/handover)"
```

---

### Task 5: Write demo tasks + solar documents → turn 2 doc tests green

**Files to modify:**
- `custom_addons/solar_demo/demo/solar_demo_data.xml` (append)

**Background:**
- `solar.checklist.item.task_id` is **required** → must create `project.task` records first.
- `solar.document` required fields: `name`, `project_id`, `document_type_id`.
- `document_type_id` xmlids live in `solar_project` module: `solar_project.solar_dtype_bill_electricity`, `solar_project.solar_dtype_roof_measurement`, `solar_project.solar_dtype_permit`, etc.
- `state` selection: draft / review / approved / expired / superseded.

**Step 1: Append to `demo/solar_demo_data.xml`** (inside the `<odoo>` tag, before closing `</odoo>`)

```xml
  <!-- ─── Tasks (required for checklist items) ─────────── -->
  <record id="solar_demo_task_residential_survey" model="project.task">
    <field name="name">Site Survey</field>
    <field name="project_id" ref="solar_demo_project_residential"/>
  </record>

  <record id="solar_demo_task_commercial_install" model="project.task">
    <field name="name">Panel Installation</field>
    <field name="project_id" ref="solar_demo_project_commercial"/>
  </record>

  <record id="solar_demo_task_groundmount_handover" model="project.task">
    <field name="name">Client Handover</field>
    <field name="project_id" ref="solar_demo_project_groundmount"/>
  </record>

  <!-- ─── Solar Documents ───────────────────────────────── -->
  <!-- Project A: Residential survey — 2 docs (approved + review) -->
  <record id="solar_demo_doc_residential_bill" model="solar.document">
    <field name="name">Electricity Bill Jan 2026</field>
    <field name="project_id" ref="solar_demo_project_residential"/>
    <field name="document_type_id" ref="solar_project.solar_dtype_bill_electricity"/>
    <field name="state">approved</field>
    <field name="valid_from" eval="(DateTime.today() - relativedelta(months=3)).strftime('%Y-%m-%d')"/>
  </record>

  <record id="solar_demo_doc_residential_roof" model="solar.document">
    <field name="name">Roof Measurement Report</field>
    <field name="project_id" ref="solar_demo_project_residential"/>
    <field name="document_type_id" ref="solar_project.solar_dtype_roof_measurement"/>
    <field name="state">review</field>
  </record>

  <!-- Project B: Commercial install — 2 docs (approved + draft) -->
  <record id="solar_demo_doc_commercial_permit" model="solar.document">
    <field name="name">Grid Connection Permit</field>
    <field name="project_id" ref="solar_demo_project_commercial"/>
    <field name="document_type_id" ref="solar_project.solar_dtype_permit"/>
    <field name="state">approved</field>
  </record>

  <record id="solar_demo_doc_commercial_sld" model="solar.document">
    <field name="name">Single-Line Electrical Diagram v2</field>
    <field name="project_id" ref="solar_demo_project_commercial"/>
    <field name="document_type_id" ref="solar_project.solar_dtype_single_line_diagram"/>
    <field name="state">draft</field>
  </record>

  <!-- Project C: Ground mount handover — 2 docs (approved) -->
  <record id="solar_demo_doc_groundmount_handover" model="solar.document">
    <field name="name">Handover Act signed</field>
    <field name="project_id" ref="solar_demo_project_groundmount"/>
    <field name="document_type_id" ref="solar_project.solar_dtype_handover_act"/>
    <field name="state">approved</field>
    <field name="valid_from" eval="(DateTime.today() - relativedelta(days=10)).strftime('%Y-%m-%d')"/>
  </record>

  <record id="solar_demo_doc_groundmount_commissioning" model="solar.document">
    <field name="name">Commissioning Test Report</field>
    <field name="project_id" ref="solar_demo_project_groundmount"/>
    <field name="document_type_id" ref="solar_project.solar_dtype_commissioning_report"/>
    <field name="state">approved</field>
  </record>
```

**Step 2: Run tests — doc tests GREEN**

Run the helper command.

Expected:
```
TestSolarDemoData.test_demo_documents_exist         OK
TestSolarDemoData.test_demo_documents_varied_states OK  (states: approved, review, draft)
TestSolarDemoData.test_demo_checklist_items_exist   FAIL (no checklist items yet)
```

**Step 3: Commit**

```bash
git add custom_addons/solar_demo/demo/solar_demo_data.xml
git commit -m "[ADD] solar_demo: demo tasks (3) and solar documents (6, varied types/states)"
```

---

### Task 6: Write demo checklist items → all tests green + safety checks

**Files to modify:**
- `custom_addons/solar_demo/demo/solar_demo_data.xml` (append)

**Step 1: Append checklist items inside `<odoo>` before `</odoo>`**

```xml
  <!-- ─── Checklist Items ───────────────────────────────── -->
  <!-- Residential: Site Survey task -->
  <record id="solar_demo_check_survey_1" model="solar.checklist.item">
    <field name="name">Roof dimensions measured</field>
    <field name="task_id" ref="solar_demo_task_residential_survey"/>
    <field name="sequence">10</field>
    <field name="is_done" eval="True"/>
  </record>

  <record id="solar_demo_check_survey_2" model="solar.checklist.item">
    <field name="name">Shading analysis completed</field>
    <field name="task_id" ref="solar_demo_task_residential_survey"/>
    <field name="sequence">20</field>
    <field name="is_done" eval="False"/>
  </record>

  <record id="solar_demo_check_survey_3" model="solar.checklist.item">
    <field name="name">Electricity meter photo taken</field>
    <field name="task_id" ref="solar_demo_task_residential_survey"/>
    <field name="sequence">30</field>
    <field name="is_done" eval="True"/>
  </record>

  <!-- Commercial: Panel Installation task -->
  <record id="solar_demo_check_install_1" model="solar.checklist.item">
    <field name="name">Mounting structure installed</field>
    <field name="task_id" ref="solar_demo_task_commercial_install"/>
    <field name="sequence">10</field>
    <field name="is_done" eval="True"/>
  </record>

  <record id="solar_demo_check_install_2" model="solar.checklist.item">
    <field name="name">Panels wired and tested</field>
    <field name="task_id" ref="solar_demo_task_commercial_install"/>
    <field name="sequence">20</field>
    <field name="is_done" eval="True"/>
  </record>

  <record id="solar_demo_check_install_3" model="solar.checklist.item">
    <field name="name">Inverter commissioning complete</field>
    <field name="task_id" ref="solar_demo_task_commercial_install"/>
    <field name="sequence">30</field>
    <field name="is_done" eval="False"/>
  </record>
```

**Step 2: Run tests — ALL should be GREEN**

Run the helper command.

Expected: `Ran 12 tests ... OK` — all pass, no failures.

**Step 3: Verify no-demo install (required-field safety)**

Run the no-demo helper command from the top of this plan.

Expected output contains `Modules loaded.` with no `ERROR` lines. This confirms `solar_demo` installs cleanly without demo data — no required-field crash on `solar.checklist.item.task_id`.

**Step 4: Commit**

```bash
git add custom_addons/solar_demo/demo/solar_demo_data.xml
git commit -m "[ADD] solar_demo: demo checklist items (6 items across 2 tasks, mixed done/pending)"
```

---

### Task 7: Docker artifacts — Dockerfile + odoo.conf + secrets setup

**Files to create:**
- `docker/Dockerfile`
- `docker/odoo.conf`
- `.env.example`
- Update `.gitignore` to exclude `.env`

**Background — why secrets stay out of committed files:**
- `admin_passwd` gates the DB manager (create/drop/backup/restore); committing it in plain text makes it a permanent git history secret.
- The official `odoo:19` image entrypoint reads `HOST`, `USER`, `PASSWORD` env vars to configure the DB connection — no password needed in `odoo.conf`.
- `admin_passwd` is passed via `--admin-passwd ${ADMIN_PASSWD}` CLI arg in docker-compose, reading from `.env`.

**Step 1: Create `docker/` directory**

```bash
mkdir -p docker
```

**Step 2: Create `docker/Dockerfile`**

`httpx` is pinned with an upper bound `<1.0.0` to prevent silent breaking changes from a future major release being pulled on `docker compose build`.

```dockerfile
FROM odoo:19
USER root
RUN pip3 install --no-cache-dir --break-system-packages "httpx>=0.27.0,<1.0.0"
USER odoo
```

**Step 3: Create `docker/odoo.conf`**

No passwords here — DB password comes from the official image's `PASSWORD` env var protocol; admin password comes from `--admin-passwd` CLI arg.

```ini
[options]
addons_path = /mnt/extra-addons
db_host = db
db_port = 5432
db_user = odoo
list_db = False
dbfilter = isolar
```

`list_db = False` — hides the database manager at `/web/database/manager`, preventing unauthorized DB operations even with the default demo admin password. `dbfilter = isolar` — Odoo only recognises the `isolar` database.

**Step 4: Create `.env.example`**

```bash
# iSolar Demo — environment variables
# Copy to .env (gitignored) and adjust before docker compose up
# These values are safe defaults for local demo only — change for any shared/production use.

DB_PASSWORD=odoo
ADMIN_PASSWD=admin

# OpenRouter API key — leave empty to run iSolar without AI features
# Get a free key at https://openrouter.ai
OPENROUTER_API_KEY=
```

**Step 5: Add `.env` to `.gitignore`**

```bash
echo ".env" >> .gitignore
```

Verify it was added:

```bash
grep "^\.env$" .gitignore
```

Expected: `.env`

**Step 6: User copies `.env.example` to `.env`**

```bash
cp .env.example .env
```

**Step 7: Verify Dockerfile builds**

```bash
docker build --no-cache -t isolar-odoo-test ./docker
```

Expected: `Successfully built ...` with no errors. The `pip install httpx` line should complete cleanly.

**Step 8: Commit**

```bash
git add docker/ .env.example .gitignore
git commit -m "[ADD] solar_demo: Docker Dockerfile (httpx pinned), odoo.conf (no secrets), .env.example"
```

---

### Task 8: docker-compose.yml + smoke test

**Files to create:**
- `docker-compose.yml` (repo root)

**Step 1: Create `docker-compose.yml`**

Key differences from v1:
- Secrets via `${DB_PASSWORD}` / `${ADMIN_PASSWD}` from `.env` (never hardcoded).
- Official image's `HOST/USER/PASSWORD` env vars handle DB auth; `--admin-passwd` handles admin auth.
- `OPENROUTER_API_KEY` forwarded to container (empty = AI inactive, no crash).
- Odoo service has a healthcheck (curl `/web/health`).
- `list_db = False` + `dbfilter` already in `odoo.conf` from Task 7.

```yaml
services:
  db:
    image: postgres:17
    environment:
      POSTGRES_DB: postgres
      POSTGRES_USER: odoo
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - odoo-db:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD", "pg_isready", "-U", "odoo"]
      interval: 5s
      timeout: 5s
      retries: 10

  odoo:
    build: ./docker
    depends_on:
      db:
        condition: service_healthy
    ports:
      - "8069:8069"
    environment:
      # Official odoo:19 entrypoint uses HOST/USER/PASSWORD for DB connection
      HOST: db
      USER: odoo
      PASSWORD: ${DB_PASSWORD}
      # OpenRouter key — empty = AI features inactive, no crash
      OPENROUTER_API_KEY: ${OPENROUTER_API_KEY:-}
    volumes:
      - ./custom_addons:/mnt/extra-addons
      - ./docker/odoo.conf:/etc/odoo/odoo.conf
      - odoo-web:/var/lib/odoo
    command: odoo -d isolar -i solar_demo --admin-passwd ${ADMIN_PASSWD}
    healthcheck:
      test: ["CMD", "curl", "-sf", "http://localhost:8069/web/health"]
      interval: 10s
      timeout: 5s
      retries: 20
      start_period: 90s

volumes:
  odoo-db:
  odoo-web:
```

**Self-seeding logic:** On first `docker compose up`, Odoo creates DB `isolar`, installs `solar_demo` (which pulls `solar_project` + `solar_ai` via depends chain), loads `demo/branding.xml` and `demo/solar_demo_data.xml` (demo is enabled by default on CLI DB init). On subsequent starts the DB exists; `-i` for an already-installed module is a no-op, server just starts. No custom entrypoint needed.

**Step 2: Start the stack**

```bash
docker compose up -d --build
```

**Step 3: Watch logs until ready**

```bash
docker compose logs -f odoo
```

Wait for: `HTTP service (werkzeug) running on 0.0.0.0:8069` or `Modules loaded.`

Expected install sequence:
```
odoo-1  | Loading module solar_project
odoo-1  | Loading module solar_ai
odoo-1  | Loading module solar_demo
```

If you see `ImportError: httpx` → Dockerfile step was missed; rebuild.

**Step 4: Wait for odoo healthcheck to turn healthy**

```bash
docker compose ps
```

Expected: `odoo` status shows `healthy` (may take 90s on first boot due to module install).

**Step 5: Health check**

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:8069/web/health
```

Expected: `200`

**Step 6: UI smoke test (manual — ~3 minutes)**

Open `http://localhost:8069`. Login: `admin` / `admin` (from `.env`), DB: `isolar`.

Checklist:
- [ ] Top-left shows **iSolar Energy** with green/amber branded logo
- [ ] **Solar Projects** menu visible → 3 projects in list
- [ ] Open "Sonnenhaus — 8 kWp Residential" → Solar tab shows kWp=8, stage=Survey
- [ ] **Solar Documents** → 6 documents, mixed states (Approved / In Review / Draft)
- [ ] Open commercial project → Tasks → "Panel Installation" → Checklist shows 3 items
- [ ] AI menu items visible but inactive (no API key configured — expected)

**Step 7: Apps menu verification**

In Odoo Apps → Search "solar" → confirm `solar_project`, `solar_ai`, `solar_demo` all show **Installed**.

**Step 8: Rollback procedure (if init fails)**

If `solar_demo` install fails mid-init (e.g. missing xmlid), the DB is left in a broken state. Full reset:

```bash
docker compose down -v          # removes named volumes — wipes the DB
docker compose up -d --build    # fresh start, re-seeds from scratch
```

After fixing the underlying issue, `docker compose up -d --build` gives a clean slate.

**Step 9: Verify clean re-run**

```bash
docker compose down -v
docker compose up -d
```

Watch logs — second boot must also complete without errors (confirms idempotency of the setup).

**Step 10: Commit**

```bash
git add docker-compose.yml
git commit -m "[ADD] solar_demo: docker-compose.yml — self-seeding iSolar demo stack (env-var secrets, healthchecks)"
```

---

### Task 9: Docs + post-task cleanup

**Files to create/modify:**
- Create: `docker/README.md`
- Create: `docs/plans/2026-05-23-isolar-docker-demo-v2-IMPLEMENTED.md`

**Step 1: Create `docker/README.md`**

```markdown
# iSolar Demo Stack

One-command demo environment for iSolar Odoo modules.

## Quick start

```bash
cp .env.example .env          # copy demo secrets (safe defaults)
docker compose up -d --build  # first boot: ~3-5 min (installs + seeds)
```

Open: http://localhost:8069 · Login: admin / admin · DB: isolar

## What's included

- **iSolar Energy** company branding (logo, green/amber palette)
- 3 sample projects (Survey / Installation / Handover stages)
- 6 solar documents (varied types and approval states)
- Checklist items on tasks (mixed done/pending)
- OpenRouter config stubs (no real API key — AI features inactive)

## Enable AI features

Set `OPENROUTER_API_KEY` in `.env`, then configure the key in Odoo:
Settings → Technical → System Parameters → `solar_ai.openrouter_api_key`.

## Stop / reset

```bash
docker compose down          # stop, keep data
docker compose down -v       # stop + delete all data (full re-seed on next up)
```

## Logs

```bash
docker compose logs -f odoo
```

## Security note

Credentials in `.env` (`admin/odoo`) are demo-only defaults.
Never expose port 8069 publicly with these values.
```

**Step 2: Create IMPLEMENTED doc**

Create `docs/plans/2026-05-23-isolar-docker-demo-v2-IMPLEMENTED.md` after all tasks complete, listing: files added, key patterns (httpx pinned layer, branding via demo/ not data/, env-var secret protocol, no-demo install verified), any deviations from plan, commit hashes.

**Step 3: Commit docs**

```bash
git add docker/README.md docs/plans/2026-05-23-isolar-docker-demo-v2-IMPLEMENTED.md
git commit -m "[ADD] solar_demo: docker README and v2 implementation log"
```

---

## Summary of files created / changed vs v1

```
custom_addons/solar_demo/
├── __init__.py                      (unchanged)
├── __manifest__.py                  (CHANGED: data=[], demo=[branding.xml, solar_demo_data.xml])
├── data/
│   └── img/
│       └── isolar_logo.png          (unchanged)
├── demo/
│   ├── branding.xml                 (NEW — was data/branding.xml in v1)
│   └── solar_demo_data.xml          (unchanged content, fixed via env.ref tests)
└── tests/
    ├── __init__.py                  (unchanged)
    └── test_solar_demo.py           (CHANGED: env.ref, xmlid-based asserts, constraints class)

docker/
├── Dockerfile                       (CHANGED: httpx pinned >=0.27.0,<1.0.0)
├── odoo.conf                        (CHANGED: no secrets, +list_db=False, +dbfilter)
└── README.md                        (NEW)

docker-compose.yml                   (CHANGED: env vars, healthcheck, OPENROUTER_API_KEY)
.env.example                         (NEW)
.gitignore                           (CHANGED: +.env)
```

## Commit sequence (9 commits)

1. `[ADD] solar_demo: scaffold module with empty data stubs and full test suite`
2. `[ADD] solar_demo: add placeholder iSolar logo (256×256 PNG)`
3. `[ADD] solar_demo: demo/branding.xml — iSolar Energy company name, logo, and colours`
4. `[ADD] solar_demo: demo partners (3 clients) and projects (survey/install/handover)`
5. `[ADD] solar_demo: demo tasks (3) and solar documents (6, varied types/states)`
6. `[ADD] solar_demo: demo checklist items (6 items across 2 tasks, mixed done/pending)`
7. `[ADD] solar_demo: Docker Dockerfile (httpx pinned), odoo.conf (no secrets), .env.example`
8. `[ADD] solar_demo: docker-compose.yml — self-seeding iSolar demo stack (env-var secrets, healthchecks)`
9. `[ADD] solar_demo: docker README and v2 implementation log`
