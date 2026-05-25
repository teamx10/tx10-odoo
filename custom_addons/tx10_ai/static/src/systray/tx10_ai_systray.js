/** @odoo-module */
import { Component, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class Tx10AiSystray extends Component {
    static template = "tx10_ai.Systray";

    setup() {
        this.store = useService("mail.store");
        this.rpc = useService("rpc");
        this.partnerId = null;
        onWillStart(async () => {
            const result = await this.rpc("/tx10_ai/bot_partner", {});
            this.partnerId = result?.partner_id ?? null;
        });
    }

    onClick() {
        if (this.partnerId) {
            this.store.openChat({ partnerId: this.partnerId });
        }
    }
}

registry.category("systray").add("tx10_ai.assistant", {
    Component: Tx10AiSystray,
}, { sequence: 10 });
