# 11b. Чтение результата портальной подписи (подпись ставится в браузере, см. docs/DEMO-WALKTHROUGH.md).
import base64
import hashlib
import os

with scenario("11b результат демоподписи", "demo-pm (чтение)"):
    req = env(user=xid(env, "user_pm"))["sign.oca.request"].browse(xid(env, "sign_request_fo001").id)
    signer = req.signer_ids[:1]
    check(req.state == "2_signed", f"{req.name}: state={req.state}, signed {signer.signed_on} by {signer.partner_id.name}")
    tmpl_hash = hashlib.sha1(base64.b64decode(xid(env, "sign_tmpl_acceptance").data)).hexdigest()
    pdf = base64.b64decode(req.data)
    check(hashlib.sha1(pdf).hexdigest() != tmpl_hash and req.current_hash == hashlib.sha1(pdf).hexdigest(),
          f"PDF изменён подписью, current_hash совпадает ({req.current_hash[:12]}…), {len(pdf)} байт")
    values = [str(v.get("value"))[:30] for v in (req.signatory_data or {}).values()]
    check(any(v.startswith("data:image/png") for v in values) and any(v and not v.startswith("data:") for v in values),
          f"значения полей: имя + PNG подписи {values}")
    logs = env["sign.oca.request.log"].sudo().search([("request_id", "=", req.id)], order="id").mapped("action")
    check(bool(logs), f"журнал действий: {logs}")
    fo = xid(env, "fso_install")
    check(fo.sign_request_state == "2_signed", f"{fo.name}.sign_request_state = {fo.sign_request_state}")
    out = os.path.join(os.environ.get("SOLAR_DEMO_DIR", "."), "docs", "signed-acceptance-act-FO001.pdf")
    with open(out, "wb") as fh:
        fh.write(pdf)
    print(f"signed PDF → {out}")

with scenario("12 карта — ПРОПУЩЕН, проверено отсутствие", "—"):
    mods = env["ir.module.module"].search([("name", "in", ["base_google_map", "web_view_google_map",
                                                           "fieldservice_google_map"])])
    check(all(m.state == "uninstalled" for m in mods),
          "НЕ УСТАНОВЛЕНА намеренно: нет разрешённого API-ключа Google (billing) — "
          + ", ".join(f"{m.name}={m.state}" for m in mods))
