import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { _t } from "@web/core/l10n/translation";

/**
 * How long this file has been where it is, and - the part that matters -
 * whose delay it is.
 *
 * «لدى الجهة منذ ٦ أيام عمل — تجاوز الهدف بيومين» and «بانتظارنا» are two
 * different sentences about the same elapsed time, and a legal department is
 * measured on the second while it can only chase the first. That distinction
 * is the module's headline metric, so the badge states it in words before it
 * states anything in colour.
 *
 * Every string it shows - the verdict, the age, the target, the body - is
 * composed and translated on the server, in the body's own working days,
 * through its `resource.calendar`. There is no threshold, no duration
 * arithmetic and no business rule in this file, which is what keeps the Python
 * tests the only place the clock is defined.
 *
 * The component is used two ways and must read in both: as a field widget on
 * the case form, and - in `compact` mode - as one line inside a Mail Room row
 * or a narrow list cell, where the chip is all the room there is.
 */
export class LegalClockBadge extends Component {
    static template = "legal_procedure.LegalClockBadge";
    static props = {
        // Either a field record (widget use) or a plain payload (row use).
        ...standardFieldProps,
        record: { type: Object, optional: true },
        name: { type: String, optional: true },
        payload: { type: Object, optional: true },
        compact: { type: Boolean, optional: true },
    };
    static defaultProps = { compact: false };

    // Only literal _t() calls reach the .pot, so the component's own few
    // strings live in a lookup rather than inline in the template.
    static labels = {
        clock: _t("Waiting time"),
    };

    get label() {
        return LegalClockBadge.labels;
    }

    get payload() {
        if (this.props.payload) {
            return this.props.payload;
        }
        if (this.props.record && this.props.name) {
            return this.props.record.data[this.props.name] || {};
        }
        return {};
    }

    /** A decided file owes nobody anything, so it says nothing. */
    get isSilent() {
        const state = this.payload.state;
        return !state || state === "not_applicable";
    }

    get rootClass() {
        return [
            "o_legal_clock",
            `o_legal_clock_${this.payload.state}`,
            this.payload.kind ? `o_legal_clock_${this.payload.kind}` : "",
            this.props.compact ? "o_legal_clock_compact" : "",
        ].filter(Boolean).join(" ");
    }

    /** The one line a list cell has room for. */
    get summary() {
        return [this.payload.kind_label, this.payload.age]
            .filter(Boolean)
            .join(" · ");
    }

    /** The whole story, for the hover. */
    get title() {
        return [
            this.payload.kind_label,
            this.payload.age_label,
            this.payload.target_label,
            this.payload.overdue_label,
            this.payload.escalation_label,
        ].filter(Boolean).join(" — ");
    }
}

export const legalClockBadge = {
    component: LegalClockBadge,
    displayName: _t("Legal Waiting Clock"),
    supportedTypes: ["json"],
    supportedOptions: [
        {
            label: _t("Compact"),
            name: "compact",
            type: "boolean",
            help: _t("One line only, for a kanban card or a narrow list cell."),
        },
    ],
    extractProps: ({ options }) => ({ compact: Boolean(options.compact) }),
    // A payload that came back empty would make the badge vanish rather than
    // render as its own silent state, and a vanished badge reads as a bug.
    isEmpty: () => false,
};

registry.category("fields").add("legal_clock_badge", legalClockBadge);
