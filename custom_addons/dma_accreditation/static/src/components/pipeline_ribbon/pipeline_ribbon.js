import { Component, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";

/**
 * Where the open caseload is sitting, as one segmented bar.
 *
 * A bar per step is the obvious form and the wrong one here: twelve bars of
 * one to three files each is twelve near-identical stubs, which is exactly
 * what the old board looked like. One bar whose segments are the steps makes
 * the *composition* the subject - which phase of the procedure holds the work -
 * and stays readable when every step holds a similar number.
 *
 * It is CSS, not a canvas. The segments have to be clickable, keyboard
 * reachable and labelled, they must mirror in Arabic, and they must survive
 * being printed. A canvas gives up all four to save nothing.
 *
 * `authorized` is deliberately not here. It is where files come to rest, so it
 * accumulates every organisation ever accredited and would swallow the bar.
 */
export class PipelineRibbon extends Component {
    static template = "dma_accreditation.PipelineRibbon";
    static props = {
        steps: { type: Array },
        total: { type: Number },
        withApplicant: { type: Number, optional: true },
        phases: { type: Array, optional: true },
        onOpen: { type: Function },
    };
    static defaultProps = { withApplicant: 0, phases: [] };

    static labels = {
        title: _t("Where the open caseload is"),
        inProcess: _t("files in process"),
        withApplicant: _t("with the applicant"),
        showTable: _t("Show the steps as a table"),
        step: _t("Step"),
        files: _t("Files"),
        share: _t("Share"),
        empty: _t("No file is in process."),
    };

    setup() {
        this.state = useState({ open: false });
    }

    get label() {
        return PipelineRibbon.labels;
    }

    /**
     * A step holding one file out of sixty is 1.6% of the bar - about four
     * pixels, too small to see and too small to click. Segments are widened to
     * a floor and the surplus taken back from the widest, so the bar still
     * sums to the whole and every step stays reachable.
     */
    get segments() {
        const shown = this.props.steps.filter((step) => step.count > 0);
        if (!shown.length) {
            return [];
        }
        const total = shown.reduce((sum, step) => sum + step.count, 0);
        const FLOOR = 4;
        const raw = shown.map((step) => ({
            ...step,
            width: (100 * step.count) / total,
        }));
        const owed = raw.reduce((sum, s) => sum + Math.max(0, FLOOR - s.width), 0);
        const spare = raw.reduce((sum, s) => sum + Math.max(0, s.width - FLOOR), 0);
        return raw.map((s) => ({
            ...s,
            width: s.width < FLOOR
                ? FLOOR
                : s.width - (spare ? (owed * (s.width - FLOOR)) / spare : 0),
        }));
    }

    toggle() {
        this.state.open = !this.state.open;
    }
}
