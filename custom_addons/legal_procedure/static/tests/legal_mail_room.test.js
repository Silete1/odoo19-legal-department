import { beforeEach, describe, expect, test } from "@odoo/hoot";
import { click } from "@odoo/hoot-dom";
import { animationFrame } from "@odoo/hoot-mock";
import {
    defineModels, getService, models, mountWithCleanup,
} from "@web/../tests/web_test_helpers";
import { WebClient } from "@web/webclient/webclient";

describe.current.tags("desktop");

/**
 * The Mail Room is a pure renderer of one server call, so the whole of these
 * tests is: hand it a payload, assert the screen. Every threshold, every
 * domain and every Arabic sentence in that payload is composed in
 * `legal.dashboard` and is covered by the Python tests - what is asserted here
 * is only what exists in the browser.
 *
 * The important assertions are the ones about *absence*: an empty column still
 * renders and still says what would be there, a zero hero is not a button, and
 * a file that is not ready still shows its next action, greyed, with the
 * reason attached. Those three are the design decisions most likely to be
 * quietly lost in a refactor.
 */
let payload;
// How many loads the mock server should fail before answering: the error
// state below is exercised by failing exactly one.
let failures;

function basePayload() {
    return {
        rtl: false,
        numerals: "western",
        title: "The Mail Room",
        subtitle: "What arrived, what we are chasing, what must go out",
        role: { is_manager: false, is_approver: false, is_officer: false,
                is_auditor: false, can_write: true,
                landing_band: "files", label: "Clerk" },
        degraded: [],
        hero: {
            label: "Waiting for you",
            count: 3,
            count_label: "3",
            note: "2 to register, 1 to send out",
            oldest_label: "Oldest chase: 6 working day(s)",
            action: { type: "ir.actions.act_window", res_model: "legal.correspondence",
                      views: [[false, "list"]], domain: [] },
        },
        tiles: [
            { key: "overdue", label: "Overdue replies", value: 1, value_label: "1",
              hint: "Past the target", icon: "fa-exclamation-triangle", tone: "critical",
              action: { type: "ir.actions.act_window", res_model: "legal.correspondence",
                        views: [[false, "list"]], domain: [] } },
            { key: "at_body", label: "With the bodies", value: 0, value_label: "0",
              hint: "Sent, no reply yet", icon: "fa-institution", tone: "neutral",
              action: false },
            { key: "to_issue", label: "To be issued", value: 1, value_label: "1",
              hint: "Next move is a letter", icon: "fa-paper-plane", tone: "attention",
              action: false },
        ],
        columns: [
            {
                key: "incoming",
                title: "Arrived today",
                hint: "Registered, and not yet attached to any file",
                empty: "Nothing new is waiting to be filed.",
                empty_hint: "An incoming letter appears here the moment it is registered.",
                count: 2, count_label: "2", overflow: 0, overflow_label: "0 more",
                open_all_label: "Open all", action: false,
                rows: [
                    {
                        id: 11, model: "legal.correspondence",
                        our_number: "و/2026/0044", their_ref: "ص/ضرائب/9812",
                        their_date_label: "2026-02-11", date_label: "2026-02-12",
                        subject: "Tax assessment for 2025", body_label: "Taxes",
                        body_colour: 3, is_draft: false, draft_label: "",
                        attachment_id: 5, attachment_label: "Open the scan",
                        link: { model: "legal.case", domain: [], title: "Attach to a file" },
                        link_label: "Attach to a file",
                        new_case: { type: "ir.actions.act_window", res_model: "legal.case",
                                    views: [[false, "form"]], context: {} },
                        new_case_label: "Open a new file",
                        open: false,
                    },
                    {
                        id: 12, model: "legal.correspondence",
                        our_number: "", their_ref: "", their_date_label: "",
                        date_label: "2026-02-12", subject: "Inspection notice",
                        body_label: "Civil Defence", body_colour: 1,
                        is_draft: true, draft_label: "Not numbered yet",
                        attachment_id: false, attachment_label: "Open the scan",
                        link: false, link_label: "Attach to a file",
                        new_case: false, new_case_label: "Open a new file", open: false,
                    },
                ],
            },
            {
                key: "awaiting",
                title: "Awaiting a reply",
                hint: "Sent by us, with no reply matched to it yet",
                empty: "We are not waiting on anybody.",
                empty_hint: "An outgoing letter appears here the day it is issued.",
                count: 1, count_label: "1", overflow: 0, overflow_label: "0 more",
                open_all_label: "Open all", action: false,
                rows: [
                    {
                        id: 21, model: "legal.correspondence", our_number: "ص/2026/0101",
                        subject: "Request for a clearance letter", body_label: "Taxes",
                        body_colour: 3, date_label: "2026-02-01",
                        due_label: "Reply due 2026-02-10",
                        waiting_days: 12, waiting_label: "12 working day(s)",
                        age_band: "stuck", age_percent: 86,
                        clock: {
                            rtl: false, state: "overdue", state_label: "Overdue",
                            kind: "at_body", kind_label: "With Taxes",
                            age: "12 working day(s)",
                            age_label: "With them for 12 working day(s)",
                            overdue_label: "4 working day(s) past the target",
                            target_label: "Target 8 working day(s)",
                            icon: "fa-exclamation-triangle",
                        },
                        remind: { type: "ir.actions.act_window",
                                  res_model: "legal.correspondence",
                                  views: [[false, "form"]], target: "new", context: {} },
                        remind_label: "Send a reminder",
                        call: false, call_label: "Log a telephone call",
                        open: false,
                    },
                ],
            },
            {
                key: "issue",
                title: "To be issued",
                hint: "The next move on these files is a letter from us",
                empty: "No letter is waiting to be written.",
                empty_hint: "A file appears here when its procedure reaches an outgoing step.",
                count: 1, count_label: "1", overflow: 0, overflow_label: "0 more",
                open_all_label: "Open all", action: false,
                rows: [
                    {
                        id: 31, model: "legal.case", name: "LEG/2026/0007",
                        subject: "Chamber of Commerce renewal", body_label: "Chamber",
                        body_colour: 2, step_label: "Draft the letter",
                        next_action_label: "Write the letter",
                        docs_done: 3, docs_total: 4, meter_label: "3 / 4",
                        meter_percent: 75, ready: false,
                        action_label: "Write the letter",
                        blocker_summary: "1 required document(s) still outstanding.",
                        open: false,
                    },
                ],
            },
        ],
    };
}

