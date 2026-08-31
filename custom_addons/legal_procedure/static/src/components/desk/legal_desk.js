import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Layout } from "@web/search/layout";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";
import { _t } from "@web/core/l10n/translation";

import { LegalKpiTile } from "../kpi_tile/legal_kpi_tile";
import { LegalWorklist } from "../worklist/legal_worklist";
import { LegalBodyDesk } from "../body_desk/legal_body_desk";

/**
 * My Desk (طاولتي).
 *
 * ONE client action for the clerk, the approver and the legal manager - not
 * one each. The three roles differ in *which slice* of a single procedure they
 * own, not in kind: they read the same rows, need the same two ages and act on
 * the same files. And the manager holds every role at once, which three
 * separate screens could not represent at all. So the payload changes - the
 * server sets `role.landing_band` and the first band leads with the approval
 * queue instead of the file queue - and this component does not.
 *
 * Three bands, and the order is the argument:
 *
 *   **A - طاولتي.** The hero count, three tiles, and the worklist. What is on
 *   this reader, right now, in the order to open it.
 *
 *   **B - مكاتب الجهات.** One panel per body the reader deals with, drawn from
 *   the same payload. It answers the question the desk above cannot: not "how
 *   much is on me" but "what does this counter want, and when is it open".
 *
 *   **C - الحِمل.** Context. A clerk opening the application to a report has to
 *   scroll past it to reach their own three files, so for a non-manager it is
 *   behind a disclosure and for a manager it is open - the manager's screen is
 *   the caseload, and they still have files of their own above it.
 */
export class LegalDesk extends Component {
    static template = "legal_procedure.LegalDesk";
    // Bookmarkable at /odoo/legal-desk.
    static path = "legal-desk";
    static components = { Layout, LegalKpiTile, LegalWorklist, LegalBodyDesk };
    static props = { ...standardActionServiceProps };

    // Only literal _t() calls reach the .pot.
    static labels = {
        loading: _t("Loading your desk…"),
        deskBand: _t("Your desk"),
        bodiesBand: _t("The bodies' desks"),
        loadBand: _t("The caseload"),
        showLoad: _t("Show the department figures"),
        hideLoad: _t("Hide the department figures"),
        noBodies: _t("You are not on any body's follow-up list."),
        noBodiesHint: _t("A manager adds you to a body's follow-up officers, and that body's desk appears here with its opening hours and its counter notes."),
        degraded: _t("Some of this screen is not available yet:"),
    };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ data: null, busy: false, load: false });

        onWillStart(() => this.load());
    }

    async load() {
        this.state.busy = true;
        try {
            this.state.data = await this.orm.call("legal.dashboard", "get_desk_data", []);
        } finally {
            this.state.busy = false;
        }
    }

    get label() {
        return LegalDesk.labels;
    }

    get data() {
        return this.state.data;
    }

    doAction(action) {
        if (action) {
            this.action.doAction(action);
        }
    }

    tileOpen(tile) {
        return tile.action ? () => this.doAction(tile.action) : undefined;
    }

    openRecord(row) {
        this.doAction(row.open);
    }

    /**
     * The department-wide figures are the manager's screen and are open for
     * them by default. Everyone else gets them on request: a clerk who has to
     * scroll past a report to reach their own three files stops opening the
     * application at all.
     */
    get showsLoad() {
        return Boolean(this.data && this.data.role.is_manager) || this.state.load;
    }

    toggleLoad() {
        this.state.load = !this.state.load;
    }
}

registry.category("actions").add("legal_desk", LegalDesk);
