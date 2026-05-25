/** @odoo-module */
import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { Reactive } from "@web/core/utils/reactive";
import { AiAssistantPanel } from "../components/ai_assistant_panel";

// Reactive subclass so the object IS the proxy — mutations from the service
// go through the proxy set-trap and notify all useState() subscribers.
class PanelState extends Reactive {
    open = false;
    chatId = null;
}

const _panelState = new PanelState();

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
        // useState links _panelState mutations to this component's render cycle.
        this.panelState = useState(_panelState);
    }

    toggle = () => {
        this.panelState.open = !this.panelState.open;
        if (!this.panelState.open) {
            this.panelState.chatId = null;
        }
    };
}

registry.category("systray").add("solar_ai.assistant", {
    Component: AiAssistantSystray,
}, { sequence: 5 });