class LegalDashboard extends models.Model {
    _name = "legal.dashboard";

    get_mail_room_data() {
        if (failures > 0) {
            failures--;
            throw new Error("the register is unreachable");
        }
        return payload;
    }

    link_correspondence() {
        return { ok: true, message: "linked" };
    }
}

defineModels([LegalDashboard]);

beforeEach(() => {
    payload = basePayload();
    failures = 0;
});

async function open() {
    await mountWithCleanup(WebClient);
    await getService("action").doAction({ type: "ir.actions.client", tag: "legal_mail_room" });
    await animationFrame();
}

test("one call fills the page: three columns, a hero and three tiles", async () => {
    await open();
    expect(".o_legal_mail_room").toHaveCount(1);
    expect(".o_legal_column").toHaveCount(3);
    expect(".o_legal_tile").toHaveCount(3);
    expect("[data-column='incoming']").toHaveCount(1);
    expect("[data-column='awaiting']").toHaveCount(1);
    expect("[data-column='issue']").toHaveCount(1);
});

test("the hero is a button carrying the server's own domain", async () => {
    await open();
    expect("button.o_legal_hero_value").toHaveCount(1);
    expect("button.o_legal_hero_value").toHaveText("3");
    // Pinned ltr: a numeral prefixed by anything at all is reordered by bidi
    // inside an Arabic paragraph.
    expect("button.o_legal_hero_value").toHaveAttribute("dir", "ltr");
});

test("a hero reading zero is legible and is not a button", async () => {
    payload.hero.count = 0;
    payload.hero.count_label = "0";
    await open();
    expect("button.o_legal_hero_value").toHaveCount(0);
    expect(".o_legal_hero_zero").toHaveText("0");
});

test("a tile with nothing behind it stops being a button", async () => {
    await open();
    // Overdue: value 1 with an action - a way in to the records.
    expect(".o_legal_tile[data-kpi='fa-exclamation-triangle']").toHaveAttribute("role", "button");
    // With the bodies: value 0 - a count with nothing behind it is a poster.
    expect(".o_legal_tile[data-kpi='fa-institution']").not.toHaveAttribute("role", "button");
});

test("the incoming row offers exactly two moves, and no more", async () => {
    await open();
    const row = "[data-column='incoming'] [data-row='11'] .o_legal_mr_actions";
    expect(`${row} .btn-secondary`).toHaveCount(1);
    expect(`${row} .btn-primary`).toHaveCount(1);
});

