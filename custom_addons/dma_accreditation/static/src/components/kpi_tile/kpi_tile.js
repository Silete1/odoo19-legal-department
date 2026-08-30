import { Component } from "@odoo/owl";

/**
 * One number the reader can act on.
 *
 * Every tile is a button, because a count with nothing behind it is a poster.
 * `tone` is a *status*, never a series colour, and it never travels alone: the
 * template renders an icon and the caption beside it, so the meaning survives
 * a monochrome print and a colour-blind reader.
 */
export class KpiTile extends Component {
    static template = "dma_accreditation.KpiTile";
    static props = {
        label: { type: String },
        value: { type: [Number, String] },
        hint: { type: String, optional: true },
        tone: { type: String, optional: true },   // neutral | attention | critical
        icon: { type: String, optional: true },
        lead: { type: Boolean, optional: true },
        onOpen: { type: Function, optional: true },
    };
    static defaultProps = { tone: "neutral", lead: false, hint: "", icon: "" };

    get clickable() {
        // A tile reading zero opens an empty list, which is a dead end. It
        // stays legible and stops being a button.
        return Boolean(this.props.onOpen) && Number(this.props.value) !== 0;
    }

    onClick() {
        if (this.clickable) {
            this.props.onOpen();
        }
    }

    /**
     * A div carrying role="button" has to answer the keyboard itself.
     * Written as a method rather than inline: the OWL template compiler takes
     * an expression, not a statement block.
     */
    onKeydown(ev) {
        if (ev.key === "Enter" || ev.key === " ") {
            ev.preventDefault();
            this.onClick();
        }
    }
}
