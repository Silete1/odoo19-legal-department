import { registry } from "@web/core/registry";

/**
 * Walks the real UI through the end of the office accreditation phase:
 * a file sitting at the Certifications Division check, with an incomplete
 * prerequisites checklist, is completed and granted.
 *
 * What this proves that the Python tests cannot: the progress widget renders
 * and refreshes, the checklist bulk buttons are wired to the right methods,
 * and the hard gate is reflected in the interface the officer actually sees.
 *
 * Every trigger is technical - data-state, the page `name`, the button `name` -
 * so the tour passes whatever language the user is in. Matching translated text
 * would make it fail on an Arabic-only database, which is exactly the
 * deployment this module targets.
 */
registry.category("web_tour.tours").add("dma_accreditation_office_grant", {
    // No `url`: the record to walk is chosen by start_tour, and a `url` here
    // would make tour_service redirect away from it (tour_service.js:157).
    steps: () => [
        {
            content: "the form is open",
            trigger: ".o_form_view",
        },
        {
            content: "the progress widget is mounted on the right step",
            trigger: ".o_dma_progress[data-state='cert_check']",
        },
        {
            content: "and it says the file is waiting on the Certifications Division",
            trigger: ".o_dma_progress[data-pending-role='cert_officer']",
        },
        {
            content: "the current step is flagged as blocked",
            trigger: ".o_dma_step_current.o_dma_step_blocked",
        },
        {
            content: "the widget lists what is missing",
            trigger: ".o_dma_blockers li",
        },
        {
            content: "open the prerequisites checklist",
            trigger: ".o_notebook .nav-link[name='documents']",
            run: "click",
        },
        {
            content: "tick every document as provided",
            trigger: "button[name='action_mark_all_provided']:enabled",
            run: "click",
        },
        {
            content: "the Certifications Division accepts them all",
            trigger: "button[name='action_accept_all_provided']:enabled",
            run: "click",
        },
        {
            content: "nothing blocks the step any more",
            trigger: ".o_dma_progress[data-blockers='0']",
        },
        {
            content: "the gate is open, so grant the office accreditation",
            trigger: "button[name='action_grant_office_accreditation']:enabled",
            run: "click",
        },
        {
            content: "the file has moved on and the widget followed it",
            trigger: ".o_dma_progress[data-state='office_granted']",
        },
        {
            content: "the certifications step is now signed off",
            trigger: ".o_dma_step_done",
        },
        {
            content: "and the form is clean",
            trigger: ".o_form_saved",
        },
    ],
});

/**
 * The counterpart: a department that does not own the current step gets no
 * action button at all, however the file is reached.
 */
registry.category("web_tour.tours").add("dma_accreditation_wrong_role", {
    steps: () => [
        {
            content: "the file is waiting on the Certifications Division",
            trigger: ".o_dma_progress[data-pending-role='cert_officer']",
        },
        {
            content: "Finance sees the file but is offered nothing to press",
            trigger: ".o_form_view:not(:has(button[name='action_grant_office_accreditation']))",
        },
        {
            content: "not even the return and reject buttons of another step",
            trigger: ".o_form_view:not(:has(button[name='action_open_return_wizard']))",
        },
        {
            content: "and it cannot bulk-accept the checklist either",
            trigger: ".o_form_view:not(:has(button[name='action_accept_all_provided']))",
        },
    ],
});
