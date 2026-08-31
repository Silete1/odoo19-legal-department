import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { _t } from "@web/core/l10n/translation";

/**
 * The runner's ordered stamp checklist (جولة المراجع).
 *
 * This is the screen that answers the twenty-two-counter براءة ذمة walk. Under
 * one step of the procedure sits an ordered list of windows: which floor,
 * which window, what to bring, what fee is payable there, and - the thing the
 * whole walk is actually about - which stamp that counter applies. The runner
 * needs to know two things at any moment, and no other screen in the module
 * tells them: which window am I at, and which stamp is still missing.
 *
 * Two facts about how this work really happens drive the shape.
 *
 * **Entry is retrospective and batched.** The expediter does not stand at
 * window seven with a laptop. He walks the building and enters six files at
 * 14:15 when he gets back. So ticks accumulate in local state and are saved
 * once, on one button, and nothing blocks on a network round trip per tick. A
 * widget that saved on every tick would be unusable on a government wifi and
 * would lose the afternoon's work at the first timeout.
 *
 * **Half of the domain is paper.** The same payload is printed as an A4 sheet
 * the runner carries, with blank boxes for the receipt numbers - which is why
 * the payload carries every string already composed rather than assembled in
 * this component: the sheet and the screen must say the same words.
 *
 * The ticks are written back through the record, so whatever guard the case
 * model puts on the write applies. This component decides nothing.
 */
export class LegalCounterWalk extends Component {
    static template = "legal_procedure.LegalCounterWalk";
    static props = {
        ...standardFieldProps,
        record: { type: Object, optional: true },
        name: { type: String, optional: true },
        payload: { type: Object, optional: true },
    };

    static labels = {
        title: _t("The counter walk"),
        empty: _t("This step has no counters configured."),
        emptyHint: _t("Add the windows to the step and they appear here in order, with the floor, what to bring and the stamp each one applies."),
        obtained: _t("Stamped"),
        pending: _t("Not yet"),
        next: _t("You are here"),
        bring: _t("Bring"),
        stamp: _t("Applies the stamp"),
        fee: _t("Fee"),
        receipt: _t("Receipt number"),
        save: _t("Save the ticks"),
        print: _t("Print the runner's sheet"),
    };

    setup() {
        // Pending ticks, by counter id. Kept here rather than written straight
        // through, because the runner enters a whole walk at once.
        this.state = useState({ pending: {} });
    }

    get label() {
        return LegalCounterWalk.labels;
    }

    get payload() {
        if (this.props.payload) {
            return this.props.payload;
        }
        if (this.props.record && this.props.name) {
            return this.props.record.data[this.props.name] || {};
        }
        return {};
    }

    get counters() {
        return this.payload.counters || [];
    }

    /** Ticked, counting what the reader has just ticked and not yet saved. */
    isObtained(counter) {
        const pending = this.state.pending[counter.id];
        return pending === undefined ? Boolean(counter.stamp_obtained) : pending;
    }

    get unsavedCount() {
        return Object.keys(this.state.pending).length;
    }

    /** How much this widget is holding, stated rather than implied. */
    get unsavedLabel() {
        return _t("%s tick(s) not saved yet", this.unsavedCount);
    }

    /**
     * The window the runner is standing at: the first that is not yet stamped.
     * Answering "where am I" is the whole point of an ordered list, and the
     * ordering is the server's - the component only reads it.
     */
    get currentId() {
        const next = this.counters.find((counter) => !this.isObtained(counter));
        return next ? next.id : null;
    }

    toggle(counter) {
        const now = !this.isObtained(counter);
        if (now === Boolean(counter.stamp_obtained)) {
            delete this.state.pending[counter.id];
        } else {
            this.state.pending[counter.id] = now;
        }
    }

    counterClass(counter) {
        return [
            "o_legal_counter",
            this.isObtained(counter) ? "o_legal_counter_done" : "o_legal_counter_todo",
            counter.id === this.currentId ? "o_legal_counter_here" : "",
            this.state.pending[counter.id] !== undefined ? "o_legal_counter_dirty" : "",
        ].filter(Boolean).join(" ");
    }

    /**
     * One save for the whole walk. The write goes through the record, so the
     * model's own guard on the field decides whether it is allowed - this
     * component only says which lines the runner ticked.
     */
    async save() {
        const record = this.props.record;
        if (!record || !this.props.name || !this.unsavedCount) {
            return;
        }
        const ticks = Object.entries(this.state.pending).map(([id, obtained]) => ({
            id: Number(id), stamp_obtained: obtained,
        }));
        const payload = { ...this.payload, ticks };
        await record.update({ [this.props.name]: payload });
        await record.save();
        this.state.pending = {};
    }
}

registry.category("fields").add("legal_counter_walk", {
    component: LegalCounterWalk,
    displayName: _t("Legal Counter Walk"),
    supportedTypes: ["json"],
    additionalClasses: ["d-block", "w-100"],
    isEmpty: () => false,
});
