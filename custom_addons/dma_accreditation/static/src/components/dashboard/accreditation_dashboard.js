import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Layout } from "@web/search/layout";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";
import { _t } from "@web/core/l10n/translation";

/**
 * Department dashboard for the Directorate.
 *
 * Every number comes from `dma.accreditation.request.get_dashboard_data`, so
 * the queue definitions live next to the ones the menus and the "My Turn"
 * filter use, and the record rules are applied by the server.
 */
export class AccreditationDashboard extends Component {
    static template = "dma_accreditation.AccreditationDashboard";
    static components = { Layout };
    static props = { ...standardActionServiceProps };

    static labels = {
        myTurn: _t("Waiting for me"),
        inProgress: _t("In progress"),
        authorized: _t("Accredited"),
        returned: _t("Returned"),
        rejected: _t("Rejected"),
        needsYou: _t("Needs your action"),
        allClear: _t("Nothing needs your action right now."),
        waiting: _t("waiting"),
        urgent: _t("Urgent"),
        queues: _t("Department queues"),
        queuesHint: _t("Everything at your department's steps, including files a colleague already signed."),
        pipeline: _t("Files by step"),
        expiring: _t("Accreditations expiring"),
        noExpiring: _t("No accreditation expires in the next 90 days."),
        open: _t("Open"),
        empty: _t("Nothing here"),
    };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ data: null });
        onWillStart(async () => {
            this.state.data = await this.orm.call(
                "dma.accreditation.request", "get_dashboard_data", []
            );
        });
    }

    get label() {
        return AccreditationDashboard.labels;
    }

    get data() {
        return this.state.data;
    }

    /** Drill through to the matching list of requests. */
    openRequests(title, domain) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: title,
            res_model: "dma.accreditation.request",
            views: [[false, "list"], [false, "form"]],
            domain: domain,
            target: "current",
        });
    }

    openMyTurn() {
        this.openRequests(this.label.myTurn, [["is_my_turn", "=", true]]);
    }

    openRecord(resId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "dma.accreditation.request",
            res_id: resId,
            views: [[false, "form"]],
            target: "current",
        });
    }
}

registry.category("actions").add("dma_accreditation_dashboard", AccreditationDashboard);
