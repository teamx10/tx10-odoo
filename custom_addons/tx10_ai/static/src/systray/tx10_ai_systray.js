/** @odoo-module */
import { Component, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";
import { _t } from "@web/core/l10n/translation";

export class Tx10AiSystray extends Component {
    static template = "tx10_ai.Systray";

    setup() {
        this.store = useService("mail.store");
        this.notification = useService("notification");
        this.channelId = null;
        onWillStart(() => this._fetchChannel());
    }

    async _fetchChannel() {
        try {
            const result = await rpc("/tx10_ai/bot_channel", {});
            this.channelId = result?.channel_id ?? null;
        } catch {
            this.channelId = null;
        }
        return this.channelId;
    }

    async onClick() {
        // Channel may not have existed at page load (bot just bootstrapped) — retry.
        const channelId = this.channelId ?? (await this._fetchChannel());
        if (!channelId) {
            this.notification.add(
                _t("TeamX10 AI is not available yet. Please try again in a moment."),
                { type: "warning" }
            );
            return;
        }
        const thread = await this.store.Thread.getOrFetch({
            id: channelId,
            model: "discuss.channel",
        });
        thread?.open({ focus: true });
    }
}

registry.category("systray").add("tx10_ai.assistant", {
    Component: Tx10AiSystray,
}, { sequence: 10 });
