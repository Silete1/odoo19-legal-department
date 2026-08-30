import { Component } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";

/**
 * The files on the reader's desk, in the order they should be opened.
 *
 * This is the one panel an officer uses every day, so it carries two ages,
 * because they answer different questions. Time at this step says whose desk
 * is blocked. Time since submission is what the applicant actually
 * experiences, and unlike the first it does not reset every time a file is
 * passed along - a request bounced four times looks fresh by the first measure
 * and is four months old by the second.
 *
 * The meter beside each row is a display scale capped at a fortnight, not a
 * deadline: the Directorate has never agreed a table of per-step targets, so
 * the exact number of days always sits next to the bar and the word "target"
 * appears nowhere.
 */
export class ActionWorklist extends Component {
    static template = "dma_accreditation.ActionWorklist";
    static props = {
        files: { type: Array },
        total: { type: Number },
        onOpenRecord: { type: Function },
        onOpenAll: { type: Function },
    };

    static labels = {
        title: _t("Needs your action"),
        empty: _t("Nothing is waiting for you."),
        emptyHint: _t("Files appear here the moment they reach a step your department owns."),
        urgent: _t("Urgent"),
        atStep: _t("at this step"),
        sinceSubmission: _t("since submission"),
        openAll: _t("Open all my files"),
        days: _t("d"),
        blocked: _t("Blocked"),
    };

    get label() {
        return ActionWorklist.labels;
    }

    /** How many rows are hidden behind the "open all" link. */
    get overflow() {
        return Math.max(0, this.props.total - this.props.files.length);
    }
}
