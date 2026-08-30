import { Component } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";

/**
 * What this department is for, and what it has to do right now.
 *
 * The desk above answers "how much is on me". This answers the two questions
 * that come straight after it and that a count cannot: what does this step
 * expect of me, and why can I not finish this particular file. Both answers
 * are composed on the server (see `dma_role_workspace.py`) and arrive already
 * translated, so this component never re-derives the state machine.
 *
 * It renders whatever sections the payload carries, and the three row shapes
 * differ only in what a row of that kind has to show: a file, a payment, or
 * one step signed by two departments at once. A department is added to the
 * product by adding a builder in Python - not a component here.
 */
export class DepartmentDesk extends Component {
    static template = "dma_accreditation.DepartmentDesk";
    static props = {
        brief: { type: Object },
        onOpenRecord: { type: Function },
        onOpenFee: { type: Function },
        onOpenSection: { type: Function },
        onNewRequest: { type: Function },
    };

    static labels = {
        title: _t("Your department"),
        newRequest: _t("New Accreditation Request"),
        openAll: _t("Open all"),
        more: _t("%s more"),
        atThisStep: _t("at this step"),
        urgent: _t("Urgent"),
        days: _t("d"),
        signed: _t("signed"),
        awaiting: _t("awaiting"),
        recentTitle: _t("What you last put through"),
        recentEmpty: _t("You have not recorded a decision yet."),
        receipt: _t("Receipt"),
        noReceipt: _t("No receipt number"),
        files: _t("Files"),
        outstanding: _t("outstanding"),
        nothing: _t("Nothing outstanding"),
    };

    get label() {
        return DepartmentDesk.labels;
    }

    /** Rows the section is holding back behind its "open all" link. */
    overflow(section) {
        return Math.max(0, section.count - section.rows.length);
    }

    /**
     * A section with nothing in it still renders, because "nothing to verify
     * today" is the answer to the officer's question and an absent panel is
     * not. What it does not do is take a whole card's worth of the page.
     */
    sectionClass(section) {
        return [
            "o_dma_dept_section",
            `o_dma_dept_${section.kind}`,
            section.rows.length ? "" : "o_dma_dept_clear",
        ].filter(Boolean).join(" ");
    }
}
