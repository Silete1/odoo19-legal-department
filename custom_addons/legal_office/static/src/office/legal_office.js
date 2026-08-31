import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Layout } from "@web/search/layout";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";
import { _t } from "@web/core/l10n/translation";

import { LegalWorkQueue } from "./work_queue";
import { LegalAgenda } from "./agenda";
import { LegalSecondary } from "./secondary";

/**
 * مكتبي - My Desk.
 *
 * The application's first screen, redesigned in place: this component replaces
 * what `legal_procedure.action_legal_desk` renders, so the menu entry, the
 * name and the /odoo/legal-desk URL people already use are all unchanged.
 *
 * It answers exactly one question:
 * *what requires my action now.* Everything on it is either a thing to do, the
 * date a thing becomes late, or the reason a thing is here. Nothing on it is a
 * figure to admire.
 *
 * The layout is three zones and their order is the argument:
 *
 *   **The rail.** Three to five indicators on one line, each a filtered list
 *   behind a number. It is one line - not five cards - because it is a status
 *   bar, and a status bar that occupies a third of the screen has stopped
 *   being one.
 *
 *   **The queue and the agenda, side by side.** The queue is the visual
 *   centre and takes roughly two thirds of the width; the agenda is the
 *   narrow column beside it. The two answer different questions - *what is on
 *   me* and *what is coming* - and a reader who has to scroll between them
 *   cannot plan the day.
 *
 *   **The secondary strip.** Context, behind tabs, below the fold on a small
 *   screen and never above the work.
 *
 * The reader's own chrome is deliberately absent: no hero, no welcome, no
 * giant numeral. The largest type on this screen is the subject line of the
 * top row of the queue, which is the thing the reader came to read.
 *
 * There is no client-side business logic. The role decides the payload on the
 * server and the component renders whatever it is handed, so a screen the
 * server would not authorise cannot be produced by editing the markup.
 */
export class LegalOffice extends Component {
    static template = "legal_office.LegalOffice";
    // No `static path`: this component is mounted by
    // `legal_procedure.action_legal_desk`, whose own `path` field owns
    // /odoo/legal-desk. A second path here would publish the same screen at
    // two URLs and make one of them the wrong one to send to a colleague.
    static components = {
        Layout, Dropdown, DropdownItem, LegalWorkQueue, LegalAgenda, LegalSecondary,
    };
    static props = { ...standardActionServiceProps };

    // Only literal _t() calls are collected into the .pot, so every string the
    // component owns is declared here rather than built at the call site.
    static labels = {
        loading: _t("Opening your office…"),
        create: _t("New"),
        errorTitle: _t("Your office could not be loaded."),
        errorHint: _t("The server could not be reached, or it reported an error. Nothing you did caused this."),
        permissionTitle: _t("You do not have permission to open this screen."),
        permissionHint: _t("Ask the legal manager for a role in the Legal Department."),
        retry: _t("Try again"),
        reloadFailed: _t("Could not refresh, so the screen is showing what it already had."),
        refresh: _t("Refresh"),
        degraded: _t("Part of this screen is unavailable:"),
        readOnly: _t("Read-only"),
    };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({ data: null, busy: false, error: null });

        // Reached through its own URL rather than through the menu, a client
        // action arrives with no display name and Odoo breadcrumbs it as
        // "Untitled". Naming it here fixes the breadcrumb and the browser tab
        // for the bookmarked case, which is the case the `path` exists for.
        if (this.env.config && this.env.config.setDisplayName) {
            this.env.config.setDisplayName(this.props.action.name || _t("My Desk"));
        }

        onWillStart(() => this.load());
    }

    /**
     * A caught load with three distinct outcomes, because they need three
     * different responses. A refusal is an answer and offers no retry; a
     * failure with nothing on screen is an error state that does; a failure
     * while the screen already holds data keeps the data and says so quietly,
     * because throwing away a working screen to report a transient failure is
     * the worse of the two outcomes.
     */
    async load() {
        this.state.busy = true;
        this.state.error = null;
        try {
            this.state.data = await this.orm.call("legal.office", "get_office_data", []);
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
            title: permission ? this.label.permissionTitle : this.label.errorTitle,
            hint: permission ? this.label.permissionHint : this.label.errorHint,
        };
    }

    get label() {
        return LegalOffice.labels;
    }

    get data() {
        return this.state.data;
    }

    doAction(action) {
        if (action) {
            this.action.doAction(action);
        }
    }

    onOpenRow(row) {
        this.doAction(row && row.open);
    }
}

registry.category("actions").add("legal_office", LegalOffice);
