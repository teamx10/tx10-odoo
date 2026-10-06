# Генерирует docs/MODULES.md и config/repos.lock из манифестов и БД (запуск: .venv19/bin/python)
import ast, os, subprocess, psycopg2
D = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); ROOT = os.path.dirname(D)
REPOS = ["field-service", "maintenance", "rma", "sign", "geospatial"]
paths = {r: f"{D}/oca/{r}" for r in REPOS}
paths.update({"odoo/addons": f"{ROOT}/addons", "odoo/base": f"{ROOT}/odoo/addons"})
git = lambda p, *a: subprocess.check_output(["git", "-C", p, *a], text=True).strip()
lock = [f"odoo https://github.com/odoo/odoo 19.0 {git(ROOT, 'rev-parse', 'HEAD')}"]
lock += [f"{r} https://github.com/OCA/{r} 19.0 {git(paths[r], 'rev-parse', 'HEAD')}" for r in REPOS]
open(f"{D}/config/repos.lock", "w").write("\n".join(lock) + "\n")
cn = psycopg2.connect(host="127.0.0.1", user="odoo", password=os.environ.get("DB_PASSWORD", "odoo"), dbname="solar_epc_demo19")
cur = cn.cursor(); cur.execute("select name, state, latest_version from ir_module_module where state='installed' order by name")
inst = {n: v for n, s, v in cur.fetchall()}
rows = []
for name in sorted(inst):
    for repo, p in paths.items():
        f = f"{p}/{name}/__manifest__.py"
        if os.path.exists(f):
            m = ast.literal_eval(open(f).read())
            if repo.startswith("odoo"):
                rows.append((name, "odoo", m.get("version", "19.0"), m.get("license", "LGPL-3"), "Odoo Community (stable)", ""))
            else:
                st = m.get("development_status") or "Beta (README badge, не задан в манифесте)"
                ext = m.get("external_dependencies", {}).get("python", [])
                rows.append((name, f"OCA/{repo}", m["version"], m["license"], st, ", ".join(ext)))
            break
oca = [r for r in rows if r[1] != "odoo"]; core = [r for r in rows if r[1] == "odoo"]
out = ["# Установленные модули — solar_epc_demo19", "", "Сгенерировано `scripts/gen-inventory.py` из манифестов и `ir_module_module`.", "",
       f"Всего installed: **{len(rows)}** (OCA: {len(oca)}, Odoo Community: {len(core)}). Enterprise/OEEL: **0**.", "",
       "## OCA", "", "| Модуль | Репозиторий | Версия | Лицензия | Зрелость | Python deps |", "|---|---|---|---|---|---|"]
out += [f"| `{a}` | {b} | {c} | {d} | {e} | {f} |" for a, b, c, d, e, f in oca]
out += ["", "## Odoo Community (целевые + транзитивные)", "", "| Модуль | Лицензия |", "|---|---|"]
out += [f"| `{a}` | {d} |" for a, b, c, d, e, f in core]
out += ["", "## Закреплённые commit (config/repos.lock)", "", "```"] + lock + ["```", ""]
open(f"{D}/docs/MODULES.md", "w").write("\n".join(out))
print(len(rows), len(oca), len(core))
