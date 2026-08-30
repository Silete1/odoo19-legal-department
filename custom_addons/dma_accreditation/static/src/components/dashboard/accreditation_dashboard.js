import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Layout } from "@web/search/layout";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";
import { _t } from "@web/core/l10n/translation";
import { getColor, hexToRGBA } from "@web/core/colors/colors";
import { cookie } from "@web/core/browser/cookie";

import { DmaChart } from "../chart/dma_chart";
import { KpiTile } from "../kpi_tile/kpi_tile";
import { ActionWorklist } from "../action_worklist/action_worklist";
import { PipelineRibbon } from "../pipeline_ribbon/pipeline_ribbon";
import { DepartmentDesk } from "../department/department_desk";

/**
 * The directorate workspace.
 *
 * One client action, not one per department. The seven roles differ in *which
 * slice* of a single process they own, not in kind: the same worklist, the
 * same caseload and the same performance figures serve all of them, and the
 * Accreditation Manager holds every role at once - which seven separate
 * screens could not represent at all. What varies by role is the data, and
 * that is decided on the server, where `ROLE_QUEUE_STATES` already lives.
 *
 * Everything the page draws arrives in one call, so there is no request per
 * panel and the browser never composes a domain the server would disagree
 * with. Every number is a way in to the files behind it; a count with nothing
 * behind it would be a poster.
 */
export class AccreditationDashboard extends Component {
    static template = "dma_accreditation.AccreditationDashboard";
    static components = {
        Layout, DmaChart, KpiTile, ActionWorklist, PipelineRibbon, DepartmentDesk,
    };
    static props = { ...standardActionServiceProps };

    static labels = {
        deskTitle: _t("Your desk"),
        waitingForMe: _t("Waiting for you"),
        urgentSuffix: _t("urgent"),
        oldestSuffix: _t("longest wait"),
        nothingWaiting: _t("Nothing is waiting for you"),
        stalled: _t("Stalled over 7 days"),
        stalledHint: _t("On your desk and not moving"),
        withApplicant: _t("With the applicant"),
        withApplicantHint: _t("Returned for completion"),
        expiringTile: _t("Expiring in 90 days"),
        expiringHint: _t("Accreditations to renew"),

        departmentTitle: _t("Your department"),
        newRequest: _t("New Accreditation Request"),
        caseloadTitle: _t("The caseload"),
        caseloadHint: _t("The whole directorate's open files, for context. Your own work is above."),
        showCaseload: _t("Show the directorate figures"),
        hideCaseload: _t("Hide the directorate figures"),
        queues: _t("Department queues"),
        queuesHint: _t("Every step your department owns, including files a colleague already signed."),
        ageingTitle: _t("Where work is standing still"),
        ageingHint: _t("Open files by the department that owes the next move. A file awaiting two departments is counted under both."),
        ageingEmpty: _t("Nothing is waiting on a department right now."),
        stuckSuffix: _t("over 7 days"),
        mostStalled: _t("most stalled"),
        expiringTitle: _t("Accreditations expiring"),
        noExpiring: _t("No accreditation expires in the next 90 days."),

        performanceTitle: _t("Why we are slow"),
        cycleTitle: _t("How long each step takes"),
        cycleHint: _t("Median days a file waits at a step, measured on files that have finished it."),
        cycleThin: _t("Not enough finished files yet to measure how long each step takes."),
        cohortThin: _t("Measured on %s files, fewer than the twenty this module treats as enough - read these as indicative rather than as published figures."),
        median: _t("median"),
        p90: _t("9 in 10 within"),
        throughputTitle: _t("Received against issued"),
        throughputHint: _t("Applications arriving each month against accreditations granted."),
        throughputThin: _t("Not enough months of history to show a trend yet."),
        returnsTitle: _t("Where files get sent back"),
        returnsHint: _t("Returns and rejections by the step that issued them."),
        returnsEmpty: _t("No file has been returned or rejected in this window."),

        window90: _t("90 days"),
        window180: _t("180 days"),
        window365: _t("1 year"),
        scopeNote: _t("These three panels only"),
        days: _t("d"),
        files: _t("files"),
        returned: _t("returned"),
        rejected: _t("rejected"),
        loading: _t("Loading the workspace…"),
    };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.colorScheme = cookie.get("color_scheme");
        this.state = useState({
            data: null, window: 180, busy: false,
            // Off for an officer, irrelevant for a manager (who always
            // sees the figures); the toggle only exists for the former.
            analytics: false,
        });

