"""Screenshot + console harness for the Legal Affairs backend.

Odoo's bus keeps a long-poll open forever, so ``wait_until="networkidle"``
never resolves against a logged-in web client. Every wait here is therefore an
explicit selector wait with a bounded timeout, which is both faster and the
only thing that actually works.

Usage::

    python scripts/legal_ui_capture.py OUTDIR [--roles clerk,officer]
                                              [--screens desk,deadlines]
                                              [--viewports 1366x768,1440x900]
                                              [--full]

Writes ``<outdir>/<role>__<screen>__<w>x<h>.png`` plus ``report.json`` holding
the console errors, page errors and layout metrics collected per role.
"""

import argparse
import asyncio
import json
import os
import sys

from playwright.async_api import async_playwright

URL = os.environ.get("LEGAL_URL", "http://localhost:8090")
DB = os.environ.get("LEGAL_DB", "legal_dept")
PASSWORD = os.environ.get("LEGAL_PASSWORD", "Legal#2026")

ROLES = {
    "clerk": ("clerk@legal.iq", PASSWORD),
    "officer": ("officer@legal.iq", PASSWORD),
    "approver": ("approver@legal.iq", PASSWORD),
    "manager": ("manager@legal.iq", PASSWORD),
    "auditor": ("auditor@legal.iq", PASSWORD),
    "admin": ("admin", os.environ.get("LEGAL_ADMIN_PASSWORD", "admin")),
}

# Path fragments appended to the origin. Client actions carry a `static path`
# and are addressable directly; everything else goes through /odoo/action-.
SCREENS = {
    # مكتبي keeps the URL it always had; only what it renders changed.
    "office": "/odoo/legal-desk",
    "govdesks": "/odoo/gov-desks",
    "analytics": "/odoo/legal-analytics",
    "mailroom": "/odoo/action-legal_correspondence.action_legal_correspondence_mail_room",
    "cases": "/odoo/action-legal_procedure.action_legal_case",
    "requests": "/odoo/action-legal_request.action_legal_request",
    "contracts": "/odoo/action-legal_contract.action_legal_contract",
    "lawsuits": "/odoo/action-legal_litigation.action_legal_lawsuit",
    "hearings": "/odoo/action-legal_litigation.action_legal_hearing",
    "opinions": "/odoo/action-legal_opinion.action_legal_opinion",
    "register": "/odoo/action-legal_correspondence.action_legal_register",
    "deadlines": "/odoo/action-legal_deadline.action_legal_deadline",
    "documents": "/odoo/action-legal_core.action_legal_document",
    "poas": "/odoo/action-legal_procedure.action_legal_poa",
    "reports": "/odoo/action-legal_reports.action_legal_reports_case",
}

# Any one of these means "the web client has painted something real".
READY = ".o_legal_office, .o_legal_body, .o_list_renderer, .o_kanban_renderer, " \
        ".o_form_view, .o_calendar_view, .o_graph_renderer, .o_pivot, .o_nocontent_help"

METRICS_JS = """() => {
  const q = s => Array.from(document.querySelectorAll(s));
  const box = e => { const r = e.getBoundingClientRect();
                     return {top: Math.round(r.top), h: Math.round(r.height),
                             w: Math.round(r.width)}; };
  const root = document.querySelector('.o_legal_office, .o_legal_body');
  const txt = e => (e.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 60);
  return {
    scrollHeight: document.documentElement.scrollHeight,
    dir: root ? root.getAttribute('dir') : null,
    band: root ? root.getAttribute('data-band') : null,
    sections: q('.o_legal_band_head, .o_legal_section__head').map(
        e => ({title: txt(e), ...box(e)})),
    cards: q('.o_legal_card, .o_legal_panel').length,
    tiles: q('.o_legal_kpi, .o_legal_tile, .o_legal_signal').length,
    queueRows: q('.o_legal_queue__row, .o_legal_worklist tbody tr').length,
    agendaRows: q('.o_legal_agenda__row').length,
    attention: q('.o_legal_attention_item, .o_legal_signal').map(txt),
    hero: (() => { const e = document.querySelector('.o_legal_hero'); return e ? box(e) : null; })(),
    firstQueue: (() => { const e = document.querySelector('.o_legal_queue, .o_legal_worklist');
                         return e ? box(e) : null; })(),
    rtlLeak: q('[style*="margin-left"], [style*="padding-left"]').length,
  };
}"""


