import { Component, onWillStart, useEffect, useRef } from "@odoo/owl";
import { loadBundle } from "@web/core/assets";
import { cookie } from "@web/core/browser/cookie";
import { getCustomColor } from "@web/core/colors/colors";

/**
 * One Chart.js canvas, wrapped so the rest of the workspace never touches the
 * library directly.
 *
 * Chart.js ships with Odoo but in a lazy bundle, so it is loaded on demand
 * rather than added to `web.assets_backend` - a workspace that draws three
 * charts should not make every other screen in the database carry the library.
 *
 * The component owns three things the callers should not have to remember:
 *
 *  - the lifecycle. A canvas that already holds a chart throws
 *    "Canvas is already in use" on the next `new Chart`, so the old one is
 *    destroyed first and again when the component goes away.
 *  - the theme. Grid lines, ticks and legend text are not part of the data and
 *    must come from Odoo's own light/dark pair rather than being hard-coded.
 *  - the direction. Chart.js has no RTL detection of its own: its legend and
 *    tooltip lay out left-to-right unless told otherwise, which is wrong on
 *    every Arabic screen in this module.
 *
 * A canvas says nothing to a screen reader, so `ariaLabel` is required and the
 * caller is expected to render the same figures as text somewhere near it.
 */
export class DmaChart extends Component {
    static template = "dma_accreditation.DmaChart";
    static props = {
        type: { type: String },
        data: { type: Object },
        options: { type: Object, optional: true },
        ariaLabel: { type: String },
        rtl: { type: Boolean, optional: true },
        height: { type: Number, optional: true },
    };
    static defaultProps = { options: {}, rtl: false, height: 260 };

    setup() {
        this.canvasRef = useRef("canvas");
        this.chart = null;
        this.colorScheme = cookie.get("color_scheme");

        onWillStart(() => loadBundle("web.chartjs_lib"));

        useEffect(
            () => {
                this.render_();
                return () => this.destroy_();
            },
            () => [this.props.type, this.props.data, this.props.options],
        );
    }

    destroy_() {
        if (this.chart) {
            this.chart.destroy();
            this.chart = null;
        }
    }

    /** Odoo's own ink for chart furniture, in whichever theme is active. */
    get theme() {
        const scheme = this.colorScheme;
        return {
            ink: getCustomColor(scheme, "#111827", "#E4E4E4"),
            muted: getCustomColor(scheme, "#6b7280", "#A9ACB6"),
            grid: getCustomColor(scheme, "rgba(0,0,0,.08)", "rgba(255,255,255,.12)"),
            tooltipBg: getCustomColor(scheme, "rgba(17,24,39,.92)", "rgba(15,17,26,.94)"),
            tooltipInk: getCustomColor(scheme, "#ffffff", "#E4E4E4"),
        };
    }

    /**
     * Defaults every chart in the workspace shares, merged under whatever the
     * caller passes so a panel can still override any single option.
     */
    get config() {
        const t = this.theme;
        const rtl = this.props.rtl;
        const base = {
            responsive: true,
            // The wrapper sets the height; letting Chart.js keep a ratio makes
            // it grow without bound inside a flex parent.
            maintainAspectRatio: false,
            animation: { duration: 420 },
            plugins: {
                legend: {
                    display: false,
                    rtl,
                    textDirection: rtl ? "rtl" : "ltr",
                    labels: {
                        color: t.ink,
                        boxWidth: 10,
                        boxHeight: 10,
                        usePointStyle: true,
                        pointStyle: "rectRounded",
                        padding: 14,
                    },
                },
                tooltip: {
                    rtl,
                    textDirection: rtl ? "rtl" : "ltr",
                    backgroundColor: t.tooltipBg,
                    titleColor: t.tooltipInk,
                    bodyColor: t.tooltipInk,
                    borderWidth: 0,
                    padding: 10,
                    cornerRadius: 4,
                    displayColors: true,
                    boxWidth: 8,
                    boxHeight: 8,
                    usePointStyle: true,
                },
            },
        };
        return {
            type: this.props.type,
            data: this.props.data,
            options: this.merge_(base, this.props.options || {}),
        };
    }

    /** Deep merge, so a caller can set one nested option without losing the rest. */
    merge_(base, extra) {
        const out = { ...base };
        for (const [key, value] of Object.entries(extra)) {
            const isPlain = (v) =>
                v && typeof v === "object" && !Array.isArray(v) && !(v instanceof Function);
            out[key] = isPlain(value) && isPlain(out[key])
                ? this.merge_(out[key], value)
                : value;
        }
        return out;
    }

    render_() {
        this.destroy_();
        const el = this.canvasRef.el;
        if (!el || typeof Chart === "undefined") {
            return;
        }
        this.chart = new Chart(el, this.config);
    }
}
