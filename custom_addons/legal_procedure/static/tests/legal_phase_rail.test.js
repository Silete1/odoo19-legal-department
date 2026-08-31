import { describe, expect, test } from "@odoo/hoot";
import { click } from "@odoo/hoot-dom";
import { animationFrame } from "@odoo/hoot-mock";
import { defineModels, fields, models, mountView } from "@web/../tests/web_test_helpers";

describe.current.tags("desktop");

/**
 * The rail is a pure renderer of the `progress_payload` Json field, so these
 * tests feed it payloads directly. What the payload *contains* is built on the
 * server and is covered by the Python tests; what is asserted here is the part
 * that only exists in the browser - the phase count, the accessibility
 * contract, the table fallback and the bidi handling.
 *
 * The first payload is the one that matters most: a twelve-step procedure
 * drawn as five phases. If this component ever starts drawing one segment per
 * step, this test fails, and it should.
 */
class LegalCase extends models.Model {
    _name = "legal.case";

    name = fields.Char();
    progress_payload = fields.Json();

    _records = [
        {
            id: 1,
            name: "LEG/2026/0001",
            progress_payload: {
                rtl: false,
                percent: 45,
                counter_label: "3 / 5",
                current_phase: "with_body",
                current_step: "await_assessment",
                current_label: "Awaiting the assessment",
                clerk_instruction_html:
                    "<p>Second floor, window 3. Ask for the assessment order.</p>",
                mine: false,
                closed: false,
                pending_groups: ["General Commission for Taxes"],
                phases: [
                    { key: "intake", number: 1, label: "Intake", status: "done",
                      step_labels: ["Open the file", "Collect the documents"],
                      actor: "Ali Clerk", date: "2026-01-05" },
                    { key: "prepare", number: 2, label: "Preparation", status: "done",
                      step_labels: ["Draft the letter", "Sign it", "Stamp it"],
                      actor: "Ali Clerk", date: "2026-01-08" },
                    { key: "with_body", number: 3, label: "With the body", status: "current",
                      step_labels: ["Deliver it", "Await the assessment"],
                      actor: false, date: false },
                    { key: "settle", number: 4, label: "Settlement", status: "todo",
                      step_labels: ["Pay the fee", "Collect the receipt"],
                      actor: false, date: false },
                    { key: "close", number: 5, label: "Closing", status: "todo",
                      step_labels: ["File the outcome"], actor: false, date: false },
                ],
                blockers: [
                    "The tax clearance letter has not been provided.",
                    "The Chamber identity has expired.",
                ],
            },
        },
        {
            id: 2,
            name: "LEG/2026/0002",
            progress_payload: {
                rtl: true,
                percent: 100,
                counter_label: "5 / 5",
                current_phase: "close",
                current_label: "أُغلقت المعاملة",
                mine: false,
                closed: true,
                pending_groups: [],
                phases: [
                    { key: "intake", number: 1, label: "الاستلام", status: "done",
                      step_labels: ["فتح الملف"], actor: "علي", date: "2026-01-05" },
                    { key: "close", number: 2, label: "الإغلاق", status: "done",
                      step_labels: ["حفظ النتيجة"], actor: "علي", date: "2026-02-01" },
                ],
                blockers: [],
            },
        },
    ];
}

defineModels([LegalCase]);

const ARCH = `
    <form>
        <field name="progress_payload" nolabel="1" readonly="1" widget="legal_phase_rail"/>
    </form>`;

async function mount(resId) {
    await mountView({ type: "form", resModel: "legal.case", resId, arch: ARCH });
}

test("draws phases, not steps - five segments over twelve stops", async () => {
    await mount(1);
    expect(".o_legal_rail").toHaveCount(1);
    expect(".o_legal_phase").toHaveCount(5);
    expect(".o_legal_phase_done").toHaveCount(2);
    expect(".o_legal_phase_current").toHaveCount(1);
    expect(".o_legal_phase_todo").toHaveCount(2);
});

test("the current phase carries aria-current, and only it does", async () => {
    await mount(1);
    expect(".o_legal_phase_current .o_legal_phase_btn").toHaveAttribute("aria-current", "step");
    expect("[aria-current='step']").toHaveCount(1);
});

test("every segment is a real button, so the rail is keyboard reachable", async () => {
    await mount(1);
    expect("button.o_legal_phase_btn").toHaveCount(5);
});

test("the status of a phase is stated in words, not only in colour", async () => {
    await mount(1);
    // Blocked rather than "in progress": the payload carries blockers, and a
    // reader who cannot see the tint must still be told.
    expect(".o_legal_phase_current .visually-hidden").toHaveText("Blocked");
    expect(".o_legal_phase_current").toHaveClass("o_legal_phase_blocked");
});

test("the fine step is named in prose beneath the rail", async () => {
    await mount(1);
    expect(".o_legal_rail_focus").toHaveCount(1);
    expect(".o_legal_rail_focus_steps").toHaveText(/Deliver it.*Await the assessment/);
});

test("selecting another phase moves the prose and nothing else", async () => {
    await mount(1);
    await click(".o_legal_phase[data-phase-key='settle'] .o_legal_phase_btn");
    await animationFrame();
    expect(".o_legal_rail_focus_steps").toHaveText(/Pay the fee.*Collect the receipt/);
    // Selecting is a reading act: the current phase is unchanged.
    expect(".o_legal_phase_current").toHaveClass("o_legal_phase_blocked");
});

test("the blockers are listed, and the counter is pinned ltr", async () => {
    await mount(1);
    expect(".o_legal_rail_blockers li").toHaveCount(2);
    expect(".o_legal_rail_counter").toHaveText("3 / 5");
    // A bare "3 / 5" is reordered to "5 / 3" by the bidi algorithm inside an
    // Arabic paragraph, so the span is pinned whatever the language.
    expect(".o_legal_rail_counter").toHaveAttribute("dir", "ltr");
});

test("the same figures are available as a real table, for print and for a reader", async () => {
    await mount(1);
    expect(".o_legal_rail_table").toHaveCount(1);
    expect(".o_legal_rail_table tbody tr").toHaveCount(5);
    expect(".o_legal_rail_table tbody tr:first th").toHaveText("Intake");
});

test("an Arabic payload flips the rail, and a closed file shows no blockers", async () => {
    await mount(2);
    expect(".o_legal_rail").toHaveAttribute("dir", "rtl");
    expect(".o_legal_rail_blockers").toHaveCount(0);
    expect(".o_legal_rail_pending").toHaveCount(0);
    expect(".o_legal_phase").toHaveCount(2);
});

test("a file waiting on the reader says so instead of naming a group", async () => {
    LegalCase._records[0].progress_payload.mine = true;
    await mount(1);
    expect(".o_legal_rail_mine").toHaveCount(1);
    expect(".o_legal_rail_pending").toHaveCount(0);
    LegalCase._records[0].progress_payload.mine = false;
});
