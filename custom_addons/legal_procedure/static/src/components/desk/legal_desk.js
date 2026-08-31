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
        retry: _t("Try again"),
        errorTitle: _t("Your desk could not be loaded."),
        errorHint: _t("The server could not be reached, or it reported an error. Nothing you did caused this."),
        noPermissionTitle: _t("You do not have permission to see this screen."),
        noPermissionHint: _t("Ask the legal manager for a role in the Legal Department."),
        reloadFailed: _t("The desk could not be refreshed, so it is showing what it already had."),
    };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({ data: null, busy: false, load: false, error: null });

        onWillStart(() => this.load());
    }

    /**
     * A caught load. The old version was try/finally with no catch, which
     * turned any failed RPC - including the AccessError the server correctly
     * re-raises for a reader who may not see a body's files - into an
     * eternal spinner plus an unhandled rejection. Now: a failure with no
     * data yet is a visible error state with a retry; a failure while data
     * is already on screen keeps the screen and says so in a notification.
     */
    async load() {
        this.state.busy = true;
        this.state.error = null;
        try {
            this.state.data = await this.orm.call("legal.dashboard", "get_desk_data", []);
        } catch (error) {
            if (this.state.data) {
                this.notification.add(this.label.reloadFailed, { type: "warning" });
            } else {
                this.state.error = this.describeError(error);
            }
        } finally {
            this.state.busy = false;
        }
    }

    /**
     * No-permission is not failure. The server refusing a read is the ORM
     * answering correctly, and the reader should be told so rather than
     * urged to retry a request that will refuse again - which is why the
     * permission variant carries no retry button.
     */
    describeError(error) {
        const name =
            (error && error.exceptionName) ||
            (error && error.data && error.data.name) ||
            "";
        const permission = name === "odoo.exceptions.AccessError";
        return {
            permission,
            title: permission ? this.label.noPermissionTitle : this.label.errorTitle,
            hint: permission ? this.label.noPermissionHint : this.label.errorHint,
        };
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
