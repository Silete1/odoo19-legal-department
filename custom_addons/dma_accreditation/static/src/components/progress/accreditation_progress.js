import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { _t } from "@web/core/l10n/translation";

/**
 * Reads the `progress_payload` Json field of dma.accreditation.request and
 * draws the accreditation as a rail of steps.
 *
 * Everything it shows is computed on the server (see
 * `_compute_progress_payload`), so the workflow logic stays in Python where the
 * tests are, and this component stays a renderer with no business rules of its
 * own.
 */
export class AccreditationProgress extends Component {
    static template = "dma_accreditation.AccreditationProgress";
    static props = { ...standardFieldProps };

    // Only literal _t() calls reach the .pot, so the labels live in a lookup.
    static labels = {
        done: _t("Done"),
        current: _t("In progress"),
        todo: _t("Not started"),
        blocked: _t("Waiting on"),
        mine: _t("Waiting for you"),
        blockers: _t("Before this step can be completed:"),
        blocked_step: _t("Blocked"),
        progress: _t("Accreditation progress"),
    };

    get payload() {
        return this.props.record.data[this.props.name] || {};
    }

    get steps() {
        return this.payload.steps || [];
    }

    get blockers() {
        return this.payload.blockers || [];
    }

    /** Every department that still owes a move; two of them at the parallel step. */
    get pendingRoles() {
        return this.payload.pending_roles || [];
    }

    /** The status of a step in words, for readers who cannot see the tint. */
    statusLabel(step) {
        if (step.status === "current" && this.blockers.length) {
            return AccreditationProgress.labels.blocked_step;
        }
        return AccreditationProgress.labels[step.status] || "";
    }

    get label() {
        return AccreditationProgress.labels;
    }

    /** Tooltip for a step: who decided it and when. */
    stepTitle(step) {
        if (step.user && step.date) {
            return _t("%(role)s — %(user)s, %(date)s", {
                role: step.role,
                user: step.user,
                date: step.date,
            });
        }
        return step.role;
    }

    stepClass(step) {
        const blocked = step.status === "current" && this.blockers.length;
        return [
            "o_dma_step",
            `o_dma_step_${step.status}`,
            blocked ? "o_dma_step_blocked" : "",
        ].filter(Boolean).join(" ");
    }
}

registry.category("fields").add("dma_accreditation_progress", {
    component: AccreditationProgress,
    displayName: _t("Accreditation Progress"),
    supportedTypes: ["json"],
    // The rail is placed straight in the sheet rather than inside a <group>, so
    // it never inherits the width: 100% Odoo grants group descendants, and the
    // seven column grid would be shrink-to-fit.
    additionalClasses: ["d-block", "w-100"],
    // A payload that ever came back empty would make the whole rail disappear
    // rather than render as an empty one.
    isEmpty: () => false,
});
