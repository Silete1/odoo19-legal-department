import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { _t } from "@web/core/l10n/translation";

/**
 * Reads the `dossier_payload` Json field of dma.accreditation.request and
 * draws the complete evidence file: what is in it, what is missing, which
 * version of each document is current, and the decision trail underneath.
 *
 * The index itself is built on the server (`_dossier_index`) and is the very
 * same structure the printed cover sheet and the downloadable archive are
 * built from, so the three can never disagree about what the dossier holds.
 * This component adds no knowledge of its own: it lays the structure out and
 * opens files.
 */
export class AccreditationDossier extends Component {
    static template = "dma_accreditation.AccreditationDossier";
    static props = { ...standardFieldProps };

    static labels = {
        files: _t("files"),
        noFiles: _t("No file"),
        missing: _t("Missing or not accepted"),
        complete: _t("Every required document is on file and accepted."),
        superseded: _t("superseded"),
        version: _t("Version"),
        open: _t("Open"),
        generated: _t("Generated with the dossier"),
        empty: _t("Nothing filed under this heading yet."),
        required: _t("Required"),
        optional: _t("Optional"),
        history: _t("Decision trail"),
        step: _t("Step"),
        entered: _t("Entered"),
        left: _t("Left"),
        duration: _t("Duration"),
        stillHere: _t("still here"),
        reviewer: _t("Reviewed by"),
    };

    setup() {
        this.action = useService("action");
        // Only the first section is open on arrival: a dossier of eighteen
        // headings is a table of contents, not a wall.
        this.state = useState({ open: { prerequisites: true } });
    }

    get payload() {
        return this.props.record.data[this.props.name] || {};
    }

    get sections() {
        return this.payload.sections || [];
    }

    get missing() {
        return this.payload.missing || [];
    }

    get label() {
        return AccreditationDossier.labels;
    }

    isOpen(section) {
        return Boolean(this.state.open[section.key]);
    }

    toggle(section) {
        this.state.open[section.key] = !this.state.open[section.key];
    }

    sectionCount(section) {
        return (section.entries || []).length;
    }

    /** Open one attachment in the viewer, through the access-checked route. */
    openFile(entry) {
        this.action.doAction({
            type: "ir.actions.act_url",
            target: "new",
            url: `/web/content/${entry.attachment_id}?download=false`,
        });
    }

    /** A file size a human reads, without pretending to precision. */
    humanSize(bytes) {
        if (!bytes) {
            return "";
        }
        if (bytes < 1024) {
            return `${bytes} B`;
        }
        if (bytes < 1024 * 1024) {
            return `${Math.round(bytes / 1024)} kB`;
        }
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    }
}

registry.category("fields").add("dma_dossier", {
    component: AccreditationDossier,
    displayName: _t("Accreditation Dossier"),
    supportedTypes: ["json"],
});
