# Компания, роли (штатные группы), сотрудники и исполнители FSM.
# Пароли берутся из solar-demo/.secrets через переменные окружения PW_*.
import os

company = env.company
company.write({
    "name": "DEMO-SOLAR EPC Demo Co",
    "street": "1 Synthetic Energy Ave",
    "city": "Demo City",
    "zip": "00000",
    "country_id": env.ref("base.ua").id,
    "email": "office@demo-solar.example.invalid",
    "phone": "+000 000 0000",
})
LOG.append(f"= company #{company.id} renamed")

# Внутренние пользователи получают уведомления только в Odoo (inbox), не по email.
ROLES = {
    "pm": ("DEMO-SOLAR PM Olena Demo", "demo-pm", [
        "project.group_project_manager", "fieldservice.group_fsm_dispatcher",
        "purchase.group_purchase_user", "stock.group_stock_user",
        "sign_oca.sign_oca_group_manager",
    ]),
    "tech": ("DEMO-SOLAR Technician Ivan Demo", "demo-tech", [
        # FSM User (не «own»): кнопка Complete в форме заказа доступна только этой группе
        "fieldservice.group_fsm_user", "project.group_project_user",
        "hr_timesheet.group_hr_timesheet_user", "sign_oca.sign_oca_group_user",
        # серийные номера оборудования (stock.lot) видны только Inventory/User
        "stock.group_stock_user",
    ]),
    "svcmgr": ("DEMO-SOLAR Service Manager Petro Demo", "demo-svcmgr", [
        "fieldservice.group_fsm_manager", "maintenance.group_equipment_manager",
        "stock.group_stock_user", "purchase.group_purchase_user",
        "project.group_project_user", "hr_timesheet.group_hr_timesheet_approver",
        "sign_oca.sign_oca_group_manager",
    ]),
}

users = {}
for key, (name, login, groups) in ROLES.items():
    group_ids = [env.ref(g).id for g in groups] + [env.ref("base.group_user").id]
    user = ensure(env, f"user_{key}", "res.users", {
        "name": name,
        "login": login,
        "email": f"{login}@demo-solar.example.invalid",
        "group_ids": [(6, 0, group_ids)],
        "notification_type": "inbox",
        "company_id": company.id,
        "company_ids": [(6, 0, [company.id])],
    }, update=True)
    pw = os.environ.get(f"PW_{key}")
    # пароль — только при создании: смена пароля инвалидирует активные сессии
    if pw and LOG[-1].startswith("+"):
        user.password = pw
    users[key] = user

admin = env.ref("base.user_admin")
admin.write({"name": "DEMO-SOLAR Administrator",
             "email": "admin@demo-solar.example.invalid",
             "notification_type": "inbox"})
# пароль admin меняется один раз (маркер demo_solar.admin_password_set)
if os.environ.get("PW_admin") and not xid(env, "admin_password_set"):
    admin.password = os.environ["PW_admin"]
    ensure(env, "admin_password_set", "ir.config_parameter",
           {"key": "demo_solar.admin_password_set", "value": "1"})
users["admin"] = admin

# Сотрудники — нужны для учёта времени (account.analytic.line.employee_id).
for key, user in users.items():
    emp = env["hr.employee"].search([("user_id", "=", user.id)], limit=1)
    if not emp:
        emp = env["hr.employee"].create({"name": user.name, "user_id": user.id,
                                         "work_email": user.email})
    bind(env, f"employee_{key}", emp)

# Исполнители Field Service (fsm.person наследует res.partner через partner_id).
for key in ("tech", "svcmgr"):
    person = env["fsm.person"].search([("partner_id", "=", users[key].partner_id.id)], limit=1)
    if not person:
        person = env["fsm.person"].create({"partner_id": users[key].partner_id.id})
    bind(env, f"fsm_person_{key}", person)

# Внешний эффект: cron «Update Notification» шлёт данные БД на odoo.com — отключаем.
cron = env.ref("mail.ir_cron_module_update_notification", raise_if_not_found=False)
if cron and cron.active:
    cron.active = False
    LOG.append("cron publisher_warranty disabled")

report("10 company & users")
