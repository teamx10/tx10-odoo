# iSolar Docker Demo Environment Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a `solar_demo` Odoo module + Docker Compose setup so anyone can run `docker compose up` and get Odoo 19 with iSolar branding, sample clients, projects, and documents pre-loaded — zero manual steps.

**Architecture:** A thin `solar_demo` addon (no models, only XML data) depends on `solar_project` + `solar_ai`. Branding (company name, logo, colors) in `data/` (loads always); sample business records in `demo/` (loads on CLI DB init by default). Docker extends the official `odoo:19` image with a single `pip install httpx` layer (required by `solar_ai`). `docker-compose.yml` passes `-i solar_demo` so the DB self-seeds on first boot; subsequent boots are no-ops.

**Tech Stack:** Odoo 19.0 XML data files, `odoo.tests.TransactionCase`, Docker Compose v2, `postgres:17`, Python `Pillow` for logo generation (install in venv if missing).

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

---

### Task 1: Scaffold solar_demo module + all test stubs (all red)

**Files to create:**
- `custom_addons/solar_demo/__init__.py`
- `custom_addons/solar_demo/__manifest__.py`
- `custom_addons/solar_demo/data/branding.xml` (empty stub)
- `custom_addons/solar_demo/data/img/.gitkeep`
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

```python
{
    "name": "Solar Demo Data",
    "version": "19.0.1.0.0",
    "summary": "Branding and sample data for iSolar demo environment",
    "category": "Project",
    "depends": ["solar_project", "solar_ai"],
    "data": ["data/branding.xml"],
    "demo": ["demo/solar_demo_data.xml"],
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
```

**Step 4: Create empty stub `custom_addons/solar_demo/data/branding.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo noupdate="1">
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

**Step 7: Create `custom_addons/solar_demo/tests/test_solar_demo.py` — ALL tests, all will fail**

```python
from odoo.tests import TransactionCase, tagged


@tagged("solar_demo", "post_install", "-at_install")
class TestSolarDemoBranding(TransactionCase):
    def test_company_name(self):
        company = self.env["res.company"].sudo().browse(1)
        self.assertEqual(company.name, "iSolar Energy")

    def test_company_primary_color(self):
        company = self.env["res.company"].sudo().browse(1)
        self.assertEqual(company.primary_color, "#1f6e43")

    def test_company_secondary_color(self):
        company = self.env["res.company"].sudo().browse(1)
        self.assertEqual(company.secondary_color, "#f5a623")

    def test_company_logo_set(self):
        partner = self.env.ref("base.main_partner")
        self.assertTrue(partner.image_1920, "Company logo should be set")


@tagged("solar_demo", "post_install", "-at_install")
class TestSolarDemoData(TransactionCase):
    def test_demo_partners_exist(self):
        partners = self.env["res.partner"].search(
            [("name", "in", ["Sonnenhaus GmbH", "Green Valley Farm", "Riverside Logistics"])],
        )
        self.assertEqual(len(partners), 3)

    def test_demo_projects_exist(self):
        projects = self.env["project.project"].search(
            [("solar_stage", "in", ["survey", "installation", "handover"])],
        )
        self.assertGreaterEqual(len(projects), 3)

    def test_demo_project_solar_fields_populated(self):
        project = self.env["project.project"].search(
            [("solar_kw_capacity", ">", 0)], limit=1,
        )
        self.assertTrue(project, "At least one project should have kWp set")
        self.assertGreater(project.solar_budget_usd, 0)

    def test_demo_documents_exist(self):
        docs = self.env["solar.document"].search([])
        self.assertGreaterEqual(len(docs), 5)

    def test_demo_documents_varied_states(self):
        states = set(self.env["solar.document"].search([]).mapped("state"))
        self.assertGreater(len(states), 1, "Demo docs should cover multiple states")

    def test_demo_checklist_items_exist(self):
        items = self.env["solar.checklist.item"].search([])
        self.assertGreaterEqual(len(items), 3)
```

**Step 8: Run tests — verify ALL fail (red)**

Run the helper command from the top of this plan.

Expected: `FAIL` for all tests in `TestSolarDemoBranding` and `TestSolarDemoData` because both XML files are empty stubs.

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
import os

size = 256
img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# Green background circle
draw.ellipse([4, 4, size - 4, size - 4], fill="#1f6e43")

# Sun rays (8 lines from centre)
cx, cy, r_inner, r_outer = size // 2, size // 2, 50, 90
import math
for i in range(8):
    angle = math.radians(i * 45)
    x1 = cx + r_inner * math.cos(angle)
    y1 = cy + r_inner * math.sin(angle)
    x2 = cx + r_outer * math.cos(angle)
    y2 = cy + r_outer * math.sin(angle)
    draw.line([(x1, y1), (x2, y2)], fill="#f5a623", width=6)

# Sun core
draw.ellipse([cx - 35, cy - 35, cx + 35, cy + 35], fill="#f5a623")

# "iSolar" text — try a system font, fall back to default
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

### Task 3: Write branding.xml → turn branding tests green

**Files to modify:**
- `custom_addons/solar_demo/data/branding.xml`

**Background:** `res.company.logo` is `related='partner_id.image_1920'` (from `odoo/addons/base/models/res_company.py:47`). Set the logo via `base.main_partner`. The `primary_color` / `secondary_color` fields are on `res.company` (lines 75-76); writing them auto-clears the asset cache to apply the new palette to reports and layout.

**Step 1: Write `custom_addons/solar_demo/data/branding.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo noupdate="1">
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