test("an entry the register cannot yet file says so rather than offering a dead button", async () => {
    await open();
    const row = "[data-column='incoming'] [data-row='12']";
    expect(`${row} .o_legal_mr_draft`).toHaveText("Not numbered yet");
    expect(`${row} .o_legal_mr_actions .btn-primary`).toHaveCount(0);
});

test("a chase row is aged in the body's working days and carries the reminder", async () => {
    await open();
    const row = "[data-column='awaiting'] [data-row='21']";
    expect(`${row} .o_legal_clock`).toHaveAttribute("data-clock", "overdue");
    // Whose clock it is, in words, before any colour says it.
    expect(`${row} .o_legal_clock_kind`).toHaveText("With Taxes");
    expect(`${row} .o_legal_mr_actions .btn-secondary`).toHaveText("Send a reminder");
});

test("the issuing row shows the meter and the GREYED twin with its blocker", async () => {
    await open();
    const row = "[data-column='issue'] [data-row='31']";
    expect(`${row} .o_legal_mr_meter_label`).toHaveText("3 / 4");
    expect(`${row} .o_legal_mr_meter_label`).toHaveAttribute("dir", "ltr");
    // The next action stays visible while it is out of reach, and carries why.
    expect(`${row} .btn-primary`).toHaveCount(0);
    expect(`${row} .btn-secondary.disabled`).toHaveText("Write the letter");
    expect(`${row} .btn-secondary.disabled`).toHaveAttribute(
        "title", "1 required document(s) still outstanding."
    );
    // ... and in words too, because a title attribute reaches neither a touch
    // user nor a printer.
    expect(`${row} .o_legal_mr_blocker`).toHaveText(
        "1 required document(s) still outstanding."
    );
});

test("a ready file gets the enabled primary and no greyed twin", async () => {
    payload.columns[2].rows[0].ready = true;
    await open();
    const row = "[data-column='issue'] [data-row='31']";
    expect(`${row} .btn-primary`).toHaveText("Write the letter");
    expect(`${row} .btn-secondary.disabled`).toHaveCount(0);
    expect(`${row} .o_legal_mr_blocker`).toHaveCount(0);
});

test("an empty column still renders and says what would be there", async () => {
    payload.columns[0].rows = [];
    payload.columns[0].count = 0;
    payload.columns[0].count_label = "0";
    await open();
    expect("[data-column='incoming'] .o_legal_empty").toHaveCount(1);
    expect("[data-column='incoming'] .o_legal_empty_title").toHaveText(
        "Nothing new is waiting to be filed."
    );
    expect("[data-column='incoming'] .o_legal_empty_hint").toHaveText(
        "An incoming letter appears here the moment it is registered."
    );
});

test("an Arabic payload flips the whole screen from the server flag", async () => {
    payload.rtl = true;
    await open();
    expect(".o_legal_mail_room .o_legal_body").toHaveAttribute("dir", "rtl");
});

test("a missing sibling model is stated once, not left as three blank columns", async () => {
    payload.degraded = ["The procedure engine is not installed."];
    await open();
    expect(".o_legal_degraded").toHaveCount(1);
    expect(".o_legal_degraded").toHaveText(/The procedure engine is not installed./);
});

test("a failed load is an error state with a retry, never an eternal spinner", async () => {
    failures = 1;
    await open();
    expect(".o_legal_error").toHaveCount(1);
    expect(".o_legal_loading").toHaveCount(0);
    expect(".o_legal_error .o_legal_retry").toHaveCount(1);
    // The retry reloads, and the second answer fills the page.
    await click(".o_legal_error .o_legal_retry");
    await animationFrame();
    expect(".o_legal_error").toHaveCount(0);
    expect(".o_legal_mail_room .o_legal_body").toHaveCount(1);
    expect(".o_legal_column").toHaveCount(3);
});

test("a read-only reader is offered not one mutation control", async () => {
    payload.role.can_write = false;
    payload.role.is_auditor = true;
    payload.role.label = "Auditor";
    await open();
    // The rows still read in full; only the verbs are gone.
    expect("[data-column='incoming'] [data-row='11']").toHaveCount(1);
    expect("[data-column='incoming'] .o_legal_mr_actions .btn-primary").toHaveCount(0);
    expect("[data-column='incoming'] .o_legal_mr_actions .btn-secondary").toHaveCount(0);
    expect("[data-column='awaiting'] .o_legal_mr_actions .btn-secondary").toHaveCount(0);
});
