import { Component } from "@odoo/owl";

/**
 * One number the reader can act on.
 *
 * A count with nothing behind it is a poster, so every tile is a way in to the
 * records it counts - and a tile reading zero stops being a button rather than
 * opening an empty list, because an empty list is a dead end and the reader has
 * to work out for themselves that nothing went wrong.
 *
 * `tone` is a STATUS - neutral, attention, critical - and never a series
 * colour. It never travels alone either: the template renders an icon and the
 * caption beside it, so the meaning survives a monochrome print, a photocopy
 * and a colour-blind reader. All three come composed from the server, which is
 * where the thresholds that decide them live.
 */
export class LegalKpiTile extends Component {
    static template = "legal_procedure.LegalKpiTile";
    static props = {
        label: { type: String },
        value: { type: [Number, String] },
        // The value already rendered in the company's numeral system. Kept
        // separate from `value` because the emptiness test below is arithmetic
        // and "٠" is not a number to JavaScript.
        valueLabel: { type: String, optional: true },
        hint: { type: String, optional: true },
        tone: { type: String, optional: true },
        icon: { type: String, optional: true },
        lead: { type: Boolean, optional: true },
        onOpen: { type: Function, optional: true },
    };
    static defaultProps = { tone: "neutral", lead: false, hint: "", icon: "", valueLabel: "" };

    get displayValue() {
        return this.props.valueLabel || String(this.props.value);
    }

    get clickable() {
        return Boolean(this.props.onOpen) && Number(this.props.value) !== 0;
    }

    onClick() {
        if (this.clickable) {
            this.props.onOpen();
        }
    }

    /**
     * A div carrying role="button" has to answer the keyboard itself. Written
     * as a method rather than inline because the OWL template compiler takes an
     * expression, not a statement block.
     */
    onKeydown(ev) {
        if (ev.key === "Enter" || ev.key === " ") {
            ev.preventDefault();
            this.onClick();
        }
    }
}
