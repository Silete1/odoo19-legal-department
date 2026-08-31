import { Component } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";

import { LegalClockBadge } from "../clock_badge/legal_clock_badge";

/**
 * The files on the reader's desk, in the order they should be opened.
 *
 * This is the one panel a clerk uses every day, so it carries TWO ages,
 * because they answer different questions and only one of them is on the
 * clerk's conscience.
 *
 *   * **Days at this step** says whose desk is blocked. It resets every time
 *     the file is handed on, which is exactly right for the question "what
 *     should I open next".
 *   * **Days since the file was opened** is what the company actually
 *     experiences, and it does NOT reset when a file moves from the Tax
 *     Commission to the Chamber of Commerce. A file bounced four times looks
 *     fresh by the first measure and is four months old by the second, and a
 *     desk that shows only the first is quietly lying to the general manager.
 *
 * Both are counted in the body's working days on the server, through its
 * `resource.calendar`, because an office that closes Friday and Saturday makes
 * "ten days" and "ten working days" two different facts and only the second is
 * the one the counter clerk would recognise.
 *
 * The meter beside each row is a display scale capped at a fortnight, not a
 * deadline: no Iraqi body publishes per-step targets, so the exact figure sits
 * next to the bar and the word "target" appears nowhere in this component.
 */
export class LegalWorklist extends Component {
    static template = "legal_procedure.LegalWorklist";
    static components = { LegalClockBadge };
    static props = {
        title: { type: String },
        hint: { type: String, optional: true },
        empty: { type: String },
        emptyHint: { type: String, optional: true },
        files: { type: Array },
        total: { type: Number },
        onOpenRecord: { type: Function },
        onOpenAll: { type: Function, optional: true },
    };
    static defaultProps = { hint: "", emptyHint: "" };

    // Only literal _t() calls reach the .pot, so the strings the component
    // owns - as opposed to the ones the payload carries - live in a lookup.
    static labels = {
        atThisStep: _t("at this step"),
        sinceOpened: _t("since the file was opened"),
        openAll: _t("Open all my files"),
        urgent: _t("Urgent"),
        blocked: _t("Blocked"),
        ages: _t("Two ages: at this step, and since the file was opened."),
    };

    get label() {
        return LegalWorklist.labels;
    }

    /** How many rows are hidden behind the "open all" link. */
    get overflow() {
        return Math.max(0, this.props.total - this.props.files.length);
    }
}