async def capture(role, login, password, screens, viewports, outdir, full, report):
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(
            viewport={"width": viewports[0][0], "height": viewports[0][1]},
            locale="ar",
        )
        page = await ctx.new_page()
        seen = report[role]["console"]
        page.on("console", lambda m: seen.append(f"{m.type}: {m.text[:300]}")
                if m.type in ("error",) else None)
        page.on("pageerror", lambda e: seen.append(f"pageerror: {str(e)[:300]}"))

        # The server hosts several databases, so a bare /web/login lands on the
        # database manager and the real form never becomes visible. Naming the
        # database on the query string binds the session before the form paints.
        await page.goto(f"{URL}/web/login?db={DB}", wait_until="domcontentloaded",
                        timeout=60000)
        await page.wait_for_selector("input[name=login]:visible", timeout=30000)
        await page.fill("input[name=login]", login)
        await page.fill("input[name=password]", password)
        await page.click("button[type=submit]")
        await page.wait_for_selector(".o_main_navbar", timeout=60000)

        for screen in screens:
            path = SCREENS[screen]
            try:
                await page.goto(f"{URL}{path}", wait_until="domcontentloaded", timeout=60000)
                await page.wait_for_selector(READY, timeout=45000)
                await page.wait_for_timeout(1600)
            except Exception as exc:  # noqa: BLE001 - recorded, not raised
                report[role].setdefault("errors", []).append(f"{screen}: {exc!r}"[:300])
                continue
            for width, height in viewports:
                await page.set_viewport_size({"width": width, "height": height})
                await page.wait_for_timeout(700)
                name = f"{role}__{screen}__{width}x{height}.png"
                await page.screenshot(path=os.path.join(outdir, name))
            if full:
                await page.set_viewport_size({"width": viewports[0][0],
                                              "height": viewports[0][1]})
                await page.wait_for_timeout(500)
                await page.screenshot(path=os.path.join(outdir, f"{role}__{screen}__full.png"),
                                      full_page=True)
            try:
                report[role]["metrics"][screen] = await page.evaluate(METRICS_JS)
            except Exception as exc:  # noqa: BLE001
                report[role]["metrics"][screen] = {"error": repr(exc)[:200]}

        await ctx.close()
        await browser.close()


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("outdir")
    parser.add_argument("--roles", default="clerk,officer,approver,manager,auditor,admin")
    parser.add_argument("--screens", default="office")
    parser.add_argument("--viewports", default="1440x900,1366x768,1920x1080")
    parser.add_argument("--full", action="store_true")
    args = parser.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    roles = [r.strip() for r in args.roles.split(",") if r.strip()]
    screens = [s.strip() for s in args.screens.split(",") if s.strip()]
    viewports = []
    for chunk in args.viewports.split(","):
        w, _, h = chunk.strip().partition("x")
        viewports.append((int(w), int(h)))

    unknown = [s for s in screens if s not in SCREENS]
    if unknown:
        sys.exit(f"unknown screens: {unknown}")

    report = {}
    for role in roles:
        login, password = ROLES[role]
        report[role] = {"console": [], "metrics": {}}
        try:
            await capture(role, login, password, screens, viewports,
                          args.outdir, args.full, report)
        except Exception as exc:  # noqa: BLE001
            report[role]["fatal"] = repr(exc)[:400]

    with open(os.path.join(args.outdir, "report.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=1)

    for role, data in report.items():
        errs = len(data.get("console", [])) + len(data.get("errors", []))
        print(f"{role}: {len(data.get('metrics', {}))} screens, {errs} console/nav errors"
              + (f"  FATAL {data['fatal']}" if "fatal" in data else ""))


asyncio.run(main())
