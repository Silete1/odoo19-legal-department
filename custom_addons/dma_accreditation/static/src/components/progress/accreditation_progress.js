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
        blockers: _t("Before this step can be completed:"),
        noBlockers: _t("Nothing is blocking this step."),
        closed: _t("This file is closed."),
        progress: _t("Progress"),
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

    get stepKeys() {
        return this.steps.map((step) => step.key);
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
});
