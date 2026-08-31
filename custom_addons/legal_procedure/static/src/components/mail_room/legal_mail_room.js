import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Layout } from "@web/search/layout";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";
import { _t } from "@web/core/l10n/translation";

import { LegalKpiTile } from "../kpi_tile/legal_kpi_tile";
import { LegalClockBadge } from "../clock_badge/legal_clock_badge";

/**
 * The Mail Room (غرفة البريد) - the module's default landing action.
 *
 * Three columns, and they are literally the shape of an Iraqi diwan clerk's
 * morning:
 *
 *   1. **وارد اليوم.** What arrived and belongs to no file yet. This column is
 *      the answer to the one gap a case-centred design cannot close: a tax
 *      assessment, a summons or an inspection notice arrives unprompted, with
 *      no file behind it, and it must be numbered the day it arrives. Two
 *      buttons per row and no more - attach it to a file, or open one from it.
 *   2. **بانتظار الرد.** What we have sent and are still chasing, oldest first,
 *      aged in the *body's* working days. Every row carries the reminder and
 *      the telephone note, because "I rang them and they said come back after
 *      Eid" is the commonest real event in this domain and a note that costs
 *      more than one click never gets written - after which the chase list
 *      starts lying and the clerk stops using it.
 *   3. **للإصدار.** What has to go out. The document meter and the twin
 *      buttons: the enabled primary when the file is ready, and its greyed
 *      twin - same label, same position - carrying the blocker summary as its
 *      title when it is not, so the next action stays visible while it is out
 *      of reach.
 *
 * ONE call fills the page. Three calls would let the browser draw three panels
 * computed a second apart in three different transactions, and every number,
 * colour, domain and Arabic sentence on the screen is composed on the server -
 * this component contains no business rule whatsoever, which is why the whole
 * of the logic is testable in Python.
 */
export class LegalMailRoom extends Component {
    static template = "legal_procedure.LegalMailRoom";
    // Bookmarkable at /odoo/legal-mailroom. The action record carries the
    // same path and wins where both are set; this is the fallback, and it
    // matters more in a ministry than it sounds - a manager sends the URL in
    // a message and it opens the screen rather than the application.
    static path = "legal-mailroom";
    static components = { Layout, LegalKpiTile, LegalClockBadge };
    static props = { ...standardActionServiceProps };

    // Only literal _t() calls reach the .pot, so the few strings the component
    // owns live in a lookup. The list is short on purpose: every button label,
    // every column heading and every empty-state sentence on this screen is
    // composed and translated on the server, so it cannot drift from the rule
    // that produced the row beneath it.
    static labels = {
        loading: _t("Loading the mail room…"),
        theirRef: _t("Their reference"),
        pickCase: _t("Which file does this belong to?"),
        degraded: _t("Some of this screen is not available yet:"),
    };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.dialog = useService("dialog");
        this.state = useState({ data: null, busy: false });

        onWillStart(() => this.load());
    }

    async load() {
        this.state.busy = true;
        try {
            this.state.data = await this.orm.call("legal.dashboard", "get_mail_room_data", []);
        } finally {
            this.state.busy = false;
        }
    }

    get label() {
        return LegalMailRoom.labels;
    }

    get data() {
        return this.state.data;
    }

    /**
     * Everything this screen opens, it opens with an action the server built.
     * The browser never composes a domain, so it can never compose one the
     * record rules would disagree with.
     */
    doAction(action) {
        if (action) {
            this.action.doAction(action);
        }
    }

    /** A KPI tile only becomes a button when the server gave it somewhere to go. */
    tileOpen(tile) {
        return tile.action ? () => this.doAction(tile.action) : undefined;
    }

    /**
     * Attaching an incoming entry to a file: the clerk picks the record in
     * Odoo's own selector, scoped by the server-supplied domain, and the write
     * happens on the server as the reader. The dialog is a UI mechanic; which
     * files are offered, and whether the write is allowed, are not.
     */
    attach(row) {
        if (!row.link) {
            return;
        }
        const SelectCreateDialog = registry.category("dialogs").get("select_create");
        this.dialog.add(SelectCreateDialog, {
            resModel: row.link.model,
            domain: row.link.domain,
            title: row.link.title || this.label.pickCase,
            noCreate: false,
            multiSelect: false,
            onSelected: async (resIds) => {
                if (!resIds || !resIds.length) {
                    return;
                }
                await this.orm.call("legal.dashboard", "link_correspondence", [], {
                    correspondence_id: row.id,
                    case_id: resIds[0],
                });
                await this.load();
            },
        });
    }

    /** The overflow behind a column's "open all" link. */
    overflow(column) {
        return column.overflow || 0;
    }
}

registry.category("actions").add("legal_mail_room", LegalMailRoom);
