# Part of the DMA Accreditation module. See LICENSE file for full copyright and licensing details.
"""Demo helper.

The demo files could set ``state`` directly, but then the approval log, the
chatter and the activities of the demo records would be empty and the module
would demo badly. Instead the demo data drives the *real* workflow methods,
each one impersonating the department that owns the step, so a freshly
installed demo database looks exactly like one that has been used.

This module is loaded in every database but the method below only ever runs
when the demo data file calls it.
"""
import logging
import random
from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models

from .dma_constants import MAIN_PATH_STATES

_logger = logging.getLogger(__name__)

#: Demining organisations behind the generated caseload. Fictional, but named
#: the way real applicants to a national mine action authority are named.
DEMO_ORGS = [
    ("Al-Amal Demining Company", "Baghdad"),
    ("Sanad Mine Action Services", "Basra"),
    ("Nahrain Clearance Group", "Mosul"),
    ("Dijla Explosive Ordnance Disposal", "Baghdad"),
    ("Furat Survey and Clearance", "Najaf"),
    ("Zagros Demining Foundation", "Erbil"),
    ("Babil Battle Area Clearance", "Hilla"),
    ("Karbala Risk Education Initiative", "Karbala"),
    ("Anbar Mine Action Team", "Ramadi"),
    ("Kirkuk Technical Survey Unit", "Kirkuk"),
    ("Maysan Humanitarian Demining", "Amarah"),
    ("Salah al-Din Clearance Services", "Tikrit"),
]

#: How long a file typically waits at each step, in hours (low, high). These
#: are what give the cycle-time chart its shape, so they are set to the two
#: places a real accreditation actually stalls: the prerequisites check, and
#: the Accreditation Committee, which only sits every few weeks.
DEMO_STEP_HOURS = {
    "draft": (18, 120),
    "submitted": (2, 20),
    "gd_review": (20, 96),
    "legal_review": (36, 168),
    "cert_check": (72, 360),
    "office_granted": (96, 600),
    "sop_submission": (48, 240),
    "sop_fee": (20, 120),
    "dual_confirm": (48, 200),
    "demo_fee": (72, 336),
    "committee": (168, 780),
    "legal_refine": (20, 120),
}


