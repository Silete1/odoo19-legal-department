import { Component, useRef, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";

/**
 * The work queue - the visual centre of مكتبي.
 *
 * A table, not cards. Twelve matters as twelve cards is a wall; twelve matters
 * as twelve rows is a list you can read in one downward sweep, compare across,
 * and act on from the keyboard.
 *
 * **Rows are grouped into focus bands, not sorted into one flat list.** This is
 * the mechanic Linear's My Issues uses and the reason that screen is readable
 * at a glance: assigned work is "grouped in a focus order such as urgent work,
 * SLA-bound work, blockers ... some sections only appear when they apply", and
 * within a band the ordering is by priority. A flat list ordered by the same
 * key carries the same information and hides it - the reader has to parse a
 * date column to discover where "overdue" stops and "this week" begins.
 *
 * The bands here are the server's own `bucket`, which already decides that
 * ordering; this component only draws the boundaries the server had implied.
 * No row moves, no row is filtered, nothing is recomputed - regrouping is
 * presentation, and the payload is unchanged.
 *
 * Six columns, fixed, because a seventh is a column somebody stops reading:
 *
 *   1. the register icon - what sort of thing this is;
 *   2. the reference, pinned ``dir="ltr"`` in tabular figures so the column
 *      aligns and the bidi algorithm cannot reorder ``2026/0498/ق``;
 *   3. the subject - the dominant type on the screen;
 *   4. where it stands, as a small semantic dot and word;
 *   5. *why it is here*, plain text - the column that makes the screen worth
 *      opening;
 *   6. when it bites, emphasised only when it already has.
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

    // The focus bands, in the order the server's own bucket numbers them. A
    // band with nothing in it is never drawn, so a clear week costs no height.
    static bands = [
        { bucket: 0, label: _t("Overdue"), tone: "critical" },
        { bucket: 1, label: _t("Today"), tone: "critical" },
        { bucket: 2, label: _t("Within the week"), tone: "warning" },
        { bucket: 3, label: _t("Later"), tone: "neutral" },
        { bucket: 4, label: _t("No date"), tone: "neutral" },
    ];

    setup() {
        this.state = useState({ scope: "all", active: -1 });
        this.tableRef = useRef("table");
    }

    get label() {
        return LegalWorkQueue.labels;
    }

    /** The rows the current scope shows, in payload order. */
    get rows() {
        const rows = this.props.queue.rows || [];
        if (this.state.scope === "all") {
            return rows;
        }
        return rows.filter((row) => row.kind === this.state.scope);
    }

    /**
     * The rows in the order they are actually painted.
     *
     * The keyboard walk indexes into this rather than into `rows`, because
     * `querySelectorAll` returns DOM order and only this getter is guaranteed
     * to match it. The two happen to agree while the payload arrives sorted by
     * bucket - but a walk that silently depends on that would break the day
     * the server's ordering changed, and break by selecting the wrong record.
     */
    get flatRows() {
        return this.bands.flatMap((band) => band.rows.map((entry) => entry.row));
    }

    /**
     * The same rows, cut into bands.
     *
     * Each row keeps a flat `index` so the keyboard walk crosses band
     * boundaries without the caller having to know the bands exist.
     */
    get bands() {
        const out = [];
        let index = 0;
        for (const band of LegalWorkQueue.bands) {
            const rows = this.rows.filter((row) => row.bucket === band.bucket);
            if (!rows.length) {
                continue;
            }
            out.push({
                ...band,
                label: band.label.toString(),
                rows: rows.map((row) => ({ row, index: index++ })),
                count: rows.length,
            });
        }
        return out;
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
        const rows = this.flatRows;
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
