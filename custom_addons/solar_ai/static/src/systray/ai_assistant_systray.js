/** @odoo-module */
import { Component, reactive } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { AiAssistantPanel } from "../components/ai_assistant_panel";

// Shared reactive state — outlives any single component instance.
const _panelState = reactive({ open: false, chatId: null });

registry.category("services").add("solar_ai_assistant", {
    start() {
        return {
            openChat(chatId) {
                _panelState.chatId = chatId || null;
                _panelState.open = true;
            },
            close() {
                _panelState.open = false;
                _panelState.chatId = null;
            },
        };
    },
});

// Client action: called from the "Continue in assistant" form-view button.
registry.category("actions").add("solar_ai.continue_chat", (env, action) => {
    const chatId = action.context?.active_id || null;
    env.services["solar_ai_assistant"].openChat(chatId);
});

export class AiAssistantSystray extends Component {
    static template = "solar_ai.AiAssistantSystray";
    static components = { AiAssistantPanel };

    setup() {
        this.panelState = _panelState;
    }

    toggle() {
        _panelState.open = !_panelState.open;
        if (!_panelState.open) {
            _panelState.chatId = null;
        }
    }
}

registry.category("systray").add("solar_ai.assistant", {
    Component: AiAssistantSystray,
}, { sequence: 5 });