Run the helper command from the top of this plan.

Expected:
```
TestSolarDemoBranding.test_company_name          OK
TestSolarDemoBranding.test_company_primary_color OK
TestSolarDemoBranding.test_company_secondary_color OK
TestSolarDemoBranding.test_company_logo_set      OK
TestSolarDemoData.*  all still FAIL (no demo records yet)
```

**Step 3: Commit**

```bash
git add custom_addons/solar_demo/data/branding.xml
git commit -m "[ADD] solar_demo: branding.xml — iSolar Energy company name, logo, and colours"
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

**Step 2: Run tests — 3 more tests should be GREEN**

Run the helper command from the top of this plan.

Expected:
```
TestSolarDemoData.test_demo_partners_exist        OK
TestSolarDemoData.test_demo_projects_exist        OK
TestSolarDemoData.test_demo_project_solar_fields  OK
TestSolarDemoData.test_demo_documents_exist       FAIL (no docs yet)
TestSolarDemoData.test_demo_documents_varied_*    FAIL
TestSolarDemoData.test_demo_checklist_items_exist FAIL
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
  <!-- Project A: Residential survey — 2 docs (draft + review) -->
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

Run the helper command from the top of this plan.

Expected:
```
TestSolarDemoData.test_demo_documents_exist        OK
TestSolarDemoData.test_demo_documents_varied_states OK
TestSolarDemoData.test_demo_checklist_items_exist  FAIL (no checklists yet)
```

**Step 3: Commit**

```bash
git add custom_addons/solar_demo/demo/solar_demo_data.xml
git commit -m "[ADD] solar_demo: demo tasks (3) and solar documents (6, varied types/states)"
```

---

### Task 6: Write demo checklist items → all tests green

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

Run the helper command from the top of this plan.

Expected: `Ran 10 tests ... OK` — all pass, no failures.

**Step 3: Commit**

```bash
git add custom_addons/solar_demo/demo/solar_demo_data.xml
git commit -m "[ADD] solar_demo: demo checklist items (6 items across 2 tasks, mixed done/pending)"
```

---

### Task 7: Docker artifacts — Dockerfile + odoo.conf

**Files to create:**
- `docker/Dockerfile`
- `docker/odoo.conf`

**Background:** Official `odoo:19` Community image does **not** include `httpx`. `solar_ai` declares `external_dependencies: {python: [httpx]}` — without it Odoo refuses to install the module (raises `ImportError` at registry load). The fix is a one-line `pip install httpx` layer on top of the official image. The `--break-system-packages` flag is required on Debian 12+ (PEP 668 protection in the base image).

**Step 1: Create `docker/` directory**

```bash
mkdir -p docker
```

**Step 2: Create `docker/Dockerfile`**

```dockerfile
FROM odoo:19
USER root
RUN pip3 install --no-cache-dir --break-system-packages "httpx>=0.27.0"
USER odoo
```

**Step 3: Create `docker/odoo.conf`**

```ini
[options]
addons_path = /mnt/extra-addons
db_host = db
db_port = 5432
db_user = odoo
db_password = odoo
admin_passwd = admin
```

Note: Odoo discovers its bundled base addons automatically regardless of `addons_path`; only the extra-addons volume needs to be listed here.

**Step 4: Verify Dockerfile syntax**

```bash
docker build --no-cache -t isolar-odoo-test ./docker
```

Expected: `Successfully built ...` with no errors. The `pip install httpx` line should complete cleanly.

**Step 5: Commit**

```bash
git add docker/
git commit -m "[ADD] solar_demo: Docker Dockerfile (FROM odoo:19 + httpx) and odoo.conf"
```

---

### Task 8: docker-compose.yml + smoke test

**Files to create:**
- `docker-compose.yml` (repo root)

**Step 1: Create `docker-compose.yml`**

```yaml
services:
  db:
    image: postgres:17
    environment:
      POSTGRES_DB: postgres
      POSTGRES_USER: odoo
      POSTGRES_PASSWORD: odoo
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
    volumes:
      - ./custom_addons:/mnt/extra-addons
      - ./docker/odoo.conf:/etc/odoo/odoo.conf
      - odoo-web:/var/lib/odoo
    command: ["odoo", "-d", "isolar", "-i", "solar_demo"]

volumes:
  odoo-db:
  odoo-web:
```