class DmaAccreditationRequest(models.Model):
    _inherit = "dma.accreditation.request"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _demo_as(self, xmlid):
        """Return this request in the environment of a demo user."""
        user = self.env.ref(xmlid)
        return self.with_user(user)

    def _demo_accept_documents(self, limit=None):
        """Mark checklist lines as provided and accepted, oldest first."""
        lines = self.document_ids.sorted("sequence")
        if limit is not None:
            lines = lines[:limit]
        lines.write({"is_provided": True, "review_result": "accepted"})

    def _demo_add_fee(self, fee_type, receipt_number, confirm=True):
        """Register a fee as the Finance Department, which owns that model."""
        finance = self.env.ref("dma_accreditation.demo_user_finance")
        fee = self.env["dma.fee.payment"].with_user(finance).create({
            "request_id": self.id,
            "fee_type": fee_type,
            "receipt_number": receipt_number,
            "receipt_date": fields.Date.context_today(self),
        })
        if confirm:
            fee.action_confirm()
        return fee

    # ------------------------------------------------------------------
    # Demo scenario
    # ------------------------------------------------------------------
    @api.model
    def _load_demo_workflow(self):
        """Drive the demo requests through the workflow as the real roles."""
        ref = self.env.ref
        reception = "dma_accreditation.demo_user_reception"
        gd = "dma_accreditation.demo_user_general_director"
        legal = "dma_accreditation.demo_user_legal"
        cert = "dma_accreditation.demo_user_cert"
        operations = "dma_accreditation.demo_user_operations"
        committee = "dma_accreditation.demo_user_committee"

        scopes = {
            "manual": ref("dma_accreditation.scope_manual_clearance"),
            "bac": ref("dma_accreditation.scope_bac"),
            "eod": ref("dma_accreditation.scope_eod"),
            "nts": ref("dma_accreditation.scope_non_technical_survey"),
            "eore": ref("dma_accreditation.scope_eore"),
            "ts": ref("dma_accreditation.scope_technical_survey"),
        }

        def new_request(xmlid, partner_xmlid, contact_xmlid, scope_keys, request_type="new"):
            request = self.with_user(ref(reception)).create({
                "partner_id": ref(partner_xmlid).id,
                "contact_partner_id": ref(contact_xmlid).id,
                "request_type": request_type,
                "scope_ids": [(6, 0, [scopes[key].id for key in scope_keys])],
            })
            self.env["ir.model.data"]._update_xmlids([{
                "xml_id": f"dma_accreditation.{xmlid}",
                "record": request,
                "noupdate": True,
            }])
            return request

        # -- 1. A brand new file still on the desk of the reception ------
        new_request(
            "demo_request_draft", "dma_accreditation.demo_partner_alamal",
            "dma_accreditation.demo_partner_alamal_contact",
            ["manual", "eod"], request_type="renewal",
        )

        # -- 2. A file blocked on the prerequisites checklist ------------
        blocked = new_request(
            "demo_request_cert_check", "dma_accreditation.demo_partner_alamal",
            "dma_accreditation.demo_partner_alamal_contact",
            ["manual", "bac", "eod"],
        )
        blocked._demo_as(reception).action_submit()
        blocked._demo_as(reception).action_send_to_general_director()
        blocked._demo_as(gd).action_gd_accept()
        blocked._demo_as(legal).action_legal_approve()
        # Only part of the checklist is accepted: the office accreditation
        # stays blocked, which is exactly what the hard gate is for.
        blocked._demo_as(cert)._demo_accept_documents(limit=7)

        # -- 3. A file waiting for the second signature of the dual step -
        dual = new_request(
            "demo_request_dual_confirm", "dma_accreditation.demo_partner_sanad",
            "dma_accreditation.demo_partner_sanad_contact",
            ["bac", "nts", "eore"],
        )
        dual._demo_as(reception).action_submit()
        dual._demo_as(reception).action_send_to_general_director()
        dual._demo_as(gd).action_gd_accept()
        dual._demo_as(legal).action_legal_approve()
        dual._demo_as(cert)._demo_accept_documents()
        dual._demo_as(cert).action_grant_office_accreditation()
        dual._demo_as(operations).action_start_operational_phase()
        dual.sudo().write({
            "sop_reference": "SANAD-SOP-2026",
            "sop_version": "3.1",
            "sop_attachment_ids": [(6, 0, self._demo_attachment(
                dual, "Sanad-SOP-v3.1.pdf",
            ).ids)],
        })
        dual._demo_as(operations).action_register_paper_sop()
        dual._demo_as(operations).action_sop_received()
        dual._demo_add_fee("sop_reading", "REC/2026/0141")
        dual._demo_as("dma_accreditation.demo_user_finance").action_sop_fee_registered()
        # Finance signed off, Operations has not: the dual gate is visible.
        dual._demo_as("dma_accreditation.demo_user_finance").action_finance_confirm()

        # -- 4. A fully accredited organisation --------------------------
        done = new_request(
            "demo_request_authorized", "dma_accreditation.demo_partner_nahrain",
            "dma_accreditation.demo_partner_nahrain_contact",
            ["manual", "ts", "nts"],
        )
        done._demo_as(reception).action_submit()
        done._demo_as(reception).action_send_to_general_director()
        done._demo_as(gd).action_gd_accept()
        done._demo_as(legal).action_legal_approve()
        done._demo_as(cert)._demo_accept_documents()
        done._demo_as(cert).action_grant_office_accreditation()
        done._demo_as(operations).action_start_operational_phase()
        done.sudo().write({
            "sop_reference": "NAHRAIN-SOP-2026",
            "sop_version": "1.4",
            "sop_attachment_ids": [(6, 0, self._demo_attachment(
                done, "Nahrain-SOP-v1.4.pdf",
            ).ids)],
        })
        done._demo_as(operations).action_register_paper_sop()
        done._demo_as(operations).action_sop_received()
        done._demo_add_fee("sop_reading", "REC/2026/0155")
        done._demo_as("dma_accreditation.demo_user_finance").action_sop_fee_registered()
        done._demo_as("dma_accreditation.demo_user_finance").action_finance_confirm()
        done._demo_as(operations).action_operations_confirm()
        done._demo_as(operations).action_dual_confirm_done()
        done._demo_add_fee("operational_demo", "REC/2026/0162")
        done._demo_as("dma_accreditation.demo_user_finance").action_demo_fee_registered()
        done.sudo().write({
            "committee_decision": "approve",
            "committee_date": fields.Date.context_today(self),
            "decision_text": (
                "<p>The Accreditation Committee approves the operational "
                "accreditation of Nahrain Clearance Group for manual clearance, "
                "technical survey and non-technical survey.</p>"
            ),
        })
        done._demo_as(committee).action_committee_decision()
        done.sudo().write({
            "refined_decision_text": (
                "<p>Pursuant to the decision of the Accreditation Committee and "
                "after legal refinement, the operational accreditation is granted "
                "for a renewable period, subject to the national mine action "
                "standards and to monitoring by the Directorate.</p>"
            ),
        })
        done._demo_as(legal).action_issue_authorization()

        # -- 5. A file returned to the applicant -------------------------
        returned = new_request(
            "demo_request_returned", "dma_accreditation.demo_partner_sanad",
            "dma_accreditation.demo_partner_sanad_contact",
            ["eod"], request_type="amendment",
        )
        returned._demo_as(reception).action_submit()
        returned._demo_as(reception).action_send_to_general_director()
        returned._demo_as(gd).action_return_to_applicant(
            "The organisational structure and the insurance policies attached to "
            "the application are outdated. Please provide the current versions."
        )
        self._load_demo_history()
        _logger.info("DMA accreditation demo workflow loaded")
        return True

    # ------------------------------------------------------------------
    # Generated history
    # ------------------------------------------------------------------
    @api.model
    def _load_demo_history(self):
        """Create a year and a bit of finished and in-flight accreditations.

        Seeded, so two demo databases built from the same commit hold the same
        caseload and a screenshot stays reproducible.
        """
        rng = random.Random(20260830)
        scopes = self.env["dma.accreditation.scope"].search([])
        if not scopes:
            return False

        partners = self._demo_history_partners()
        reception = "dma_accreditation.demo_user_reception"

        # What the caseload is made of. Roughly half the work of a directorate
        # is finished files; the rest is the backlog, spread over the pipeline.
        plan = (
            [("authorized", None)] * 19
            + [("rejected", None)] * 3
            + [("returned", None)] * 5
            + [(state, None) for state in MAIN_PATH_STATES[1:12] for _ in range(2)]
        )
        rng.shuffle(plan)

        # Quiet the chatter machinery: the generated files exist for their
        # numbers, and tracking every one of ~500 transitions would make
        # installing the demo data take minutes.
        maker = self.with_context(
            tracking_disable=True, mail_create_nolog=True, mail_notrack=True,
            # Hundreds of transitions, each of which would otherwise spawn a
            # wkhtmltopdf subprocess for a certificate nobody will read. The
            # five hand-written demo records still generate their real PDFs.
            dma_skip_report_attachment=True,
        )

        created = 0
        for index, (target, _unused) in enumerate(plan):
            partner, contact = partners[index % len(partners)]
            request = maker.with_user(self.env.ref(reception)).create({
                "partner_id": partner.id,
                "contact_partner_id": contact.id,
                "request_type": rng.choice(
                    ["new"] * 6 + ["renewal"] * 3 + ["amendment"]
                ),
                "priority": "1" if rng.random() < 0.15 else "0",
                "scope_ids": [(6, 0, rng.sample(
                    scopes.ids, rng.randint(1, min(3, len(scopes)))
                ))],
            })
            try:
                self._demo_drive_to(request, target, rng)
            except Exception:               # pragma: no cover - demo only
                _logger.warning(
                    "DMA demo history: could not drive %s to %s",
                    request.display_name, target, exc_info=True,
                )
                continue
            self._demo_backdate(request, target, rng)
            created += 1

        _logger.info("DMA accreditation demo history: %s requests", created)
        return True

    @api.model
    def _demo_history_partners(self):
        """The applicant organisations, created once."""
        Partner = self.env["res.partner"]
        pairs = []
        for name, city in DEMO_ORGS:
            company = Partner.search([("name", "=", name)], limit=1)
            if not company:
                company = Partner.create({
                    "name": name, "city": city, "country_id": self.env.ref(
                        "base.iq", raise_if_not_found=False,
                    ).id if self.env.ref("base.iq", raise_if_not_found=False) else False,
                    "is_company": True,
                    "email": "info@%s.example.com" % (
                        name.lower().replace(" ", "-").replace("'", "")
                    ),
                })
            contact = Partner.search(
                [("parent_id", "=", company.id)], limit=1,
            ) or Partner.create({
                "name": "%s Liaison Officer" % name.split()[0],
                "parent_id": company.id,
                "email": "liaison@%s.example.com" % (
                    name.lower().replace(" ", "-").replace("'", "")
                ),
                "phone": "+964 770 000 0000",
            })
            pairs.append((company, contact))
        return pairs

    @api.model
    def _demo_drive_to(self, request, target, rng):
        """Replay the real workflow until the file reaches ``target``."""
        reception = "dma_accreditation.demo_user_reception"
        gd = "dma_accreditation.demo_user_general_director"
        legal = "dma_accreditation.demo_user_legal"
        cert = "dma_accreditation.demo_user_cert"
        operations = "dma_accreditation.demo_user_operations"
        finance = "dma_accreditation.demo_user_finance"
        committee = "dma_accreditation.demo_user_committee"

        # A returned or rejected file is one that travelled part of the way and
        # then stopped, so pick where it stopped before replaying.
        if target in ("returned", "rejected"):
            halt = rng.choice(
                ["gd_review", "legal_review", "cert_check", "sop_fee", "committee"]
            )
        else:
            halt = target

        order = MAIN_PATH_STATES
        stop = order.index(halt)

        def reached(state):
            return order.index(state) <= stop

        if not reached("submitted"):
            return
        request._demo_as(reception).action_submit()
        if not reached("gd_review"):
            return
        request._demo_as(reception).action_send_to_general_director()
        if not reached("legal_review"):
            return self._demo_halt(request, target, gd, rng)
        request._demo_as(gd).action_gd_accept()
        if not reached("cert_check"):
            return self._demo_halt(request, target, legal, rng)
        request._demo_as(legal).action_legal_approve()
        if not reached("office_granted"):
            # A file stopped at the check has a partly done checklist, which is
            # what makes the blocked-cases panel show something real.
            request._demo_as(cert)._demo_accept_documents(
                limit=rng.randint(3, max(3, request.required_document_count - 1)),
            )
            return self._demo_halt(request, target, cert, rng)
        request._demo_as(cert)._demo_accept_documents()
        request._demo_as(cert).action_grant_office_accreditation()
        if not reached("sop_submission"):
            return self._demo_halt(request, target, operations, rng)
        request._demo_as(operations).action_start_operational_phase()
        if not reached("sop_fee"):
            return self._demo_halt(request, target, operations, rng)
        request.sudo().write({
            "sop_reference": "%s-SOP-%s" % (
                request.partner_id.name.split()[0].upper(), 2025 + rng.randint(0, 1),
            ),
            "sop_version": "%s.%s" % (rng.randint(1, 3), rng.randint(0, 9)),
            "sop_attachment_ids": [(6, 0, self._demo_attachment(
                request, "%s-SOP.pdf" % request.partner_id.name.split()[0],
            ).ids)],
        })
        request._demo_as(operations).action_register_paper_sop()
        request._demo_as(operations).action_sop_received()
        if not reached("dual_confirm"):
            return self._demo_halt(request, target, finance, rng)
        request._demo_add_fee("sop_reading", "REC/H/%s/A" % request.id)
        request._demo_as(finance).action_sop_fee_registered()
        if not reached("demo_fee"):
            # Half the files parked on the dual confirmation have one of the
            # two signatures already, which is the case the panel exists for.
            if rng.random() < 0.5:
                request._demo_as(finance).action_finance_confirm()
            return self._demo_halt(request, target, finance, rng)
        request._demo_as(finance).action_finance_confirm()
        request._demo_as(operations).action_operations_confirm()
        request._demo_as(operations).action_dual_confirm_done()
        if not reached("committee"):
            return self._demo_halt(request, target, finance, rng)
        request._demo_add_fee("operational_demo", "REC/H/%s/B" % request.id)
        request._demo_as(finance).action_demo_fee_registered()
        if not reached("legal_refine"):
            return self._demo_halt(request, target, committee, rng)
        request.sudo().write({
            "committee_decision": "approve",
            "committee_date": fields.Date.context_today(request),
            "decision_text": (
                "<p>The Accreditation Committee approves the operational "
                "accreditation of %s.</p>" % request.partner_id.name
            ),
        })
        request._demo_as(committee).action_committee_decision()
        if not reached("authorized"):
            return self._demo_halt(request, target, legal, rng)
        request.sudo().write({
            "refined_decision_text": (
                "<p>Pursuant to the decision of the Accreditation Committee, the "
                "operational accreditation of %s is granted subject to the "
                "national mine action standards.</p>" % request.partner_id.name
            ),
        })
        request._demo_as(legal).action_issue_authorization()
        return True

    @api.model
    def _demo_halt(self, request, target, actor, rng):
        """Close a file that is meant to end as returned or rejected."""
        if target == "returned":
            request._demo_as(actor).action_return_to_applicant(rng.choice([
                "The organisational structure and the insurance policies "
                "attached to the application are outdated.",
                "The prior demining experience has not been evidenced. Please "
                "attach the completion certificates of the two most recent "
                "tasks.",
                "The financial capability statement is missing the auditor's "
                "signature.",
            ]))
        elif target == "rejected":
            request._demo_as(actor).action_reject(rng.choice([
                "The organisation does not hold the insurance cover required "
                "by the national mine action standards.",
                "The submitted standing operating procedures do not meet "
                "TNMA 07.30/01.",
            ]))
        return True

    @api.model
    def _demo_backdate(self, request, target, rng):
        """Move a generated file back in time.

        Done in SQL on purpose. The approval log is immutable by design - the
        model refuses ``write`` outright - and that guard must not grow a
        context escape hatch, because the context is attacker-controlled over
        RPC. The demo loader is the only thing that can reach this method.
        """
        cr = self.env.cr
        lines = request.approval_line_ids.sorted("id")
        if not lines:
            return False

        # An open file must still look open: its last move lands somewhere in
        # the recent past so the backlog has a spread of ages, including a few
        # that are overdue. A closed one is placed anywhere in the last year.
        closed = target in ("authorized", "rejected")
        if closed:
            end = fields.Datetime.now() - timedelta(days=rng.uniform(5, 400))
        else:
            end = fields.Datetime.now() - timedelta(hours=rng.uniform(4, 1400))

        # Walk backwards from the last transition so the file ends where it
        # was placed, then hand each step a plausible duration.
        stamps = []
        when = end
        for line in reversed(lines):
            stamps.append((line.id, when))
            low, high = DEMO_STEP_HOURS.get(line.step, (24, 96))
            when -= timedelta(hours=rng.uniform(low, high))
        created_at = when

        for line_id, stamp in stamps:
            cr.execute(
                "UPDATE dma_approval_line SET date = %s, create_date = %s "
                "WHERE id = %s", (stamp, stamp, line_id),
            )
        # The chatter should agree with the log it describes.
        cr.execute(
            "UPDATE mail_message SET date = %s "
            "WHERE model = 'dma.accreditation.request' AND res_id = %s",
            (created_at, request.id),
        )

        first = dict((line.step, stamp) for line, stamp in zip(lines, [s[1] for s in reversed(stamps)]))
        values = {
            "create_date": created_at,
            "write_date": end,
            "submission_date": (first.get("draft") or created_at).date(),
        }
        if "office_granted" in first or request.office_ref:
            values["office_date"] = (
                first.get("cert_check") or first.get("office_granted") or end
            ).date()
        if target == "authorized":
            issued = end.date()
            months = self.env["ir.config_parameter"].sudo().get_param(
                "dma_accreditation.validity_months", "12",
            )
            values["issue_date"] = issued
            values["expiry_date"] = issued + relativedelta(months=int(months))

        sets = ", ".join('"%s" = %%s' % key for key in values)
        cr.execute(
            'UPDATE dma_accreditation_request SET %s WHERE id = %%s' % sets,
            list(values.values()) + [request.id],
        )
        request.invalidate_recordset()
        return True

    @api.model
    def _demo_attachment(self, request, filename):
        """Create a tiny placeholder attachment so the SOP fields are not empty."""
        return self.env["ir.attachment"].create({
            "name": filename,
            "type": "binary",
            "raw": b"%PDF-1.4\n% Demo placeholder for the DMA accreditation module.\n",
            "mimetype": "application/pdf",
            "res_model": request._name,
            "res_id": request.id,
        })