        onWillStart(() => this.load());
    }

    async load() {
        this.state.busy = true;
        try {
            this.state.data = await this.orm.call(
                "dma.accreditation.request", "get_dashboard_data", [],
                { window_days: this.state.window },
            );
        } finally {
            this.state.busy = false;
        }
    }

    async setWindow(days) {
        if (this.state.window === days) {
            return;
        }
        this.state.window = days;
        await this.load();
    }

    get label() {
        return AccreditationDashboard.labels;
    }

    get data() {
        return this.state.data;
    }

    get windows() {
        return [
            { days: 90, label: this.label.window90 },
            { days: 180, label: this.label.window180 },
            { days: 365, label: this.label.window365 },
        ];
    }

    // ------------------------------------------------------------------
    // Colour: one validated system, from Odoo's own chart palette. The
    // status scale below is used identically by the worklist meter, the
    // ageing chart and the expiry chips, so the same hue always means the
    // same thing - and every one of them also ships a written label, so
    // nothing here depends on colour alone.
    // ------------------------------------------------------------------
    get statusColors() {
        const scheme = this.colorScheme;
        return {
            fresh: getColor(2, scheme, "sm"),      // teal
            slipping: getColor(3, scheme, "sm"),   // orange
            stuck: getColor(1, scheme, "sm"),      // red
        };
    }

    get chartInk() {
        return this.colorScheme === "dark" ? "#E4E4E4" : "#111827";
    }

    get chartMuted() {
        return this.colorScheme === "dark" ? "#A9ACB6" : "#6b7280";
    }

    get chartGrid() {
        return this.colorScheme === "dark" ? "rgba(255,255,255,.12)" : "rgba(0,0,0,.08)";
    }

    // ------------------------------------------------------------------
    // The two canvases. Everything else on this page is HTML, because it
    // has to be clickable, keyboard reachable, exact and printable - all
    // of which a canvas gives up, for nothing, at these data sizes.
    // ------------------------------------------------------------------
    get ageingChart() {
        const colors = this.statusColors;
        return {
            labels: this.data.ageing.labels,
            datasets: this.data.ageing.bands.map((band) => ({
                label: band.label,
                data: band.data,
                backgroundColor: colors[band.key],
                borderWidth: 0,
                borderSkipped: false,
                barThickness: 16,
            })),
        };
    }

    get ageingOptions() {
        const rtl = Boolean(this.data.rtl);
        return {
            indexAxis: "y",
            plugins: { legend: { display: true, position: "bottom" } },
            scales: {
                x: {
                    stacked: true,
                    beginAtZero: true,
                    reverse: rtl,
                    grid: { color: this.chartGrid },
                    border: { display: false },
                    ticks: { color: this.chartMuted, precision: 0 },
                },
                y: {
                    stacked: true,
                    position: rtl ? "right" : "left",
                    grid: { display: false },
                    border: { display: false },
                    ticks: { color: this.chartInk },
                },
            },
        };
    }

    get throughputChart() {
        const scheme = this.colorScheme;
        const hues = [getColor(0, scheme, "sm"), getColor(2, scheme, "sm")];
        return {
            labels: this.data.throughput.labels,
            datasets: this.data.throughput.series.map((series, index) => ({
                label: series.label,
                data: series.data,
                borderColor: hues[index],
                backgroundColor: hexToRGBA(hues[index], 0.14),
                fill: index === 0 ? "origin" : false,
                borderWidth: 2,
                pointRadius: 3,
                pointHoverRadius: 6,
                pointBackgroundColor: hues[index],
                pointBorderWidth: 0,
                tension: 0.32,
            })),
        };
    }

    get throughputOptions() {
        const rtl = Boolean(this.data.rtl);
        return {
            plugins: { legend: { display: true, position: "bottom" } },
            interaction: { mode: "index", intersect: false },
            scales: {
                x: {
                    reverse: rtl,
                    grid: { display: false },
                    border: { display: false },
                    ticks: { color: this.chartMuted },
                },
                y: {
                    beginAtZero: true,
                    position: rtl ? "right" : "left",
                    grid: { color: this.chartGrid },
                    border: { display: false },
                    ticks: { color: this.chartMuted, precision: 0 },
                },
            },
        };
    }

    /** The ageing chart as text, for a screen reader and for a printout. */
    get ageingRows() {
        const ageing = this.data.ageing;
        return ageing.labels.map((label, index) => ({
            role: ageing.roles[index],
            label,
            total: ageing.totals[index],
            stuck: ageing.stuck[index],
            bands: ageing.bands.map((band) => ({
                key: band.key, label: band.label, value: band.data[index],
            })),
        }));
    }

    // ------------------------------------------------------------------
    // Drill-through. Every figure on this page opens the files behind it.
    // ------------------------------------------------------------------
    openRequests(title, domain) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: title,
            res_model: "dma.accreditation.request",
            views: [[false, "list"], [false, "kanban"], [false, "form"]],
            domain,
            target: "current",
        });
    }

    openRecord(resId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "dma.accreditation.request",
            res_id: resId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    openMyTurn() {
        this.openRequests(this.label.waitingForMe, [["is_my_turn", "=", true]]);
    }

    openStep(step) {
        this.openRequests(step.label, step.domain);
    }

    openStalled() {
        // The server decided which files count as stalled; sending its ids
        // keeps the browser from inventing a second definition of "7 days".
        const ids = this.data.my_files
            .filter((file) => file.waiting_days >= 7)
            .map((file) => file.id);
        this.openRequests(this.label.stalled, [["id", "in", ids]]);
    }

    openWithApplicant() {
        this.openRequests(this.label.withApplicant, [["state", "=", "returned"]]);
    }

    openExpiring() {
        this.openRequests(
            this.label.expiringTitle,
            [["id", "in", this.data.expiring.map((row) => row.id)]],
        );
    }

    openDepartment(role) {
        const queue = this.data.queues.find((entry) => entry.role === role);
        if (queue) {
            this.openRequests(queue.label, queue.domain);
        }
    }

    openFee(feeId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "dma.fee.payment",
            res_id: feeId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    /**
     * A section's own "open all". Fees open on their own model; everything
     * else is a request domain, and both come from the server so the browser
     * never composes a domain the record rules would disagree with.
     */
    openSection(section) {
        if (section.kind === "fees") {
            this.action.doAction({
                type: "ir.actions.act_window",
                name: section.title,
                res_model: "dma.fee.payment",
                views: [[false, "list"], [false, "form"]],
                domain: section.domain,
                target: "current",
            });
            return;
        }
        this.openRequests(section.title, section.domain);
    }

    /** Reception opens files; the action that starts one belongs on its desk. */
    newRequest() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: this.label.newRequest,
            res_model: "dma.accreditation.request",
            views: [[false, "form"]],
            target: "current",
        });
    }

    /**
     * The directorate-wide figures are the Accreditation Manager's screen.
     * An officer gets them on request rather than by default: a reception
     * clerk opening the app to a cycle-time percentile has to scroll past a
     * report to reach their own three files.
     */
    get showsAnalytics() {
        return this.data.role_brief.is_manager || this.state.analytics;
    }

    toggleAnalytics() {
        this.state.analytics = !this.state.analytics;
    }

    /** The cohort caveat as one sentence, rather than two joined in markup. */
    cohortNote(count) {
        return this.label.cohortThin.replace("%s", count);
    }
}

registry.category("actions").add("dma_accreditation_dashboard", AccreditationDashboard);
