import { Component, markup, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { _t } from "@web/core/l10n/translation";

import { LegalClockBadge } from "../clock_badge/legal_clock_badge";

/**
 * One government body's desk (مكتب الجهة).
 *
 * A panel, never a screen. A "Tax Commission dashboard" and a "Chamber of
 * Commerce dashboard" are the same layout with a different `body_id`, and
 * shipping them as two screens is precisely how a configurable module quietly
 * becomes twelve forked ones. So this component renders whatever sections the
 * payload carries, and their titles, hints and empty-state sentences come from
 * the step configuration rather than from a dictionary in Python or a string in
 * this file. Adding the General Commission for Taxes is data entry.
 *
 * What the panel shows above the sections is the part a case list cannot: the
 * body's opening hours, and its counter notes - «الطابق الثاني، شباك ٣، أحضر
 * نسختين». That note is the difference between a clerk who makes one journey
 * and a clerk who makes two, and it lives on the body record because it is a
 * fact about the body and not about any one file.
 *
 * Rows come in two shapes and no more, differing solely in what a row of that
 * kind has to show - a file, or a letter we are chasing.
 */
export class LegalBodyDesk extends Component {
    static template = "legal_procedure.LegalBodyDesk";
    static components = { LegalClockBadge };
    static props = {
        ...standardFieldProps,
        record: { type: Object, optional: true },
        name: { type: String, optional: true },
        // The panel is mounted twice: as a field widget on the body's own form,
        // where a manager configuring the Chamber sees exactly what a clerk
        // will get, and as a band of My Desk, where the payload is passed in.
        payload: { type: Object, optional: true },
        onOpenRecord: { type: Function, optional: true },
        onOpenAction: { type: Function, optional: true },
    };

    static labels = {
        openAll: _t("Open all"),
        outstanding: _t("outstanding"),
        clear: _t("Nothing outstanding"),
        hours: _t("Opening hours"),
        notes: _t("Which counter, which floor"),
        showNotes: _t("Counter notes"),
    };

    setup() {
        this.state = useState({ notes: false });
    }

    get label() {
        return LegalBodyDesk.labels;
    }

    get body() {
        if (this.props.payload) {
            return this.props.payload;
        }
        if (this.props.record && this.props.name) {
            return this.props.record.data[this.props.name] || {};
        }
        return {};
    }

    get sections() {
        return this.body.sections || [];
    }

    /**
     * The counter notes are `legal.gov.body.note`, a translated
     * `fields.Html`: the ORM sanitises it on every write, which is the one
     * and only reason it may be injected here. A string off JSON-RPC is not
     * an OWL Markup, so without this wrapper `t-out` escapes it and the
     * clerk reads literal `<p>` tags instead of the note.
     */
    get counterNotes() {
        return this.body.counter_notes ? markup(this.body.counter_notes) : "";
    }

    /** Rows a section is holding back behind its "open all" link. */
    overflow(section) {
        return Math.max(0, section.count - (section.rows || []).length);
    }

    /**
     * "N more", composed here rather than in the template.
     *
     * `_t` takes the literal msgid and substitutes afterwards, which is the
     * only form the .pot extractor sees: a sentence assembled from fragments
     * in markup reaches the translator as fragments, and Arabic cannot
     * reorder them.
     */
    moreLabel(section) {
        return _t("%s more", this.overflow(section));
    }

    /**
     * A section with nothing in it still renders, because "nothing to send to
     * the Tax Commission today" is the answer to the clerk's question and an
     * absent panel is not. What it does not do is take a whole card's height.
     */
    sectionClass(section) {
        return [
            "o_legal_body_section",
            `o_legal_body_${section.kind}`,
            (section.rows || []).length ? "" : "o_legal_body_clear",
        ].filter(Boolean).join(" ");
    }

    open(row) {
        if (this.props.onOpenRecord) {
            this.props.onOpenRecord(row);
        }
    }

    openSection(section) {
        if (this.props.onOpenAction && section.action) {
            this.props.onOpenAction(section.action);
        }
    }

    toggleNotes() {
        this.state.notes = !this.state.notes;
    }
}

registry.category("fields").add("legal_body_desk", {
    component: LegalBodyDesk,
    displayName: _t("Legal Body Desk"),
    supportedTypes: ["json"],
    additionalClasses: ["d-block", "w-100"],
    isEmpty: () => false,
});
