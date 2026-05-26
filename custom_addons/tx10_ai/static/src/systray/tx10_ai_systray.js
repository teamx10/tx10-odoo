/** @odoo-module */
import { Component, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";

export class Tx10AiSystray extends Component {
    static template = "tx10_ai.Systray";

    setup() {
        this.store = useService("mail.store");
        this.channelId = null;
        onWillStart(async () => {
            try {
                const result = await rpc("/tx10_ai/bot_channel", {});
                this.channelId = result?.channel_id ?? null;
            } catch {
                // Not authenticated or channel not created yet
            }
        });
    }

    async onClick() {
        if (!this.channelId) return;
        const thread = await this.store.Thread.getOrFetch({
            id: this.channelId,
            model: "discuss.channel",
        });
        thread?.open({ focus: true });
    }
}

registry.category("systray").add("tx10_ai.assistant", {
    Component: Tx10AiSystray,
}, { sequence: 10 });
