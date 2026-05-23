/** @odoo-module */
import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { AiAssistantPanel } from "../components/ai_assistant_panel";

export class AiAssistantSystray extends Component {
    static template = "solar_ai.AiAssistantSystray";
    static components = { AiAssistantPanel };

    setup() {
        this.state = useState({ open: false });
    }

    toggle() {
        this.state.open = !this.state.open;
    }
}

registry.category("systray").add("solar_ai.assistant", {
    Component: AiAssistantSystray,
}, { sequence: 5 });
