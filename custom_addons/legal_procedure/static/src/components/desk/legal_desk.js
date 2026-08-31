import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Layout } from "@web/search/layout";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";
import { _t } from "@web/core/l10n/translation";

import { LegalBodyDesk } from "../body_desk/legal_body_desk";

/**
 * مكاتب الجهات - Government Desks.
 *
 * The landing screen مكتبي used to be this component, and it used to carry
 * seven bands: a hero count, three tiles, a file worklist, an approvals queue,
 * an audit trail, the government bodies, a manager band and - below all of
 * that - the same government bodies a second time. It was the first screen a
 * clerk saw, it was three viewports tall before it reached anything they
 * owned, and its most useful content was the part furthest down.
 *
 * That content is what remains. `legal_office` now owns *what requires my
 * action now*, which is what the top of this screen was trying and failing to
 * be, so this one keeps only the question it was uniquely able to answer:
 *
 *   **What does each counter want, and when is it open?**
 *
 * One panel per government body the reader deals with - what we owe them, what
 * is lodged with them, what we are waiting on - with the opening hours and the
 * counter notes a runner actually needs before crossing Baghdad. It is
 * reference material, and reference material belongs one click away from the
 * work rather than on top of it.
 *
 * The payload is `get_body_desk_data`, not the older `get_desk_data`: the
 * bands this screen no longer draws are queries it no longer runs.
 */
export class LegalDesk extends Component {
    static template = "legal_procedure.LegalDesk";
    // Its own URL. /odoo/legal-desk stays with مكتبي, which is where anybody
    // following an old link expected to land.
    static path = "gov-desks";
    static components = { Layout, LegalBodyDesk };
    static props = { ...standardActionServiceProps };

    static labels = {
        loading: _t("Loading the bodies' desks…"),
        noBodies: _t("You are not on any body's follow-up list."),
        noBodiesHint: _t("A manager adds you to a body's follow-up officers, and that body's desk appears here with its opening hours and its counter notes."),
        retry: _t("Try again"),
        errorTitle: _t("The bodies' desks could not be loaded."),
        errorHint: _t("The server could not be reached, or it reported an error. Nothing you did caused this."),
        noPermissionTitle: _t("You do not have permission to see this screen."),
        noPermissionHint: _t("Ask the legal manager for a role in the Legal Department."),
        reloadFailed: _t("The screen could not be refreshed, so it is showing what it already had."),
    };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({ data: null, busy: false, error: null });

        // Reached through its own URL rather than through the menu, a client
        // action arrives with no display name and Odoo breadcrumbs it as
        // "Untitled" - which is what this screen showed for its whole life as
        // the landing page.
        if (this.env.config && this.env.config.setDisplayName) {
            this.env.config.setDisplayName(
                this.props.action.name || _t("Government Desks"));
        }

        onWillStart(() => this.load());
    }

    /**
     * A caught load. A failure with no data yet is a visible error state with
     * a retry; a failure while data is already on screen keeps the screen and
     * says so. An AccessError is a correct answer rather than a defect, so its
     * variant carries no retry - the server will answer the same again.
     */
    async load() {
        this.state.busy = true;
        this.state.error = null;
        try {
            this.state.data = await this.orm.call(
                "legal.dashboard", "get_body_desk_data", []);
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

    openRecord(row) {
        this.doAction(row.open);
    }
}

registry.category("actions").add("legal_desk", LegalDesk);
