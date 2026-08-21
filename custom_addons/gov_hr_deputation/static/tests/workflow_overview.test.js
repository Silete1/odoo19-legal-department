import { expect, test } from "@odoo/hoot";
import { defineModels, fields, models, mountView } from "@web/../tests/web_test_helpers";

import "@gov_hr_deputation/components/workflow_overview/workflow_overview";


class GovernmentCase extends models.Model {
    workflow_display = fields.Json();

    _records = [
        {
            id: 1,
            workflow_display: {
                rtl: true,
                steps: [
                    { id: 10, label: "مدير القسم", status: "completed", approver: "أحمد" },
                    { id: 20, label: "المدير العام", status: "current" },
                    { id: 30, label: "الموظف الإداري", status: "pending" },
                ],
            },
        },
    ];
}

defineModels([GovernmentCase]);

test("workflow overview presents completed, current, and pending steps in RTL", async () => {
    await mountView({
        type: "form",
        resModel: "government.case",
        resId: 1,
        arch: /* xml */ `<form><field name="workflow_display" widget="gov_hr_workflow_overview"/></form>`,
    });

    expect(".o_gov_hr_workflow").toHaveAttribute("dir", "rtl");
    expect(".o_gov_hr_workflow_step").toHaveCount(3);
    expect(".o_gov_hr_workflow_step.is-completed").toHaveText(/مدير القسم/);
    expect(".o_gov_hr_workflow_step.is-current").toHaveText(/المدير العام/);
    expect(".o_gov_hr_workflow_step.is-pending").toHaveText(/الموظف الإداري/);
});
