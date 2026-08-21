/** @odoo-module **/

import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { Component } from "@odoo/owl";

export class GovHrWorkflowOverview extends Component {
    static template = "gov_hr_deputation.WorkflowOverview";
    static props = { ...standardFieldProps };

    get steps() {
        const value = this.props.record.data[this.props.name];
        return value?.steps || [];
    }

    statusLabel(status) {
        return {
            completed: _t("Completed"),
            current: _t("Current step"),
            returned: _t("Returned for correction"),
            pending: _t("Pending"),
        }[status] || _t("Pending");
    }

    iconClass(status) {
        return {
            completed: "fa-check",
            current: "fa-circle",
            returned: "fa-undo",
            pending: "fa-circle-o",
        }[status] || "fa-circle-o";
    }
}

registry.category("fields").add("gov_hr_workflow_overview", {
    component: GovHrWorkflowOverview,
    displayName: _t("Approval Workflow"),
    supportedTypes: ["json"],
});
