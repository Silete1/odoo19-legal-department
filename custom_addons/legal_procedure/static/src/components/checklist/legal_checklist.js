import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
 * The required documents (المستمسكات), in GOV.UK task-list anatomy.
 *
 * Three things in that anatomy are the result of research rather than taste,
 * and all three are implemented here exactly:
 *
 *   * **the whole row is the link.** GOV.UK's own users, given a row whose name
 *     alone was clickable, mistook the status tag beside it for a second
 *     button. This row has a status tag, an expiry chip and a register badge on
 *     it, so the mistake would be three times as easy;
 *   * **sentence case, never upper.** The 2023 iteration dropped the shouting,
 *     and Arabic has no case at all, so an upper-cased vocabulary would have
 *     been a Latin-only decoration;
 *   * **a one-line hint per row.** Not what the document is - the clerk knows -
 *     but what the *counter* will accept: «أصل + نسخة، مختومة من غرفة التجارة».
 *     That sentence is configuration on the requirement, and it is the single
 *     most useful string on the screen.
 *
 * The status vocabulary is a CLOSED set of seven values, decided on the server
 * and pinned there: غير مطلوب / لم يُقدَّم / مُقدَّم / قيد التدقيق / مقبول /
 * مرفوض / منتهي الصلاحية. An eighth would be a migration, not an edit. This
 * component maps a code to a class and an icon and never to a word - the word
 * arrives translated in the payload, because a status is a business fact.
 *
 * Two behaviours are the ones that earn the widget its existence.
 *
 * **Freshness is not expiry.** A supporting letter can be demanded to have been
 * *issued* within a window whether or not it carries an expiry date at all, so
 * a row can be "expired" for either of two reasons and the hint says which.
 *
 * **The prerequisite chain.** Where a missing requirement is itself produced by
 * another procedure, the row carries the button that opens that procedure. That
 * one button is how "the Registrar refuses a filing without tax and social
 * security clearance letters" becomes three configuration records instead of
 * code.
 */
export class LegalChecklist extends Component {
    static template = "legal_procedure.LegalChecklist";
    static props = {
        ...standardFieldProps,
        record: { type: Object, optional: true },
        name: { type: String, optional: true },
        payload: { type: Object, optional: true },
        compact: { type: Boolean, optional: true },
    };
    static defaultProps = { compact: false };

    // Only literal _t() calls reach the .pot, so the strings the component
    // owns - never a status word, which is the server's - live in a lookup.
    static labels = {
        title: _t("Required documents"),
        empty: _t("This procedure asks for no documents."),
        emptyHint: _t("Requirements appear here as soon as the procedure type lists them."),
        fromRegister: _t("Taken from the company register"),
        fromRegisterHelp: _t("This line is already satisfied by a document held in the company's permanent register. Nothing needs to be uploaded here."),
        openProducer: _t("Start the procedure that issues it"),
        openDocument: _t("Open the document"),
        blockers: _t("Holding this file up:"),
        counter: _t("Provided"),
        authenticity: _t("The counter wants"),
    };

    // Status code to shape. The WORD is never here: it arrives translated in
    // the payload, because the vocabulary is a business fact with a migration
    // attached to it, not a presentation detail.
    static icons = {
        not_required: "fa-minus-circle",
        not_submitted: "fa-circle-o",
        submitted: "fa-upload",
        under_review: "fa-hourglass-half",
        accepted: "fa-check-circle",
        rejected: "fa-times-circle",
        expired: "fa-calendar-times-o",
    };

    setup() {
        this.action = useService("action");
        // A requirement list of eighteen headings is a table of contents, not a
        // wall, so only the sections the server marks open start open.
        this.state = useState({ closed: {} });
    }

    get label() {
        return LegalChecklist.labels;
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

    get sections() {
        return this.payload.sections || [];
    }

    get blockers() {
        return this.payload.blockers || [];
    }

    isOpen(section) {
        const override = this.state.closed[section.key];
        return override === undefined ? section.open_by_default !== false : !override;
    }

    toggle(section) {
        this.state.closed[section.key] = this.isOpen(section);
    }

    icon(row) {
        return LegalChecklist.icons[row.status] || "fa-circle-o";
    }

    rowClass(row) {
        return [
            "o_legal_check_row",
            `o_legal_check_${row.status}`,
            row.required ? "o_legal_check_required" : "",
        ].filter(Boolean).join(" ");
    }

    /**
     * Opening a row does whatever the server said opening it does - view the
     * held document, or start the procedure that produces it. The component
     * never composes an action of its own; it fires the one in the payload.
     */
    open(action) {
        if (action) {
            this.action.doAction(action);
        }
    }
}

registry.category("fields").add("legal_checklist", {
    component: LegalChecklist,
    displayName: _t("Legal Document Checklist"),
    supportedTypes: ["json"],
    supportedOptions: [
        {
            label: _t("Compact"),
            name: "compact",
            type: "boolean",
            help: _t("Hide the hints and the section headings."),
        },
    ],
    extractProps: ({ options }) => ({ compact: Boolean(options.compact) }),
    additionalClasses: ["d-block", "w-100"],
    isEmpty: () => false,
});
