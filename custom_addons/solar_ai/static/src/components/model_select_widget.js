/** @odoo-module */
import { Component, useState, useRef, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class ModelSelectWidget extends Component {
    static template = "solar_ai.ModelSelectWidget";
    static props = { ...standardFieldProps };

    setup() {
        this.inputRef = useRef("input");
        this._lastValid = this.props.record.data[this.props.name] || "";
        this.state = useState({
            query: this._lastValid,
            isOpen: false,
            models: [],
            loading: false,
            error: null,
            invalid: false,
        });
        this._blurTimer = null;
        onMounted(() => this._loadModels());
        onWillUnmount(() => clearTimeout(this._blurTimer));
    }

    async _loadModels() {
        this.state.loading = true;
        try {
            const resp = await fetch("/solar_ai/openrouter/models");
            if (!resp.ok) throw new Error(resp.statusText);
            const data = await resp.json();
            this.state.models = data.models || [];
        } catch (e) {
            this.state.error = "Could not load model list";
        } finally {
            this.state.loading = false;
        }
    }

    get groups() {
        const q = (this.state.query || "").toLowerCase();
        const map = {};
        for (const m of this.state.models) {
            if (q && !m.id.toLowerCase().includes(q) && !m.name.toLowerCase().includes(q)) {
                continue;
            }
            if (!map[m.provider]) map[m.provider] = [];
            map[m.provider].push(m);
        }
        return Object.entries(map).sort(([a], [b]) => a.localeCompare(b));
    }

    get currentModel() {
        return this.state.models.find((m) => m.id === this.state.query) || null;
    }

    onInput = (ev) => {
        this.state.query = ev.target.value;
        this.state.isOpen = true;
        this.state.invalid = false;
    };

    onFocus = () => {
        if (this.state.models.length) this.state.isOpen = true;
    };

    onBlur = () => {
        this._blurTimer = setTimeout(() => {
            this.state.isOpen = false;
            const q = this.state.query;
            if (!q) {
                this._lastValid = "";
                this._commit("");
            } else if (this.currentModel) {
                this._lastValid = q;
                this._commit(q);
            } else {
                this.state.query = this._lastValid;
                this.state.invalid = true;
            }
        }, 150);
    };

    onSelect = (modelId) => {
        clearTimeout(this._blurTimer);
        this._lastValid = modelId;
        this.state.query = modelId;
        this.state.isOpen = false;
        this.state.invalid = false;
        this._commit(modelId);
    };

    _commit = (value) => {
        this.props.record.update({ [this.props.name]: value || "" });
    };

    formatPrice = (model) => {
        const fmt = (n) => n.toFixed(2).replace(/\.?0+$/, "");
        return `$${fmt(model.pricing_in)} / $${fmt(model.pricing_out)}`;
    };
}

registry.category("fields").add("solar_ai_model_select", {
    component: ModelSelectWidget,
    supportedTypes: ["char"],
});
