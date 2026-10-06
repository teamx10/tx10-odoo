# Общие помощники загрузчика демоданных Solar EPC.
# Выполняется внутри `odoo-bin shell` (глобальный `env`), только через ORM.
# Идемпотентность: каждая запись получает xmlid demo_solar.<key>;
# повторный запуск находит её и не создаёт дубль.

MODULE = "demo_solar"
LOG = []


def xid(env, key):
    """Вернуть запись по ключу demo_solar.<key> или пустой recordset/None."""
    return env.ref(f"{MODULE}.{key}", raise_if_not_found=False)


def ensure(env, key, model, vals, update=False):
    """Найти запись по xmlid или создать её; зарегистрировать xmlid."""
    rec = xid(env, key)
    if rec:
        if update:
            rec.write(vals)
        LOG.append(f"= {key}")
        return rec
    rec = env[model].create(vals)
    env["ir.model.data"].create({
        "module": MODULE, "name": key, "model": model,
        "res_id": rec.id, "noupdate": True,
    })
    LOG.append(f"+ {key} ({model} #{rec.id})")
    return rec


def bind(env, key, rec):
    """Привязать xmlid к уже существующей записи (созданной штатным механизмом)."""
    if not xid(env, key) and rec:
        env["ir.model.data"].create({
            "module": MODULE, "name": key, "model": rec._name,
            "res_id": rec.id, "noupdate": True,
        })
        LOG.append(f"~ {key} -> {rec._name} #{rec.id}")
    return rec


def set_config(env, vals):
    """Применить настройки через штатный мастер res.config.settings."""
    env["res.config.settings"].create(vals).execute()
    LOG.append(f"cfg {sorted(vals)}")


def report(title):
    print(f"\n### {title}")
    for line in LOG:
        print("  ", line)
    LOG.clear()
