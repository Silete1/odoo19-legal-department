import { Component, useRef, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";

/**
 * The work queue - the visual centre of My Office.
 *
 * A table, not cards. Twelve matters as twelve cards is a wall; twelve matters
 * as twelve rows is a list you can read in one downward sweep, compare across,
 * and act on from the keyboard. The columns are fixed at six because a seventh
 * is a column somebody stops reading:
 *
 *   1. a state spine and the kind icon - what sort of thing this is;
 *   2. the reference, pinned ``dir="ltr"`` and set in tabular figures so the
 *      column aligns and the bidi algorithm cannot reorder ``2026/0498/ق``;
 *   3. the subject, the largest type on the screen, truncated not wrapped so
 *      every row is the same height and the eye can travel straight down;
 *   4. where it stands;
 *   5. *why it is here* - the column that makes the screen worth opening;
 *   6. when it bites.
 *
 * The scope chips filter what is already loaded rather than asking the server
 * again: the server sent the whole queue, the counts are exact, and a filter
 * that costs a round trip is a filter people stop using.
 *
 * Keyboard: ArrowUp/ArrowDown move, Enter and Space open, Home and End jump.
 * A legal clerk works this list forty times a day and should not have to use
 * the mouse to do it.
 */
export class LegalWorkQueue extends Component {
    static template = "legal_office.LegalWorkQueue";
    static props = {
        queue: Object,
        readOnly: { type: Boolean, optional: true },
        onOpenRow: Function,
    };

    static labels = {
        why: _t("Why"),
        reference: _t("Reference"),
        subject: _t("Subject"),
        state: _t("Stands at"),
        due: _t("Due"),
        owner: _t("Owner"),
        openAll: _t("Open the full list"),
        urgent: _t("Urgent"),
        moreAbove: _t("Showing the first rows; the rest are in the list view."),
    };

    setup() {
        this.state = useState({ scope: "all", active: -1 });
        this.tableRef = useRef("table");
    }

    get label() {
        return LegalWorkQueue.labels;
    }

    get rows() {
        const rows = this.props.queue.rows || [];
        if (this.state.scope === "all") {
            return rows;
        }
        return rows.filter((row) => row.kind === this.state.scope);
    }

    setScope(key) {
        this.state.scope = key;
        this.state.active = -1;
    }

    isScope(key) {
        return this.state.scope === key;
    }

    open(row) {
        this.props.onOpenRow(row);
    }

    /**
     * Roving focus over the rows. The active index is kept in state rather
     * than read back off the DOM so that a re-render - a scope change, a
     * refresh - cannot leave the highlight pointing at a row that has gone.
     */
    onKeydown(event) {
        const rows = this.rows;
        if (!rows.length) {
            return;
        }
        const move = (next) => {
            event.preventDefault();
            this.state.active = Math.max(0, Math.min(rows.length - 1, next));
            const table = this.tableRef.el;
            const target = table && table.querySelectorAll(".o_legal_queue__row")[this.state.active];
            if (target) {
                target.focus();
            }
        };
        switch (event.key) {
            case "ArrowDown":
                return move(this.state.active + 1);
            case "ArrowUp":
                return move(this.state.active - 1);
            case "Home":
                return move(0);
            case "End":
                return move(rows.length - 1);
            case "Enter":
            case " ":
                if (this.state.active >= 0) {
                    event.preventDefault();
                    this.open(rows[this.state.active]);
                }
                return undefined;
            default:
                return undefined;
        }
    }

    onRowFocus(index) {
        this.state.active = index;
    }
}
