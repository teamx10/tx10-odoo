# Каркас проверок сценариев: PASS/FAIL по каждому check, исключение = FAIL сценария.
import contextlib
import traceback

RESULTS = []
_CUR = {}


@contextlib.contextmanager
def scenario(title, actor):
    _CUR.update(title=title, actor=actor, checks=[], error=None)
    sp = env.cr.savepoint()
    try:
        yield
        sp.close(rollback=False)
    except Exception as ex:  # сценарий упал — фиксируем причину, транзакцию сохраняем
        sp.close(rollback=True)
        _CUR["error"] = f"{type(ex).__name__}: {str(ex)[:300]}"
        traceback.print_exc(limit=3)
    ok = _CUR["error"] is None and _CUR["checks"] and all(c[0] for c in _CUR["checks"])
    RESULTS.append(dict(_CUR, ok=bool(ok)))
    env.invalidate_all()


def check(cond, detail):
    _CUR["checks"].append((bool(cond), detail))


def summary():
    lines = []
    for r in RESULTS:
        lines.append(f"{'PASS' if r['ok'] else 'FAIL'} | {r['title']} | {r['actor']}")
        for ok, d in r["checks"]:
            lines.append(f"     {'✓' if ok else '✗'} {d}")
        if r["error"]:
            lines.append(f"     ✗ EXCEPTION {r['error']}")
    print("\n".join(lines))
    print(f"\nTOTAL: {sum(r['ok'] for r in RESULTS)}/{len(RESULTS)} PASS")
