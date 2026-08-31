import { Component, useState } from "@odoo/owl";

/**
 * The secondary strip: what is true, moving, and not yours to push today.
 *
 * One panel with a tab bar rather than three or four stacked panels, and the
 * reason is structural rather than aesthetic. Stacked panels grow: the day
 * somebody wants a fifth context list, a stack accepts it silently and the
 * first screen becomes three screens. A tab bar cannot absorb a fifth entry
 * without somebody noticing, which is exactly the pressure this region needs.
 *
 * Rows here are one line each and carry no state chip, no date and no action -
 * they are orientation. Anything that needs acting on belongs in the queue
 * above, and if it appears here instead that is a bug in the payload, not in
 * this component.
 */
export class LegalSecondary extends Component {
    static template = "legal_office.LegalSecondary";
    static props = {
        secondary: Object,
        onOpenRow: Function,
    };

    setup() {
        const tabs = this.props.secondary.tabs || [];
        this.state = useState({ active: tabs.length ? tabs[0].key : "" });
    }

    get tabs() {
        return this.props.secondary.tabs || [];
    }

    get current() {
        return this.tabs.find((tab) => tab.key === this.state.active) || this.tabs[0];
    }

    select(key) {
        this.state.active = key;
    }

    open(row) {
        if (row.open) {
            this.props.onOpenRow(row);
        }
    }
}
