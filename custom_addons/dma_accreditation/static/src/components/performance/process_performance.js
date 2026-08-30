import { Component, onWillStart, onWillUnmount, useEffect, useRef, useState } from "@odoo/owl";
import { loadBundle } from "@web/core/assets";
import { cookie } from "@web/core/browser/cookie";
import { getColor, getCustomColor } from "@web/core/colors/colors";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Layout } from "@web/search/layout";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";
import { _t } from "@web/core/l10n/translation";

/**
 * Process performance of the accreditation procedure.
 *
 * Every figure comes from `get_process_performance_data`, `get_sla_dashboard_data`
 * and `get_document_health_data`, which read the immutable approval log and the
 * live caseload. Nothing is computed in the browser, so the numbers on this
 * screen are the numbers the Python tests assert.
 *
 * What is a chart and what is not
 * --------------------------------
 * Only one thing here is a chart: the monthly flow of files through the two
 * accreditation phases, because "is this getting faster or slower" is a
 * question about a trend and a trend is what a line does well.
 *
 * The stage ranking is deliberately NOT a chart. It is one series - the median
 * wait per step - so magnitude is carried by bar length and a hue would carry
 * nothing. It uses the very same bar rows the department dashboard already
 * uses for "files by step", so the two screens read as one application.
 *
 * Everything else is a table, because a manager reading "which department is
 * holding twelve files" wants the twelve, not a wedge.
 */

//: Windows the period selector offers, in months.
const PERIODS = [3, 6, 12, 24];

//: Three milestones on the throughput chart. The palette helper is given the
//: real series count so it picks the small, well separated palette.
const THROUGHPUT_SERIES = 3;

export class AccreditationPerformance extends Component {
    static template = "dma_accreditation.AccreditationPerformance";
    static components = { Layout };
    static props = { ...standardActionServiceProps };

    // Only literal _t() calls reach the .pot, so the labels live in a lookup.
    static labels = {
        period: _t("Period"),
        months: _t("months"),
        onTime: _t("Within target"),
        overdue: _t("Overdue now"),
        escalated: _t("Escalated"),
        cycle: _t("Median end to end"),
        cycleHint: _t("Submission to operational accreditation"),
        stages: _t("Where the time goes"),
        stagesHint: _t("Median wait per step, over the period. The bar is the median; p90 is the tail."),
        median: _t("median"),
        p90: _t("p90"),
        files: _t("files"),
        waitingNow: _t("waiting now"),
        overdueNow: _t("overdue"),
        thin: _t("too few files to be a figure"),
        throughput: _t("Files by month"),
        throughputHint: _t("Submitted, office accreditation granted, operational accreditation granted."),
        showData: _t("Show the numbers"),
        hideData: _t("Hide the numbers"),
        month: _t("Month"),
        submitted: _t("Submitted"),
        officeGranted: _t("Office accreditation"),
        authorized: _t("Operational accreditation"),
        bottlenecks: _t("Bottlenecks"),
        slowest: _t("Longest median wait"),
        latest: _t("Highest overdue rate"),
        busiest: _t("Largest backlog"),
        workload: _t("Department workload"),
        holding: _t("Holding"),
        completed: _t("Completed"),
        medianAction: _t("Median action time"),
        rework: _t("Returns and rework"),
        returnsByStep: _t("Returned from"),
        repeatOffenders: _t("Returned more than once"),
        noRework: _t("No file was returned in this period."),
        documents: _t("Documentation"),
        pendingReview: _t("Waiting for review"),
        invalid: _t("Rejected as invalid"),
        missing: _t("Recorded as missing"),
        expiring: _t("Expiring soon"),
        expired: _t("Expired"),
        replaced: _t("Replaced at least once"),
        blockedRequests: _t("Files blocked by their documentation"),
        worstDocuments: _t("Most often blocking"),
        noBlocked: _t("No file is held up by its paperwork."),
        cycleOffice: _t("Submission to office accreditation"),
        cycleOperational: _t("Office to operational accreditation"),
        cycleOverall: _t("Submission to operational accreditation"),
        cycleTimes: _t("Cycle times"),
        open: _t("Open"),
        empty: _t("Nothing to show yet."),
        chartLabel: _t("Accreditation files submitted and granted, by month"),
    };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.canvasRef = useRef("throughput");
        this.chart = null;
        this.state = useState({
            months: 12,
            loading: true,
            showTable: false,
            performance: null,
            sla: null,
            documents: null,
        });

