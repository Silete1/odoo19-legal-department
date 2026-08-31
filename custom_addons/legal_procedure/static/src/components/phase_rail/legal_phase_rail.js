import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { _t } from "@web/core/l10n/translation";

/**
 * The case's progress as four to six PHASES - never as thirteen steps.
 *
 * USWDS is explicit that a labelled step indicator is for a handful of
 * high-level sections and that it stops being readable past that, and an Iraqi
 * procedure has eight to twenty-two stops. So the rail draws the coarse
 * buckets, the fine step is named in prose beneath it, and the full list of
 * steps is available - to a screen reader, to a printer and to anyone who
 * actually wants it - inside a `<details>` table carrying the same figures.
 *
 * The rail is the proof of the whole angle this module is built on: it renders
 * whatever the payload contains, so a three-phase Chamber renewal and a
 * six-phase Registrar amendment use one component and one line of arch. That
 * only holds because the payload is composed on the server, by
 * `legal.case.progress_payload`, with every label already translated. There is
 * no phase list, no ordering rule and no status vocabulary in this file.
 *
 * The accessibility contract, also USWDS's and also non-negotiable: real
 * `<button>` segments so the rail is keyboard reachable, `aria-current="step"`
 * on the current phase, a visually-hidden status WORD beside every marker so
 * the rail reads without the tint, a `role="progressbar"` over the whole, and
 * pending segments that stay visible and legible rather than being styled as
 * disabled.
 */
export class LegalPhaseRail extends Component {
    static template = "legal_procedure.LegalPhaseRail";
    static props = {
        ...standardFieldProps,
        record: { type: Object, optional: true },
        name: { type: String, optional: true },
        payload: { type: Object, optional: true },
    };

    // Only literal _t() calls reach the .pot, so the labels live in a lookup.
    static labels = {
        done: _t("Done"),
        current: _t("In progress"),
        todo: _t("Not started"),
        blocked: _t("Blocked"),
        progress: _t("Progress through the procedure"),
        blockers: _t("Before this step can be completed:"),
        tableSummary: _t("Show the steps as a table"),
        phase: _t("Phase"),
        steps: _t("Steps"),
        status: _t("Status"),
        actor: _t("Who"),
        date: _t("When"),
        waitingOn: _t("Waiting on"),
        mine: _t("Waiting for you"),
        nowAt: _t("Now at"),
    };

    setup() {
        // Which phase the reader has asked about, if any. A segment is a
        // button precisely so that a keyboard user can reach the step names
        // under a phase they are not standing on; selecting one changes what
        // the prose beneath says and nothing else. No record is written and no
        // domain is composed - the rail is a renderer.
        this.state = useState({ selected: null });
    }

    get label() {
        return LegalPhaseRail.labels;
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

    get phases() {
        return this.payload.phases || [];
    }

    get blockers() {
        return this.payload.blockers || [];
    }

    /** The phase whose steps the prose beneath the rail is describing. */
    get focused() {
        const phases = this.phases;
        if (this.state.selected !== null) {
            const chosen = phases.find((phase) => phase.key === this.state.selected);
            if (chosen) {
                return chosen;
            }
        }
        return phases.find((phase) => phase.status === "current") || phases[0] || null;
    }

    select(phase) {
        this.state.selected = this.state.selected === phase.key ? null : phase.key;
    }

    /**
     * The status of a phase in words, for a reader who cannot see the tint and
     * for the screen reader that never could.
     */
    statusLabel(phase) {
        if (phase.status === "current" && this.blockers.length) {
            return LegalPhaseRail.labels.blocked;
        }
        return LegalPhaseRail.labels[phase.status] || "";
    }

    phaseClass(phase) {
        const blocked = phase.status === "current" && this.blockers.length;
        return [
            "o_legal_phase",
            `o_legal_phase_${phase.status}`,
            blocked ? "o_legal_phase_blocked" : "",
            this.state.selected === phase.key ? "o_legal_phase_selected" : "",
        ].filter(Boolean).join(" ");
    }
}

registry.category("fields").add("legal_phase_rail", {
    component: LegalPhaseRail,
    displayName: _t("Legal Phase Rail"),
    supportedTypes: ["json"],
    // The rail goes straight into the sheet rather than inside a <group>, so
    // it never inherits the width: 100% Odoo grants group descendants - inside
    // the seven-column grid it would render shrink-to-fit.
    additionalClasses: ["d-block", "w-100"],
    // A payload that ever came back empty would make the whole rail disappear
    // rather than render as an empty one, and a vanished rail reads as a bug
    // in the procedure rather than as an absence of data.
    isEmpty: () => false,
});
