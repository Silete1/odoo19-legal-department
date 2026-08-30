import { describe, expect, test } from "@odoo/hoot";
import { queryAll, queryAllTexts, queryFirst } from "@odoo/hoot-dom";
import { mountWithCleanup } from "@web/../tests/web_test_helpers";
import { defineMailModels } from "@mail/../tests/mail_test_helpers";

import { DepartmentDesk } from "@dma_accreditation/components/department/department_desk";

describe.current.tags("desktop");

// The component is mounted in a full web environment, which brings the mail
// services along with it; without their models the environment cannot be built.
defineMailModels();

/**
 * The band is a pure renderer of the `role_brief` payload, which is built on
 * the server by `_role_brief` and covered by the Python tests. These feed it
 * payloads directly and assert the three things the markup - not the data -
 * is responsible for: that a section with nothing in it still explains itself,
 * that the parallel step draws two independent signatures rather than one
 * status, and that a row opens the record it names.
 */
function section(overrides = {}) {
    return {
        key: "cert_check",
        kind: "files",
        title: "Prerequisites to verify",
        hint: "Check each required document.",
        empty: "No file is waiting for the Certifications Division.",
        count: 0,
        domain: [["state", "=", "cert_check"]],
        rows: [],
        action: false,
        ...overrides,
    };
}

function row(overrides = {}) {
    return {
        id: 7,
        name: "DMA/ACC/2026/0007",
        partner: "Al-Amal Demining Company",
        state: "cert_check",
        state_label: "Certifications Division Check",
        urgent: false,
        waiting_days: 3,
        waiting_label: "3 day(s)",
        note: "Two prerequisites are still missing.",
        chips: [],
        meter: false,
        ...overrides,
    };
}

function brief(sections, extra = {}) {
    return {
        departments: [{
            key: "cert_officer",
            label: "Certifications Division Officer",
            mission: "Verify the prerequisites of every application.",
            sections,
            outstanding: sections.reduce((total, s) => total + s.count, 0),
        }],
        recent: [],
        is_manager: false,
        can_create: false,
        ...extra,
    };
}

async function mount(payload, handlers = {}) {
    const calls = { record: [], fee: [], section: [], create: 0 };
    await mountWithCleanup(DepartmentDesk, {
        props: {
            brief: payload,
            onOpenRecord: (id) => calls.record.push(id),
            onOpenFee: (id) => calls.fee.push(id),
            onOpenSection: (s) => calls.section.push(s.key),
            onNewRequest: () => (calls.create += 1),
            ...handlers,
        },
    });
    return calls;
}

test("an empty section still says what would be in it", async () => {
    await mount(brief([section()]));

    expect(".o_dma_sec_title").toHaveText(/Prerequisites to verify/);
    expect(".o_dma_sec_empty").toHaveText(
        "No file is waiting for the Certifications Division."
    );
    // An empty section is a result, not an alarm: it stops competing for
    // attention rather than disappearing.
    expect(".o_dma_dept_section").toHaveClass("o_dma_dept_clear");
    expect(".o_dma_sec_rows").toHaveCount(0);
});

test("a file row shows the sentence, the ratio and the age", async () => {
    await mount(brief([section({
        count: 1,
        rows: [row({
            meter: { done: 7, total: 10, percent: 70, label: "7 / 10" },
            chips: [{ label: "3 not provided", tone: "critical" }],
        })],
    })]));

    expect(".o_dma_sec_ref").toHaveText(/DMA\/ACC\/2026\/0007/);
    expect(".o_dma_sec_note").toHaveText("Two prerequisites are still missing.");
    expect(".o_dma_sec_ratio").toHaveText("7 / 10");
    // The ratio is stamped ltr: a bare "7 / 10" is reordered to "10 / 7" by
    // the bidi algorithm inside an Arabic paragraph.
    expect(".o_dma_sec_ratio").toHaveAttribute("dir", "ltr");
    expect(queryFirst(".o_dma_meter_fill").style.width).toBe("70%");
    expect(".o_dma_chip").toHaveText("3 not provided");
    expect(".o_dma_chip").toHaveClass("o_dma_tone_critical");
    expect(".o_dma_sec_age").toHaveText("3d");
});

