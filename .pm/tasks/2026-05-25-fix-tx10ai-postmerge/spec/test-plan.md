# Test Plan: Fix tx10_ai post-merge issues

**Task:** 2026-05-25-fix-tx10ai-postmerge
**Branch:** feat/tx10-ai-discuss
**Test file:** custom_addons/tx10_ai/tests/test_tx10_ai_discuss.py

---

## Test Strategy

### Unit vs Integration

All `TestTx10AiErrorSurfacing` tests are **unit tests with real DB transactions** (Odoo
`TransactionCase`). The database is used for real model/channel creation; only the HTTP
boundary (httpx.post) is mocked. This matches the pattern used in the existing
`TestTx10AiCronAgent` class and avoids the need for a running OpenRouter endpoint.

### What to mock and why

| Boundary | Mock target | Reason |
|----------|-------------|--------|
| OpenRouter HTTP calls | `httpx.post` (module-level patch) | Deterministic errors, no network, fast |
| `ir.config_parameter` key | Set/unset real param in DB | Tests the actual lookup path in `_build_headers()` |
| Admin check | Assign `base.group_system` via real `group_ids` | Tests the real Odoo group check, not a stub |

`httpx.post` is patched at the `httpx` module level (not `tx10_ai_service.httpx.post`) because
`tx10_ai_service.py` imports `httpx` directly and calls `httpx.post(...)`. This is the same
pattern used in `TestTx10AiCronAgent`.

### Error code flow (from design A1 + A2)

```
chat_with_tools() -- no key --> {error:"no_api_key", error_code:"no_api_key", content:""}
                                    |
                               _do_agent_cycle()
                                    |
                          _format_error("no_api_key")
                                    |
                      friendly text [+ "код: no_api_key" for admin]
                                    |
                          _run_agent() --> channel.message_post()  <-- ALWAYS posts
```

### Odoo test framework notes

- All classes tagged `@tagged("tx10_ai", "post_install", "-at_install")` to match existing suite.
- `TransactionCase` wraps each test in a savepoint; changes are rolled back between tests.
- `setUpClass` runs once per class in a shared savepoint; data created there is shared.
- `ir.config_parameter` set in `setUpClass` survives across test methods in the same class.
- `invalidate_recordset()` must be called on a record after SQL-level mutations (the CAS
  `UPDATE` in `_run_agent` bypasses the ORM cache).

---

## Part A: Error Surfacing Tests (new class)

### TestTx10AiErrorSurfacing — setUpClass

```python
@tagged("tx10_ai", "post_install", "-at_install")
class TestTx10AiErrorSurfacing(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # bot partner — must exist (created by tx10_ai data file)
        cls.bot_partner = cls.env.ref("tx10_ai.partner_ai_bot")

        # regular (non-admin, non-manager) user — used as chat owner
        cls.plain_user = cls.env["res.users"].create({
            "name": "Plain User",
            "login": "plain_error@test.local",
            "password": "pass",
            "group_ids": [(6, 0, [cls.env.ref("base.group_user").id])],
        })

        # admin user — in base.group_system
        cls.admin_user = cls.env["res.users"].create({
            "name": "Sys Admin",
            "login": "sysadmin_error@test.local",
            "password": "pass",
            "group_ids": [(6, 0, [
                cls.env.ref("base.group_user").id,
                cls.env.ref("base.group_system").id,
            ])],
        })
```

**Key setup points:**

- `cls.bot_partner` — obtained via `env.ref` from the module's data XML; must exist at
  `post_install` time.
- `cls.plain_user` — `base.group_user` only; no project manager, no system.
- `cls.admin_user` — `base.group_system`; this is the exact group boundary gated in
  `_format_error()` per the design decision ("project-manager/admin").
- **No API key is set by default** in this class — `tc-A1` relies on the param being absent.
  `tc-A2` sets it to a dummy value so `_build_headers()` returns headers before the mock raises.

**Helper (shared across test methods):**

