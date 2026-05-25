# Implementation Log: Solar AI — три бага (400 + навигация)

**Задача:** устранить 3 одновременных бага, видимых на Image #9.  
**Ветка:** `feat/solar-ai-settings`  
**Дата:** 2026-05-24

---

## Диагноз (подтверждён live-данными)

| Баг | Корень |
|-----|--------|
| 400 Bad Request от OpenRouter | `solar_ai.default_model = ~google/gemini-flash-latest` — `~` делает ID невалидным |
| 400 при повторных сообщениях после навигации | «Висячие» assistant-`tool_calls` в истории: клиентские инструменты никогда не писали `tool`-ответы в БД; сообщения #2 и #5 в live-БД подтвердили это |
| URL `/odoo/settings/project.project` + «Unnamed» | `doAction({res_model, views})` без action id/name → меню-сервис не вызывает `setCurrentMenu`, URL клеится из стека Settings |

---

## Файлы изменены

### `custom_addons/solar_ai/models/solar_ai_agent.py`
- `_MODEL_REGISTRY`: добавлен ключ `"action"` с xml_id оконного действия для `project.project`, `project.task`, `res.partner` (solar.document — нет, т.к. window action не зарегистрирован).
- Новый метод `resolve_navigation_action(model)`: возвращает xml_id через `env.ref(raise_if_not_found=False)`; `None` при отсутствии маппинга.

### `custom_addons/solar_ai/controllers/ai_chat.py`
- `agent_step`: при формировании `client_calls` вызывает `resolve_navigation_action` и вкладывает `action_xml_id` в `args`. JS получает готовый xml_id без дополнительного запроса.
- `_build_messages`: полностью переписана логика сборки истории. Перед эмиссией assistant-сообщений с tool_calls строится `responded_ids` = (БД tool-сообщения) ∪ (входящий tool_results). Вызовы без ответа фильтруются; пустое assistant-сообщение без контента — пропускается. Устраняет как уже испорченные строки, так и будущие клиентские инструменты.

### `custom_addons/solar_ai/static/src/components/ai_assistant_panel.js`
- `_executeClientTools`: оба ветвления (`navigate_to_record`, `open_model_list`) проверяют `tc.args.action_xml_id`. При наличии — `doAction(xmlId, {clearBreadcrumbs:true, [viewType/props для form]})`. Fallback на голый act_window сохранён.

### `custom_addons/solar_ai/static/src/components/model_select_widget.js`
- `setup()`: `this._lastValid` инициализируется текущим сохранённым значением.
- `onBlur`: commit только если `query` точно совпадает с известной моделью или пуст; иначе — откат к `_lastValid` + `state.invalid = true`.
- `onSelect`: обновляет `_lastValid` + сбрасывает `invalid`.
- `onInput`: сбрасывает `invalid`.

### `custom_addons/solar_ai/static/src/components/model_select_widget.xml`
- `<input>`: добавлен `t-att-class="{ 'is-invalid': state.invalid }"`.
- Новый блок `t-elif="state.invalid"` с подсказкой «Виберіть модель зі списку».

---

## Разовый фикс данных

```sql
UPDATE ir_config_parameter
SET value = 'google/gemini-flash-latest'
WHERE key = 'solar_ai.default_model';
-- Выполнено. Значение было: ~google/gemini-flash-latest
```

---

## Паттерны, установленные этой задачей

- Маппинг модель→window-action хранится в `_MODEL_REGISTRY["action"]`; резолвится через `env.ref(raise_if_not_found=False)` — безопасно при незагруженных модулях.
- `_build_messages` теперь является единственной точкой гарантии валидности последовательности для LLM; персистить клиентские tool-результаты в БД не требуется.
- JS: всегда использовать `doAction(xmlId, {clearBreadcrumbs:true})` для навигации из systray-панели — иначе URL/breadcrumb наследует текущий контекст приложения.

---

## Верификация

Сервер поднят: `./docker-restart.sh` → `tx10-odoo-odoo-1 Up (healthy)`. Ruff: 0 ошибок.

Ручная проверка в браузере `http://localhost:8069`:
- [ ] Fix A: ввести `~мусор` в Default Model → откат + красный hint
- [ ] Fix A: выбрать модель из списка → коммитится чисто
- [ ] Fix B: чат → «Відкрий список проєктів» → нет 400; повторный вопрос → нет 400
- [ ] Fix B: старый чат (msgs #2/#5 в БД) → новое сообщение проходит без 400
- [ ] Fix C: URL после навигации `/odoo/project/...`, breadcrumb «Проєкти»
- [ ] Регресс: обычный текстовый вопрос отвечает корректно