test("the parallel step draws two signatures, not one status", async () => {
    await mount(brief([section({
        key: "dual_confirm",
        kind: "dual",
        title: "Dual confirmation",
        count: 1,
        rows: [row({
            state: "dual_confirm",
            note: "Your confirmation is outstanding.",
            dual: {
                mine_label: "Operations Department",
                mine_done: false,
                other_label: "Finance Department",
                other_done: true,
                other_by: "Fadi Finance",
                other_on: "2026-03-03 10:00",
                complete: false,
            },
        })],
    })]));

    const signs = queryAll(".o_dma_sign");
    expect(signs.length).toBe(2);
    expect(queryAllTexts(".o_dma_sign")).toEqual([
        "Operations Department", "Finance Department",
    ]);
    // Signed and outstanding differ by class and by icon as well as by hue,
    // so the pair stays legible without colour.
    expect(signs[0]).toHaveClass("o_dma_sign_todo");
    expect(signs[1]).toHaveClass("o_dma_sign_done");
    expect(".o_dma_sign_todo .fa-clock-o").toHaveCount(1);
    expect(".o_dma_sign_done .fa-check").toHaveCount(1);
    // The department that has signed is named, so the other knows whom to ask.
    expect(signs[1]).toHaveAttribute("title", /Fadi Finance/);
});

test("a fee row leads with the money and flags a missing receipt", async () => {
    const calls = await mount(brief([section({
        key: "fees_to_confirm",
        kind: "fees",
        title: "Fees awaiting confirmation",
        count: 1,
        rows: [{
            id: 42,
            model: "dma.fee.payment",
            request_id: 7,
            name: "DMA/ACC/2026/0007",
            partner: "Al-Amal Demining Company",
            fee_type: "SOP Reading Fee",
            amount: 250,
            currency: "IQD",
            receipt_number: "",
            receipt_date: "",
            attachments: 0,
            state_label: "SOP Reading Fee",
            note: "Missing before it can be confirmed: receipt number.",
            ready: false,
        }],
    })]));

    expect(".o_dma_fee_type").toHaveText("SOP Reading Fee");
    expect(".o_dma_fee_amount").toHaveText(/250/);
    expect(".o_dma_fee_receipt").toHaveCount(0);
    expect(queryAllTexts(".o_dma_chip").join(" ")).toInclude("No receipt number");

    // A fee row opens the payment, not the file: confirming it is the action.
    await queryFirst(".o_dma_fee_row button").click();
    expect(calls.fee).toEqual([42]);
    expect(calls.record).toEqual([]);
});

test("a file row opens the record it names", async () => {
    const calls = await mount(brief([section({ count: 1, rows: [row()] })]));

    await queryFirst(".o_dma_sec_row button").click();
    expect(calls.record).toEqual([7]);
});

/** The reception department, which is the only one that opens files. */
function receptionBrief() {
    return {
        departments: [{
            key: "reception",
            label: "Reception Officer",
            mission: "Open accreditation files.",
            sections: [section({ key: "drafts", title: "Files being opened" })],
            outstanding: 0,
        }],
        recent: [],
        is_manager: false,
        can_create: true,
    };
}

test("the create action is drawn for reception and for nobody else", async () => {
    // A department that does not open files, and a reader without the right.
    await mount(brief([section()]));
    expect(".o_dma_new_request").toHaveCount(0);
});

test("reception is given the action that starts a file", async () => {
    const calls = await mount(receptionBrief());

    expect(".o_dma_new_request").toHaveCount(1);
    await queryFirst(".o_dma_new_request").click();
    expect(calls.create).toBe(1);
});

test("the create action is withheld when the reader may not create", async () => {
    const payload = receptionBrief();
    payload.can_create = false;
    await mount(payload);

    // Drawing it is a courtesy; the server is what refuses the create.
    expect(".o_dma_new_request").toHaveCount(0);
});

test("a section holding more than it shows offers the rest", async () => {
    const calls = await mount(brief([section({
        count: 9,
        rows: [row(), row({ id: 8, name: "DMA/ACC/2026/0008" })],
    })]));

    expect(".o_dma_sec_foot").toHaveCount(1);
    expect(".o_dma_sec_foot").toHaveText(/7/);
    await queryFirst(".o_dma_sec_foot button").click();
    expect(calls.section).toEqual(["cert_check"]);
});