**Self-seeding logic:** On first `docker compose up`, Odoo creates DB `isolar`, installs `solar_demo` (which pulls `solar_project` + `solar_ai` via depends chain), loads `data/branding.xml` (always) and `demo/solar_demo_data.xml` (CLI init enables demo by default). On subsequent starts the DB exists, `-i` for an installed module is a no-op, server just starts. No custom entrypoint needed.

**Step 2: Start the stack**

```bash
docker compose up -d --build
```

**Step 3: Watch logs until ready**

```bash
docker compose logs -f odoo
```

Wait for: `HTTP service (werkzeug) running on 0.0.0.0:8069` or `Modules loaded.`
If you see `ImportError: httpx` → Dockerfile step was missed; rebuild.

Expected install sequence in logs:
```
odoo-1  | Loading module solar_project
odoo-1  | Loading module solar_ai
odoo-1  | Loading module solar_demo
```

**Step 4: Health check**

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:8069/web/health
```

Expected: `200`

**Step 5: UI smoke test (manual — ~3 minutes)**

Open `http://localhost:8069`. Login: `admin` / `admin`, DB: `isolar`.

Checklist:
- [ ] Top-left shows **iSolar Energy** with green/amber branded logo
- [ ] **Solar Projects** menu visible → 3 projects in list
- [ ] Open "Sonnenhaus — 8 kWp Residential" → Solar tab shows kWp=8, stage=Survey, ROI computed
- [ ] **Solar Documents** → 6 documents, mixed states (Approved / In Review / Draft)
- [ ] Open commercial project → Tasks → "Panel Installation" → Checklist section shows 3 items

**Step 6: Apps menu verification**

In Odoo Apps → Search "solar" → confirm `solar_project`, `solar_ai`, `solar_demo` all show **Installed**.

**Step 7: Teardown (confirms clean re-run)**

```bash
docker compose down -v
docker compose up -d
```

Verify second `up` re-seeds identically (no errors on second boot).

**Step 8: Commit**

```bash
git add docker-compose.yml
git commit -m "[ADD] solar_demo: docker-compose.yml — self-seeding iSolar demo stack (odoo:19 + postgres:17)"
```

---

### Task 9: Docs + post-task cleanup

**Files to create/modify:**
- Create: `docker/README.md`
- Create: `docs/plans/2026-05-23-isolar-docker-demo-IMPLEMENTED.md`

**Step 1: Create `docker/README.md`**

```markdown
# iSolar Demo Stack

One-command demo environment for iSolar Odoo modules.

## Start

```bash
docker compose up -d --build
```

First boot takes ~3-5 min (installs modules + seeds demo data).  
Open: http://localhost:8069 · Login: admin / admin · DB: isolar

## What's included

- **iSolar Energy** company branding (logo, green/amber palette)
- 3 sample projects (Survey / Installation / Handover stages)
- 6 solar documents (varied types and approval states)
- Checklist items on tasks
- OpenRouter config stubs (no real API key — AI features inactive)

## Stop / reset

```bash
docker compose down          # stop, keep data
docker compose down -v       # stop + delete all data (fresh re-seed on next up)
```

## Logs

```bash
docker compose logs -f odoo
```
```

**Step 2: Create IMPLEMENTED doc at `docs/plans/2026-05-23-isolar-docker-demo-IMPLEMENTED.md`** — fill in after all tasks complete, listing: files added, key patterns (httpx layer, branding via partner, noupdate=1 company record update, demo: CLI-init flag behavior), any deviations from plan, commit hashes.

**Step 3: Update PR #1 description** — append Docker demo section to the test plan in `https://github.com/teamx10/tx10-odoo/pull/1`.

**Step 4: Commit docs**

```bash
git add docker/README.md docs/plans/2026-05-23-isolar-docker-demo-IMPLEMENTED.md
git commit -m "[ADD] solar_demo: docker README and implementation log"
```

---

## Summary of files created

```
custom_addons/solar_demo/
├── __init__.py
├── __manifest__.py
├── data/
│   ├── branding.xml
│   └── img/
│       └── isolar_logo.png
├── demo/
│   └── solar_demo_data.xml
└── tests/
    ├── __init__.py
    └── test_solar_demo.py

docker/
├── Dockerfile
├── odoo.conf
└── README.md

docker-compose.yml
```

## Commit sequence (7 commits)

1. `[ADD] solar_demo: scaffold module with empty data stubs and full test suite`
2. `[ADD] solar_demo: add placeholder iSolar logo (256×256 PNG)`
3. `[ADD] solar_demo: branding.xml — iSolar Energy company name, logo, and colours`
4. `[ADD] solar_demo: demo partners (3 clients) and projects (survey/install/handover)`
5. `[ADD] solar_demo: demo tasks (3) and solar documents (6, varied types/states)`
6. `[ADD] solar_demo: demo checklist items (6 items across 2 tasks, mixed done/pending)`
7. `[ADD] solar_demo: Docker Dockerfile (FROM odoo:19 + httpx) and odoo.conf`
8. `[ADD] solar_demo: docker-compose.yml — self-seeding iSolar demo stack`
9. `[ADD] solar_demo: docker README and implementation log`
