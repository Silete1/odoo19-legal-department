import { describe, expect, test } from "@odoo/hoot";
import { defineModels, fields, models, mountView } from "@web/../tests/web_test_helpers";
import { defineMailModels } from "@mail/../tests/mail_test_helpers";

describe.current.tags("desktop");

/**
 * The widget is a pure renderer of the `progress_payload` Json field, so these
 * tests feed it payloads directly. The payload itself is built on the server by
 * `_compute_progress_payload` and is covered by the Python tests.
 */
class DmaAccreditationRequest extends models.Model {
    _name = "dma.accreditation.request";

    name = fields.Char();
    progress_payload = fields.Json();

    _records = [
        {
            id: 1,
            name: "DMA/ACC/2026/0001",
            progress_payload: {
                rtl: false,
                current: "cert_check",
                current_label: "Certifications Division Check",
                closed: false,
                exception: false,
                exception_label: false,
                pending_role: "Certifications Division Officer",
                steps_done: 4,
                steps_total: 6,
                percent: 67,
                steps: [
                    { key: "draft", number: 1, label: "Draft", role: "Reception Officer",
                      status: "done", user: "Rita Reception", date: "2026-01-05 09:00:00" },
                    { key: "submitted", number: 2, label: "Submitted", role: "Reception Officer",
                      status: "done", user: "Rita Reception", date: "2026-01-05 09:10:00" },
                    { key: "gd_review", number: 3, label: "General Director Initial Acceptance",
                      role: "General Director", status: "done", user: "Gina Director",
                      date: "2026-01-06 11:00:00" },
                    { key: "legal_review", number: 4, label: "Legal Department Review",
                      role: "Legal Department Director", status: "done", user: "Leo Legal",
                      date: "2026-01-07 08:30:00" },
                    { key: "cert_check", number: 5, label: "Certifications Division Check",
                      role: "Certifications Division Officer", status: "current",
                      user: false, date: false },
                    { key: "office_granted", number: 6, label: "Office Accreditation Granted",
                      role: "Operations Department", status: "todo", user: false, date: false },
                ],
                blockers: [
                    "Equipment List has not been provided.",
                    "Insurance is provided but not accepted yet.",
                ],
            },
        },
        {
            id: 2,
            name: "DMA/ACC/2026/0002",
            progress_payload: {
                rtl: true,
                current: "authorized",
                current_label: "Operational Accreditation Granted",
                closed: true,
                exception: false,
                exception_label: false,
                pending_role: false,
                steps_done: 6,
                steps_total: 6,
                percent: 100,
                steps: [
                    { key: "draft", number: 1, label: "Draft", role: "Reception Officer",
                      status: "done", user: "Rita Reception", date: "2026-01-05 09:00:00" },
                    { key: "authorized", number: 2, label: "Operational Accreditation Granted",
                      role: "Accreditation Manager", status: "done", user: "Leo Legal",
                      date: "2026-02-01 12:00:00" },
                ],
                blockers: [],
            },
        },
        {
            id: 3,
            name: "DMA/ACC/2026/0003",
            progress_payload: {
                rtl: false,
                current: "rejected",
                current_label: "Rejected",
                closed: true,
                exception: "rejected",
                exception_label: "Rejected",
                pending_role: false,
                steps_done: 2,
                steps_total: 6,
                percent: 33,
                steps: [
                    { key: "draft", number: 1, label: "Draft", role: "Reception Officer",
                      status: "done", user: "Rita Reception", date: "2026-01-05 09:00:00" },
                ],
                blockers: [],
            },
        },
    ];
}

defineMailModels();
defineModels([DmaAccreditationRequest]);

const ARCH = `
    <form>
        <field name="progress_payload" nolabel="1" readonly="1"
               widget="dma_accreditation_progress"/>
    </form>`;

async function mount(resId) {
    await mountView({
        type: "form",
        resModel: "dma.accreditation.request",
        resId,
        arch: ARCH,
    });
}

test("draws one card per step, with the current one highlighted", async () => {
    await mount(1);
    expect(".o_dma_progress").toHaveCount(1);
    expect(".o_dma_step").toHaveCount(6);
    expect(".o_dma_step_done").toHaveCount(4);
    expect(".o_dma_step_current").toHaveCount(1);
    expect(".o_dma_step_todo").toHaveCount(1);
    expect(".o_dma_step_current .o_dma_step_label").toHaveText(
        "Certifications Division Check"
    );
});

test("names the department that owes the next move", async () => {
    await mount(1);
    expect(".o_dma_progress_state").toHaveText("Certifications Division Check");
    expect(".o_dma_progress_pending").toHaveText(
        /Certifications Division Officer/
    );
    expect(".o_dma_progress_counter").toHaveText("4 / 6");
});

test("lists what is blocking the current step, and marks it blocked", async () => {
    await mount(1);
    expect(".o_dma_blockers").toHaveCount(1);
    expect(".o_dma_blockers li").toHaveCount(2);
    expect(".o_dma_blockers li:first").toHaveText(
        "Equipment List has not been provided."
    );
    expect(".o_dma_step_current").toHaveClass("o_dma_step_blocked");
});

test("a signed step shows who signed it", async () => {
    await mount(1);
    expect(".o_dma_step:first .o_dma_step_user").toHaveText("Rita Reception");
    expect(".o_dma_step:first .o_dma_step_role").toHaveText("Reception Officer");
    // ... and an unsigned one shows nothing rather than an empty line
    expect(".o_dma_step_current .o_dma_step_user").toHaveCount(0);
});

test("a closed file shows neither blockers nor a pending department", async () => {
    await mount(2);
    expect(".o_dma_blockers").toHaveCount(0);
    expect(".o_dma_progress_pending").toHaveCount(0);
    expect(".o_dma_progress_counter").toHaveText("6 / 6");
});

test("an Arabic payload flips the rail to right-to-left", async () => {
    await mount(2);
    expect(".o_dma_progress").toHaveAttribute("dir", "rtl");
    // the counter stays ltr so bidi cannot reorder "6 / 6"
    expect(".o_dma_progress_counter").toHaveAttribute("dir", "ltr");
});

test("a rejected file is called out", async () => {
    await mount(3);
    expect(".o_dma_exception").toHaveCount(1);
    expect(".o_dma_exception").toHaveText("Rejected");
    expect(".o_dma_blockers").toHaveCount(0);
});
