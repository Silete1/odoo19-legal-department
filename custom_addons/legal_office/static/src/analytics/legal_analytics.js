import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Layout } from "@web/search/layout";
import { cookie } from "@web/core/browser/cookie";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";
import { _t } from "@web/core/l10n/translation";

import { LegalChart } from "@legal_procedure/components/chart/legal_chart";

/**
 * التقارير والتحليلات - the management reporting workspace.
 *
 * Deliberately a different screen from My Office and deliberately built the
 * other way round. My Office is HTML with no canvas on it, because work is
 * clicked through and closed. This screen is charts, because the questions it
 * answers - is the queue growing, is turnaround slipping, where does work pile
 * up - are shape questions that a list cannot answer at a glance.
 *
 * Three things keep it from becoming decoration.
 *
 * **Every panel opens with its question, in words.** The heading above each
 * chart is not "Requests by department", it is "Which departments generate the
 * legal work?". A panel whose question cannot be written has no business
 * being drawn.
 *
 * **Every panel carries its figures as a table** - the same numbers, each row
 * a link onto the records behind it. The table is the panel's real content;
 * the canvas summarises it. That is what makes every figure drillable, what a
 * screen reader reads, what prints, and what a manager who wanted the number
 * rather than the sweep actually needed.
 *
 * **Chart.js is loaded lazily and only here.** It lives in Odoo's own
 * ``web.chartjs_lib`` bundle, which ``LegalChart`` pulls in on mount, so My
 * Office - the screen everybody opens forty times a day - never pays for a
 * charting library it does not draw with.
 */
export class LegalAnalytics extends Component {
    static template = "legal_office.LegalAnalytics";
    static path = "legal-analytics";
    static components = { Layout, LegalChart };
    static props = { ...standardActionServiceProps };

    static labels = {
        loading: _t("Reading the registers…"),
        errorTitle: _t("The analytics could not be built."),
        errorHint: _t("The server could not be reached, or it reported an error."),
        permissionTitle: _t("You do not have permission to open this screen."),
        permissionHint: _t("Ask the legal manager for a role in the Legal Department."),
        retry: _t("Try again"),
        period: _t("Period"),
        figures: _t("The figures"),
        openRecords: _t("Open the records behind this figure"),
        degraded: _t("Part of this screen is unavailable:"),
        total: _t("Total"),
        empty: _t("Nothing recorded in this period."),
    };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ data: null, months: 12, error: null, busy: false });
        if (this.env.config && this.env.config.setDisplayName) {
            this.env.config.setDisplayName(this.props.action.name || _t("Legal Analytics"));
        }
        onWillStart(() => this.load());
    }

    async load(months) {
        this.state.busy = true;
        this.state.error = null;
        try {
            const value = months || this.state.months;
            this.state.data = await this.orm.call(
                "legal.analytics", "get_analytics_data", [value]);
            this.state.months = value;
        } catch (error) {
            const name =
                (error && error.exceptionName) ||
                (error && error.data && error.data.name) || "";
            const permission = name === "odoo.exceptions.AccessError";
            this.state.error = {
                permission,
                title: permission ? this.label.permissionTitle : this.label.errorTitle,
                hint: permission ? this.label.permissionHint : this.label.errorHint,
            };
        } finally {
            this.state.busy = false;
        }
    }

    get label() {
        return LegalAnalytics.labels;
    }

    get data() {
        return this.state.data;
    }

    /** Light or dark steps of the same validated palette, never an auto-flip. */
    get palette() {
        const mode = cookie.get("color_scheme") === "dark" ? "dark" : "light";
        return this.data.palette[mode];
    }

    colourOf(key) {
        return this.palette[key] || this.palette.a;
    }

    doAction(action) {
        if (action) {
            this.action.doAction(action);
        }
    }

    /**
     * Chart.js config per panel form.
     *
     * Marks are thin, the grid is a hairline on the value axis only, and no
     * chart carries a number on every point - the table beneath does that,
     * exactly, and without collisions.
     */
    chartData(panel) {
        return {
            labels: panel.labels,
            datasets: panel.series.map((series) => ({
                label: series.label,
                data: series.data,
                backgroundColor: this.colourOf(series.colour),
                borderColor: this.colourOf(series.colour),
                borderWidth: panel.chart === "line" ? 2 : 0,
                borderRadius: panel.chart === "line" ? 0 : 4,
                borderSkipped: false,
                // A 2px surface gap between adjacent fills, so touching bars
                // and stack segments read as separate marks rather than one.
                barPercentage: 0.78,
                categoryPercentage: 0.82,
                pointRadius: panel.chart === "line" ? 3 : 0,
                pointHoverRadius: panel.chart === "line" ? 5 : 0,
                tension: 0.25,
                fill: false,
            })),
        };
    }

    chartType(panel) {
        return panel.chart === "line" ? "line" : "bar";
    }

    chartOptions(panel) {
        const horizontal = panel.chart === "hbar";
        const stacked = panel.chart === "stacked";
        const rtl = Boolean(this.data.rtl);

        // Which axis carries the measure depends on the orientation, and
        // getting it wrong is not cosmetic: an integer count drawn against a
        // value axis that was never told `precision: 0` gets ticks reading
        // 0.1, 0.2 … 1.0, which is a chart claiming a tenth of a contract.
        const valueAxis = {
            stacked,
            beginAtZero: true,
            ticks: { precision: 0 },
            grid: { display: true, drawBorder: false },
            // In Arabic the measure grows from the inline start, which is the
            // right-hand edge. Chart.js has no notion of direction of its own.
            reverse: rtl && horizontal,
            position: rtl && !horizontal ? "right" : undefined,
        };
        const categoryAxis = {
            stacked,
            grid: { display: false, drawBorder: false },
            ticks: { autoSkip: !horizontal, maxRotation: 0 },
            reverse: rtl && !horizontal,
            position: rtl && horizontal ? "right" : undefined,
        };

        return {
            indexAxis: horizontal ? "y" : "x",
            plugins: {
                legend: { display: panel.series.length > 1, position: "bottom" },
            },
            scales: horizontal
                ? { x: valueAxis, y: categoryAxis }
                : { x: categoryAxis, y: valueAxis },
            onClick: (event, elements) => {
                if (!elements || !elements.length) {
                    return;
                }
                const row = panel.rows[elements[0].index];
                if (row && row.action) {
                    this.doAction(row.action);
                }
            },
        };
    }

    /** The bar behind a table row: its share of the panel's largest value. */
    percentOf(panel, row) {
        const peak = Math.max(...panel.rows.map((item) => item.value || 0), 1);
        return Math.round((100 * (row.value || 0)) / peak);
    }

    chartHeight(panel) {
        // Horizontal bars need vertical room per category; everything else is
        // a fixed band, so a screen of panels keeps one rhythm.
        return panel.chart === "hbar"
            ? Math.max(180, 34 * (panel.rows.length || 1) + 40)
            : 240;
    }
}

registry.category("actions").add("legal_analytics", LegalAnalytics);