```python
def _setup_pending_chat(self, user):
    """Create channel + chat + one pending user message. Returns (chat, channel)."""
    channel = self.env["discuss.channel"].with_user(user)._get_or_create_chat(
        [self.bot_partner.id, user.partner_id.id]
    )
    chat = self.env["tx10.ai.chat"].create({
        "name": "Error test DM",
        "user_id": user.id,
        "channel_id": channel.id,
        "pending_agent_run": True,
    })
    self.env["tx10.ai.message"].create({
        "chat_id": chat.id,
        "role": "user",
        "content": "test trigger",
    })
    return chat, channel
```

---

### TC-A1: No API key → friendly message posted

**Purpose:** Proves that a missing API key produces a user-visible bot reply containing
"не налаштовано" — no silent death.

**Given:**
- `tx10_ai.openrouter_api_key` param is absent (never set in this class's `setUpClass`).
- A channel and chat exist with `pending_agent_run=True` for `cls.plain_user`.

**When:**
- `self.env["tx10.ai.chat"]._cron_run_pending_chats()` is called.
  No `httpx.post` patch needed — `_build_headers()` returns `None` before making any
  HTTP call, so the mock is not required.

**Then:**
- A `mail.message` authored by `cls.bot_partner` appears in the channel
  (count of bot messages increases by at least 1).
- The body of that message contains the substring `"не налаштовано"`.

**Assertion pseudocode:**

```python
def test_no_api_key_posts_friendly_message(self):
    chat, channel = self._setup_pending_chat(self.plain_user)
    bot_msgs_before = channel.message_ids.filtered(
        lambda m: m.author_id == self.bot_partner
    )

    self.env["tx10.ai.chat"]._cron_run_pending_chats()

    channel.invalidate_recordset()
    bot_msgs_after = channel.message_ids.filtered(
        lambda m: m.author_id == self.bot_partner
    )
    new_msgs = bot_msgs_after - bot_msgs_before
    self.assertTrue(new_msgs, "Bot must post a message when API key is missing")
    body = new_msgs[0].body or ""  # body is Markup HTML
    self.assertIn("не налаштовано", body)
```

**Notes:**
- `mail.message.body` is stored as HTML (Markup). The substring check is sufficient because the
  friendly text is wrapped in the body as plain text content (no encoding of Cyrillic chars).
- `channel.invalidate_recordset()` is needed to bypass the ORM cache after cron's SQL mutations.

---

### TC-A2: HTTP 500 → friendly message posted

**Purpose:** Proves that an upstream 5xx response is caught and surfaced as a user-visible
"тимчасово недоступний" message, not swallowed silently.

**Given:**
- `tx10_ai.openrouter_api_key` param is set to `"dummy-key"` (so `_build_headers()` returns
  headers and proceeds to call `httpx.post`).
- A channel and chat exist with `pending_agent_run=True` for `cls.plain_user`.
- `httpx.post` is patched to raise `httpx.HTTPStatusError`.

**Mock configuration:**

```python
mock_response = MagicMock()
mock_response.status_code = 500
mock_response.text = "Internal Server Error"
mock_post.side_effect = httpx.HTTPStatusError(
    message="500 Internal Server Error",
    request=MagicMock(),
    response=mock_response,
)
```

**When:**
- `self.env["tx10.ai.chat"]._cron_run_pending_chats()` is called inside
  `@patch("httpx.post")` context.

**Then:**
- A bot `mail.message` appears in the channel (count increases by at least 1).
- The body of that message contains the substring `"тимчасово недоступний"`.

**Assertion pseudocode:**

```python
@patch("httpx.post")
def test_http_500_posts_friendly_message(self, mock_post):
    self.env["ir.config_parameter"].set_param("tx10_ai.openrouter_api_key", "dummy-key")
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"
    mock_post.side_effect = httpx.HTTPStatusError(
        message="500 Server Error", request=MagicMock(), response=mock_response
    )
    chat, channel = self._setup_pending_chat(self.plain_user)
    bot_msgs_before = channel.message_ids.filtered(
        lambda m: m.author_id == self.bot_partner
    )

    self.env["tx10.ai.chat"]._cron_run_pending_chats()

    channel.invalidate_recordset()
    bot_msgs_after = channel.message_ids.filtered(
        lambda m: m.author_id == self.bot_partner
    )
    new_msgs = bot_msgs_after - bot_msgs_before
    self.assertTrue(new_msgs, "Bot must post a message on HTTP 500")
    body = new_msgs[0].body or ""
    self.assertIn("тимчасово недоступний", body)
```

**Notes:**
- `httpx.HTTPStatusError` requires `request=` and `response=` kwargs; mock both with `MagicMock`.
- The patch must wrap both the param-set and the cron call, so use a `with patch(...)` block or
  decorate the test method and pass `mock_post` as a parameter.
- Importing `httpx` in the test file: `import httpx` at the top of the test module.

---

### TC-A3: Admin sees error code in posted body

**Purpose:** Verifies that `_format_error()` appends `"код: no_api_key"` when the chat's
`user_id` is in `base.group_system`.

**Given:**
- `tx10_ai.openrouter_api_key` param is absent.
- A channel and chat exist with `pending_agent_run=True` for `cls.admin_user`
  (who is in `base.group_system`).

**When:**
- `_cron_run_pending_chats()` is called (no mock needed — no HTTP call is made).

**Then:**
- A bot `mail.message` appears in the channel.
- The body contains the substring `"код: no_api_key"`.

**Assertion pseudocode:**

```python
def test_admin_sees_error_code(self):
    chat, channel = self._setup_pending_chat(self.admin_user)
    bot_msgs_before = channel.message_ids.filtered(
        lambda m: m.author_id == self.bot_partner
    )

    self.env["tx10.ai.chat"]._cron_run_pending_chats()

    channel.invalidate_recordset()
    bot_msgs_after = channel.message_ids.filtered(
        lambda m: m.author_id == self.bot_partner
    )
    new_msgs = bot_msgs_after - bot_msgs_before
    self.assertTrue(new_msgs, "Bot must post a message for admin user")
    body = new_msgs[0].body or ""
    self.assertIn("код: no_api_key", body)
```

**Notes:**
- `chat.user_id` is `cls.admin_user` — `_format_error()` reads `self.user_id` to determine
  group membership. The cron runs as `sudo`, but `self.user_id` on the chat record points to
  the admin user → group check passes → code is appended.
- If `_format_error()` uses `self.env.user` instead of `self.user_id`, the test would need
  adjustment. Validate the implementation matches the design (design says `self.user_id`).

---

### TC-A4: Non-admin does not see error code

**Purpose:** Verifies that plain users receive the friendly message WITHOUT the technical
error code appended.

**Given:**
- `tx10_ai.openrouter_api_key` param is absent.
- A channel and chat exist with `pending_agent_run=True` for `cls.plain_user`
  (who is in `base.group_user` only).

**When:**
- `_cron_run_pending_chats()` is called.

**Then:**
- A bot `mail.message` appears in the channel.
- The body does NOT contain the substring `"код:"`.
- The body still contains `"не налаштовано"` (the friendly message is present).

**Assertion pseudocode:**

```python
def test_non_admin_no_error_code(self):
    chat, channel = self._setup_pending_chat(self.plain_user)
    bot_msgs_before = channel.message_ids.filtered(
        lambda m: m.author_id == self.bot_partner
    )

    self.env["tx10.ai.chat"]._cron_run_pending_chats()

    channel.invalidate_recordset()
    bot_msgs_after = channel.message_ids.filtered(
        lambda m: m.author_id == self.bot_partner
    )
    new_msgs = bot_msgs_after - bot_msgs_before
    self.assertTrue(new_msgs, "Bot must post a message for plain user")
    body = new_msgs[0].body or ""
    self.assertNotIn("код:", body, "Non-admin must not see technical error code")
    self.assertIn("не налаштовано", body, "Friendly message must still appear")
```

**Notes:**
- The `assertNotIn("код:", ...)` check is intentionally broad — it catches any error code,
  not just `no_api_key`, so future codes also won't leak to plain users.
- If `_format_error()` also exposes codes to `project.group_project_manager`, revisit TC-A3/A4
  with a manager user to pin down the exact boundary. Current decision: `group_system` only.

---

## Part B: Systray (manual verification only)

**Rationale:** The `tx10_ai_systray.js` / `tx10_ai_systray.xml` components are OWL components
running inside the browser. Odoo's `TransactionCase` and `HttpCase` cannot execute JavaScript.
Testing the click behavior and floating chat window requires a full browser context.

**Manual E2E verification steps** (from design § Verification):

```
1. Boot: ./docker-restart.sh (or docker compose up)
2. Open http://localhost:8069 as any internal user
3. Observe: exactly ONE robot icon in the top navbar (the new tx10_ai systray button)
   Expected icon: fa-robot or fa-comments (NOT fa-android from solar_ai)
   Expected tooltip/aria-label: "TeamX10 AI"
4. Click the icon
   Expected: floating Discuss chat window opens showing the "TeamX10 AI" DM channel
   Expected: no page navigation (it opens in-place)
5. Settings > Technical > Parameters OR Settings > TeamX10 AI Assistant block
   Expected: block title reads "TeamX10 AI Assistant" (not "TX10 AI Assistant")
   Expected: no second "Solar AI Assistant" block
6. Verify solar_ai is gone:
   Settings > Apps: search "solar_ai" → module not listed as installed
```

**Link to full design verif steps:** `design.md § Verification steps 1-7`

---

## Part C: Regression — existing tests still pass

The new `TestTx10AiErrorSurfacing` class must not break the four existing test classes:

| Existing class | Tests | Key dependency |
|----------------|-------|----------------|
| `TestTx10AiDiscussHook` | 3 | hook skips bot, creates user msg, ignores non-bot channel |
| `TestTx10AiCronAgent` | 2 | cron posts reply, clears pending flag |
| `TestTx10AiNlConfirm` | 2 | NL confirm yes/no flows |
| `TestTx10AiBootstrap` | 2 | bootstrap creates DM, no duplicate on second call |

**Risk:** None of the new changes touch existing model fields or method signatures. The only
structural change is adding `error_code` to service return dicts (backward compatible — callers
that don't check it are unaffected) and replacing `Markup.escape("")` returns with formatted
messages.

**Regression run command (same as full tx10_ai tag):**

```bash
./odoo-bin -d <db> --test-tags tx10_ai --stop-after-init
```

All 9 existing + 4 new = **13 tests** must pass.

---

## Test Commands

### Run only the new error-surfacing tests (by class name):

```bash
./odoo-bin -d <db> --test-tags :TestTx10AiErrorSurfacing --stop-after-init
```

### Run the full tx10_ai suite (regression + new):

```bash
./odoo-bin -d <db> --test-tags tx10_ai --stop-after-init
```

### Run from a specific test file (useful for faster feedback during development):

```bash
./odoo-bin -d <db> \
  --test-file custom_addons/tx10_ai/tests/test_tx10_ai_discuss.py \
  --stop-after-init
```

### Run a single method:

```bash
./odoo-bin -d <db> \
  --test-tags :TestTx10AiErrorSurfacing.test_admin_sees_error_code \
  --stop-after-init
```

> Replace `<db>` with the actual database name (e.g. `isolar`).
> In Docker: `docker exec -it <odoo_container> ./odoo-bin -d isolar --test-tags tx10_ai --stop-after-init`

---

## Coverage Gaps / Limitations

| Gap | Reason not tested |
|-----|-------------------|
| Systray click → floating chat window | OWL JS; requires a browser (Playwright/HttpCase with JS) |
| Settings block title "TeamX10 AI Assistant" | XML rendering; verified manually |
| `solar_ai` uninstall / module removal | DB-level destructive operation; not repeatable in unit tests |
| `network_error` (httpx.RequestError) | Path is structurally identical to `http_error`; `RequestError` mock is a one-line variant of TC-A2. Can be added if deemed worth the coverage. |
| `empty_choices` and `terminated_*` error codes | Same surfacing path as `no_api_key` and `http_error`; substring varies. Not duplicated to keep suite lean. |
| Multi-worker CAS race condition | `pending_agent_run` double-run prevention is tested implicitly by `TestTx10AiCronAgent.test_cron_clears_pending_flag`; a true race requires two DB connections in parallel — out of scope. |
| `_format_error` for `project.group_project_manager` | Design decision is `group_system` only; if scope expands, add TC-A3b with a manager user. |
| `mail.message.body` HTML structure | Substring check is sufficient; full DOM assertions are fragile against minor markup changes. |
