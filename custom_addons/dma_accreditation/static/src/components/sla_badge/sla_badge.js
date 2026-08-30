import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { _t } from "@web/core/l10n/translation";

/**
 * Reads the `sla_payload` Json field of dma.accreditation.request and draws
 * how long the file has been where it is, against the target.
 *
 * Every string it shows - the verdict, the waiting time, the department, the
 * deadline - is composed and translated on the server (see
 * `_sla_badge_payload`), exactly like the progress rail's payload. The
 * component owns the layout and nothing else: there is no threshold, no
 * duration arithmetic and no business rule in this file, so the Python tests
 * remain the only place the service level is defined.
 *
 * Colour is never the sole carrier: each verdict ships an icon and a written
 * label alongside its hue.
 */
export class AccreditationSlaBadge extends Component {
    static template = "dma_accreditation.AccreditationSlaBadge";
    static props = {
        ...standardFieldProps,
        compact: { type: Boolean, optional: true },
    };

    // Only literal _t() calls reach the .pot, so the labels live in a lookup.
    static labels = {
        serviceLevel: _t("Service level"),
        parties: _t("Both departments are answerable for this step:"),
    };

    get payload() {
        return this.props.record.data[this.props.name] || {};
    }

    get label() {
        return AccreditationSlaBadge.labels;
    }

    /** Nothing to draw for a decided file: it owes nobody anything. */
    get isSilent() {
        return !this.payload.state || this.payload.state === "not_applicable";
    }

    get compact() {
        return Boolean(this.props.compact);
    }

    get rootClass() {
        return `o_dma_sla o_dma_sla_${this.payload.state}${this.compact ? " o_dma_sla_compact" : ""}`;
    }

    /** The one line a list cell has room for. */
    get summary() {
        const parts = [this.payload.state_label];
        if (this.payload.age) {
            parts.push(this.payload.age);
        }
        return parts.filter(Boolean).join(" · ");
    }

    /** The whole story, for the hover. */
    get title() {
        return [
            this.payload.state_label,
            this.payload.age_label,
            this.payload.due_label,
            this.payload.target_label,
            this.payload.waiting_on,
            this.payload.escalation_label,
        ].filter(Boolean).join(" — ");
    }
}

export const accreditationSlaBadge = {
    component: AccreditationSlaBadge,
    displayName: _t("Accreditation Service Level"),
    supportedTypes: ["json"],
    supportedOptions: [
        {
            label: _t("Compact"),
            name: "compact",
            type: "boolean",
            help: _t("One line only, for a kanban card or a narrow list."),
        },
    ],
    extractProps: ({ options }) => ({ compact: Boolean(options.compact) }),
};

registry.category("fields").add("dma_sla_badge", accreditationSlaBadge);