        onWillStart(async () => {
            // Chart.js is a lazy bundle in Odoo and is reached through the
            // global it defines, exactly as the core graph view does.
            await loadBundle("web.chartjs_lib");
            await this.load();
        });
        useEffect(() => this.renderChart());
        onWillUnmount(() => this.destroyChart());
    }

    get label() {
        return AccreditationPerformance.labels;
    }

    get periods() {
        return PERIODS;
    }

    get data() {
        return this.state.performance;
    }

    /** The two live counters the headline shows.
     *
     * Read here rather than in the template: an expression with a callback in
     * it is harder to read on a page than a named getter, and the template
     * stays a layout.
     */
    slaCount(key) {
        const counts = this.state.sla ? this.state.sla.counts : [];
        const entry = counts.find((item) => item.key === key);
        return entry ? entry.count : 0;
    }

    get overdueCount() {
        return this.slaCount("overdue") + this.slaCount("escalated");
    }

    get escalatedCount() {
        return this.slaCount("escalated");
    }

    async load() {
        this.state.loading = true;
        const today = new Date();
        const from = new Date(today);
        from.setMonth(from.getMonth() - this.state.months);
        const iso = (date) => date.toISOString().slice(0, 10);
        const [performance, sla, documents] = await Promise.all([
            this.orm.call("dma.accreditation.request", "get_process_performance_data", [], {
                date_from: iso(from),
                date_to: iso(today),
            }),
            this.orm.call("dma.accreditation.request", "get_sla_dashboard_data", []),
            this.orm.call("dma.accreditation.request", "get_document_health_data", []),
        ]);
        this.state.performance = performance;
        this.state.sla = sla;
        this.state.documents = documents;
        this.state.loading = false;
    }

    async setPeriod(months) {
        this.state.months = months;
        await this.load();
    }

    toggleTable() {
        this.state.showTable = !this.state.showTable;
    }

    // ------------------------------------------------------------------
    // Drill-through
    // ------------------------------------------------------------------
    openRequests(title, domain) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: title,
            res_model: "dma.accreditation.request",
            views: [[false, "list"], [false, "form"]],
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

    openEvidence(domain) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: this.label.documents,
            res_model: "dma.request.document",
            views: [[false, "list"], [false, "form"]],
            domain,
            target: "current",
        });
    }

    // ------------------------------------------------------------------
    // The one chart
    // ------------------------------------------------------------------
    destroyChart() {
        if (this.chart) {
            this.chart.destroy();
            this.chart = null;
        }
    }

    get chartRows() {
        const throughput = this.data?.throughput;
        if (!throughput) {
            return [];
        }
        return throughput.months.map((month, index) => ({
            month,
            submitted: throughput.series.submitted[index],
            office: throughput.series.office_granted[index],
            authorized: throughput.series.authorized[index],
        }));
    }

    renderChart() {
        this.destroyChart();
        const throughput = this.data?.throughput;
        if (!this.canvasRef.el || !throughput || !throughput.months.length) {
            return;
        }
        const scheme = cookie.get("color_scheme");
        const ink = getCustomColor(scheme, "#111827", "#ffffff");
        const grid = getCustomColor(scheme, "rgba(0,0,0,.08)", "rgba(255,255,255,.12)");
        const rtl = Boolean(this.data.rtl);

        // Three series, three hues taken in fixed order from Odoo's own
        // palette: the colour belongs to the milestone, so filtering or
        // changing the period never repaints them.
        const series = [
            { key: "submitted", label: this.label.submitted },
            { key: "office_granted", label: this.label.officeGranted },
            { key: "authorized", label: this.label.authorized },
        ].map((entry, index) => {
            const color = getColor(index, scheme, THROUGHPUT_SERIES);
            return {
                label: entry.label,
                data: throughput.series[entry.key],
                borderColor: color,
                backgroundColor: color,
                borderWidth: 2,
                pointRadius: 4,
                pointHoverRadius: 6,
                pointBorderWidth: 2,
                // A 2px ring of the surface, so two markers that land on the
                // same value stay two markers.
                pointBorderColor: getCustomColor(scheme, "#ffffff", "#1c1c1c"),
                tension: 0.25,
                fill: false,
            };
        });

        this.chart = new Chart(this.canvasRef.el, {
            type: "line",
            data: { labels: throughput.months, datasets: series },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                // Half a month label of room at each end: without it Chart.js
                // draws the first and last tick label off the canvas and the
                // reader loses the two months that matter most.
                layout: { padding: { left: 28, right: 28 } },
                interaction: { mode: "index", intersect: false },
                scales: {
                    x: {
                        // Arabic reads right to left, and so does its time axis.
                        reverse: rtl,
                        grid: { display: false },
                        border: { color: grid },
                        ticks: { color: ink, maxRotation: 0, autoSkipPadding: 12 },
                    },
                    y: {
                        // The value axis sits on the side the reader starts
                        // from, which is the right one in Arabic.
                        position: rtl ? "right" : "left",
                        beginAtZero: true,
                        // One axis. Every series here is a count of files.
                        grid: { color: grid, drawTicks: false },
                        border: { display: false },
                        ticks: { color: ink, precision: 0 },
                    },
                },
                plugins: {
                    legend: {
                        display: true,
                        position: "bottom",
                        align: "start",
                        rtl,
                        labels: {
                            color: ink,
                            boxWidth: 10,
                            boxHeight: 10,
                            usePointStyle: true,
                            pointStyle: "circle",
                        },
                    },
                    tooltip: { rtl, textDirection: rtl ? "rtl" : "ltr" },
                },
            },
        });
    }
}

registry.category("actions").add("dma_accreditation_performance", AccreditationPerformance);
