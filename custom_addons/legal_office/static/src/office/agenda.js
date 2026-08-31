import { Component } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";

/**
 * The agenda - a day-grouped rail, deliberately not a calendar.
 *
 * A month grid is the wrong instrument for the question "what is coming".
 * It spends most of its pixels on empty squares, it hides the ordering that
 * matters - what is first - inside a two-dimensional layout, and at the width
 * available beside the queue it is illegible. A rail grouped by *when* -
 * overdue, today, tomorrow, this week, later - reads top to bottom in the
 * order the reader will meet the events, and it costs one line per event.
 *
 * The full calendar is one click away on the deadline board, which is where a
 * calendar earns its space.
 *
 * Every row here is a projection of a real record on the ``legal.deadline``
 * union view, so clicking one opens the obligation, the hearing or the
 * contract itself rather than a copy of it.
 */
export class LegalAgenda extends Component {
    static template = "legal_office.LegalAgenda";
    static props = {
        agenda: Object,
        onOpenRow: Function,
        onOpenAction: Function,
    };

    static labels = {
        board: _t("Open the deadline board"),
        unowned: _t("No owner"),
    };

    get label() {
        return LegalAgenda.labels;
    }

    open(row) {
        if (row.open) {
            this.props.onOpenRow(row);
        }
    }
}
