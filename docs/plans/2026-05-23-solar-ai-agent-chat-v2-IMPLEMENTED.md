# Solar AI Agent Chat v2 — Implementation Log

**Plan:** `2026-05-23-solar-ai-agent-chat-v2.md`
**Date:** 2026-05-23
**Branch series:** feat/solar-ai-guards-extraction → feat/solar-ai-agent-phase-a → feat/solar-ai-agent-phase-b → feat/solar-ai-agent-phase-c

---

## Routes / Files Added

```
custom_addons/solar_ai/
  controllers/
    _guards.py                  NEW — auth + rate-limit guards (extracted from olg_proxy)
    ai_chat.py                  NEW — /agent/step, /agent/confirm, /agent/reject
    olg_proxy.py                MOD — imports from _guards instead of inlining

  models/
    solar_ai_service.py         MOD — chat_with_tools() added; no raw tc key stored
    solar_ai_agent.py           NEW — _MODEL_REGISTRY, tool dispatcher, write tools
    solar_ai_chat.py            NEW — solar.ai.chat model (budget, round counter)
    solar_ai_message.py         NEW — solar.ai.message model (roles, status, proposed_action)

  security/
    ir.model.access.csv         MOD — added access for solar.ai.chat, solar.ai.message
    solar_ai_security.xml       NEW — ir.rule: per-user record isolation

  data/
    config_params.xml           (unchanged)

  views/
    solar_ai_chat_views.xml     NEW — list/form views, menus, client action

  static/src/
    systray/ai_assistant_systray.js   NEW — reactive _panelState, solar_ai_assistant service
    systray/ai_assistant_systray.xml  NEW — systray button + panel mount
    components/ai_assistant_panel.js  NEW — sendMessage, _runAgentLoop, _executeClientTools
    components/ai_assistant_panel.xml NEW — panel UI with resume hint
    components/ai_assistant_panel.scss NEW — panel layout
    tests/tours/ai_panel.js           NEW — ai_panel_open_close, ai_panel_send_empty_ignored

  tests/
    test_solar_ai.py            MOD — guards tests, chat_with_tools tests
    test_solar_ai_agent.py      NEW — 47 tests across 5 classes
```

---

## Key Patterns Established

| Pattern | Location | Why |
|---------|----------|-----|
| Atomic CAS confirm | `ai_chat.py:agent_confirm` | Prevents double-confirm in multi-worker Odoo |
| Atomic token budget | `ai_chat.py:agent_step` | `UPDATE … SET total_tokens = total_tokens + %s RETURNING …` |
| Module-level `_guards` import | `ai_chat.py` | Enables mock patching in tests (`patch("…_guards.check_rate_limit")`) |
| Single `_MODEL_REGISTRY` | `solar_ai_agent.py` | Capabilities + write_fields + read_fields per model in one place |
| `arguments_str` stored, not parsed | `solar_ai_service.py` | Reconstructs LLM wire format in `_build_messages` without re-serializing |
| `reactive()` module-level state | `ai_assistant_systray.js` | Shared between service and OWL component across lifecycle |
| Client action `solar_ai.continue_chat` | `ai_chat.js` + XML | Form-view button → panel opens with active_id as chatId |

---

## v2 Blocker/Major Fixes Implemented

| # | Fix |
|---|-----|
| B1 | CAS confirm: `UPDATE … WHERE status='pending_confirmation'` + rowcount check |
| B3 | `fields.Datetime.now()` for `executed_at` |
| B4 | Atomic token budget via raw SQL `RETURNING` |
| B5 | `chat_id` guard in write tools before any ORM call |
| B6 | Explicit `message_id` guard in `agent_reject` |
| B7 | JS tours + `HttpCase.start_tour()` tests |
| B8 | double-confirm test: pre-seed SQL → counts 0→1→1 |
| M11 | Narrow catch: `ValueError` + `AccessError` only |
| M12 | `search(limit=20, order='id desc')` instead of loading all messages |
| M13 | `import datetime as dt` at module level |
| M14 | No `raw: tc` key stored; `arguments_str` reconstructed in `_build_messages` |
| M15 | `schedule_activity`: `len(summary) > 200` + `date.fromisoformat()` validation |
| M21 | Single `_MODEL_REGISTRY` dict replaces three parallel maps |

---

## Test Summary

```
47 tests, 0 failed, 0 errors
Classes: TestSolarAiBase, TestSolarAiService, TestOlgProxy,
         TestSolarAiModels, TestSolarAiAgent, TestAgentStepController,
         TestAgentConfirmController, TestAiAssistantTour
```

---

## Deviations from Plan

- **`widget="one2many_list"`** removed from form view — not a valid Odoo 19 widget name; default list rendering used instead.
- **XML ordering** in `solar_ai_chat_views.xml`: `action_solar_ai_continue_chat` placed first because Odoo resolves `%(xmlid)d` in-pass; forward references fail.
- **Resume hint** ("Продовжуємо попередній чат…") added to panel XML — not in plan, but improves UX for zero cost.

---

## Commit List

| PR | Hash | Message |
|----|------|---------|
| PR0 | 3bc84a0 | [REF] solar_ai: extract auth/rate-limit guards |
| PR1 | b67011b | chat_with_tools() |
| PR1 | a8bd5af | solar.ai.chat and solar.ai.message models |
| PR1 | 22d901a | solar.ai.agent — _MODEL_REGISTRY |
| PR1 | 0e5319 | /agent/step — atomic budget |
| PR1 | ba5f4d9 | OWL panel + tour tests |
| PR2 | 391d427 | write tools — chat_id guard, schedule_activity |
| PR2 | 4105442 | /agent/confirm + /agent/reject atomic CAS |
| PR3 | 059df1b | My AI Chats views + Continue in assistant |

---

## Manual Verification Checklist

```
[ ] Settings > Technical > Parameters — set solar_ai.openrouter_api_key
[ ] Click 🤖 systray → panel opens
[ ] Type "Знайди проєкт X" → AI responds with results
[ ] Write action → confirm card appears → click Підтвердити → record created
[ ] Double-click Підтвердити quickly → only 1 record created
[ ] Solar AI > My AI Chats → list shows conversations
[ ] Open a chat form → click "Continue in assistant" → panel opens with chatId pre-set
[ ] Panel shows "Продовжуємо попередній чат…" hint
```
