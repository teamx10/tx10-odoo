# Мастер-данные: настройки, партнёры, объекты/станции, товары с гарантией,
# категории и теги оборудования, этапы FSM с валидацией и серверным действием.

set_config(env, {
    "group_stock_production_lot": True,
    "group_fsm_equipment": True, "group_fsm_template": True,
    "group_fsm_tag": True, "group_fsm_team": True,
    "fsm_signature_capture": True, "fsm_document_signing": True,
    "fsm_require_signature_to_complete": False,
    "fsm_require_document_signed_to_complete": False,
    "sign_oca_send_sign_request_copy": False,
})

ua = env.ref("base.ua").id
customer = ensure(env, "partner_customer", "res.partner", {
    "name": "DEMO-SOLAR Customer Energy LLC", "is_company": True, "ref": "DEMO-SOLAR-CUST-01",
    "email": "customer@demo-solar.example.invalid", "city": "Demo City", "country_id": ua})
ensure(env, "partner_customer_contact", "res.partner", {
    "name": "DEMO-SOLAR Customer Rep Maria Demo", "parent_id": customer.id,
    "email": "maria.rep@demo-solar.example.invalid"})
vendor = ensure(env, "partner_vendor", "res.partner", {
    "name": "DEMO-SOLAR Supplier Components Ltd", "is_company": True, "ref": "DEMO-SOLAR-VEND-01",
    "email": "sales@supplier.demo-solar.example.invalid", "city": "Vendor Town", "country_id": ua})

# Объекты/станции: координаты задаются вручную (без вызова внешнего геокодера).
STATIONS = [
    ("station_st01", "DEMO-SOLAR-ST01 Solar Park North (5 MWp)", "DEMO-SOLAR-ST01",
     "10 Synthetic Field Rd", "Demo Village North", 50.6100, 30.9100),
    ("station_st02", "DEMO-SOLAR-ST02 Rooftop PV Logistics Hub (800 kWp)", "DEMO-SOLAR-ST02",
     "22 Example Industrial St", "Demo City", 50.4000, 30.6500),
]
stations = {}
for key, name, ref, street, city, lat, lon in STATIONS:
    stations[key] = ensure(env, key, "fsm.location", {
        "name": name, "ref": ref, "owner_id": customer.id, "street": street,
        "city": city, "country_id": ua, "partner_latitude": lat, "partner_longitude": lon,
        "description": "Synthetic demo site. Not a real installation."})

# Категории товаров и оборудования (Maintenance, иерархия OCA).
pcat_root = ensure(env, "pcat_solar", "product.category", {"name": "DEMO-SOLAR Equipment"})
mcat_root = ensure(env, "mcat_solar", "maintenance.equipment.category", {"name": "DEMO-SOLAR Solar Equipment"})
CATS = {"panels": "PV Panels", "inverters": "Inverters", "meters": "Energy Meters"}
pcat, mcat = {}, {}
for k, label in CATS.items():
    pcat[k] = ensure(env, f"pcat_{k}", "product.category", {"name": label, "parent_id": pcat_root.id})
    mcat[k] = ensure(env, f"mcat_{k}", "maintenance.equipment.category",
                     {"name": label, "parent_id": mcat_root.id})

for k, label in {"st01": "Site ST01", "critical": "Critical", "grid": "Grid-connected"}.items():
    ensure(env, f"mtag_{k}", "maintenance.equipment.tag", {"name": f"DEMO-SOLAR {label}"})

# Товары: серийный учёт, гарантия (product_warranty), авто-создание FSM-оборудования.
PRODUCTS = [
    ("prod_pv", "DEMO-SOLAR-PV-550", "PV Module 550 W (synthetic)", "panels", 120.0, 25, "year", True),
    ("prod_inv", "DEMO-SOLAR-INV-100K", "String Inverter 100 kW (synthetic)", "inverters", 6500.0, 5, "year", True),
    ("prod_mtr", "DEMO-SOLAR-MTR-01", "Bidirectional Energy Meter (synthetic)", "meters", 300.0, 24, "month", True),
    ("prod_fuse", "DEMO-SOLAR-FUSE-15A", "DC String Fuse 15 A (spare part)", "inverters", 4.5, 0, "year", False),
]
products = {}
for key, code, name, cat, cost, wn, wt, serial in PRODUCTS:
    tmpl = ensure(env, key, "product.template", {
        "name": name, "default_code": code, "type": "consu", "is_storable": True,
        "tracking": "serial" if serial else "none", "categ_id": pcat[cat].id,
        "standard_price": cost, "list_price": cost * 1.3, "purchase_ok": True, "sale_ok": True,
        "warranty": wn, "warranty_type": wt, "create_fsm_equipment": serial})
    products[key] = tmpl
    ensure(env, f"{key}_supplierinfo", "product.supplierinfo", {
        "partner_id": vendor.id, "product_tmpl_id": tmpl.id, "price": cost,
        "warranty_duration": float(wn), "warranty_return_partner": "supplier"})

# Приёмка создаёт FSM-оборудование из серийных номеров (fieldservice_equipment_stock).
receipt_type = env.ref("stock.picking_type_in")
receipt_type.create_fsm_equipment = True

# Этапы FSM-заказа: Новая → Запланирована → В работе → Выполнена → Закрыта (+ Отменена).
new = env.ref("fieldservice.fsm_stage_new")
done = env.ref("fieldservice.fsm_stage_completed")
new.name = "Новая"
done.name = "Выполнена"
bind(env, "stage_new", new)
bind(env, "stage_done", done)
sched = ensure(env, "stage_scheduled", "fsm.stage", {
    "name": "Запланирована", "stage_type": "order", "sequence": 20, "custom_color": "#4c9be8"})
inprog = ensure(env, "stage_in_progress", "fsm.stage", {
    "name": "В работе", "stage_type": "order", "sequence": 40, "custom_color": "#f0ad4e"})
ensure(env, "stage_closed", "fsm.stage", {
    "name": "Закрыта", "stage_type": "order", "sequence": 90, "is_closed": True,
    "custom_color": "#5cb85c"})

# stage_validation: в «Запланирована» обязателен исполнитель, в «Выполнена» — итог работ.
F = env["ir.model.fields"]
sched.validate_field_ids = [(6, 0, F._get("fsm.order", "person_id").ids)]
done.validate_field_ids = [(6, 0, F._get("fsm.order", "resolution").ids)]

# stage_server_action: при входе в «В работе» — внутренняя активность руководителю сервиса.
action = ensure(env, "srv_action_in_progress", "ir.actions.server", {
    "name": "DEMO-SOLAR: activity for service manager on work start",
    "model_id": env["ir.model"]._get_id("fsm.order"),
    "state": "next_activity",
    "activity_type_id": env.ref("mail.mail_activity_data_todo").id,
    "activity_summary": "Работа начата — проверить ход выполнения",
    "activity_user_type": "specific",
    "activity_user_id": xid(env, "user_svcmgr").id,
    "activity_date_deadline_range": 1, "activity_date_deadline_range_type": "days",
})
inprog.action_id = action

report("20 master data")
