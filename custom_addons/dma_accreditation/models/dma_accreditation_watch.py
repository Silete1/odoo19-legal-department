# Part of the DMA Accreditation module. See LICENSE file for full copyright and licensing details.
"""Watching what runs out: evidence, and the accreditation itself.

Two dates matter after a file is closed. The insurance policy behind an
accreditation expires, and the accreditation certificate itself expires. The
module already recorded both; this makes something happen before they do.

What it deliberately does not do
--------------------------------
Nothing here changes the legal status of anything. An accreditation whose
certificate has run out is *reported* as expired and lands on the Accreditation
Manager's desk; it is not silently revoked, and no renewal file is opened on the
Directorate's behalf. Time passing is not a decision, and decisions in this
module are taken by people through the ``action_*`` methods.
"""
import logging

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .dma_constants import CLOSED_STATES, state_label

_logger = logging.getLogger(__name__)

EXPIRY_WARNING_PARAMETER = "dma_accreditation.expiry_warning_days"
EXPIRY_WARNING_DEFAULT = 90


class DmaAccreditationRequest(models.Model):
    _inherit = "dma.accreditation.request"

    accreditation_validity_state = fields.Selection(
        [
            ("not_issued", "Not Issued"),
            ("valid", "Valid"),
            ("expiring", "Expiring Soon"),
            ("expired", "Expired"),
        ],
        string="Accreditation Validity", compute="_compute_accreditation_validity",
        store=True, index=True,
        help="Whether the operational accreditation certificate is still "
             "current. Informational: an expiry never changes the status of "
             "the file by itself.",
    )
    days_to_accreditation_expiry = fields.Integer(
        string="Days to Expiry", compute="_compute_accreditation_validity", store=True,
    )

    @api.model
    def _expiry_warning_days(self):
        raw = self.env["ir.config_parameter"].sudo().get_param(
            EXPIRY_WARNING_PARAMETER, EXPIRY_WARNING_DEFAULT,
        )
        try:
            return max(int(float(raw)), 0)
        except (TypeError, ValueError):
            return EXPIRY_WARNING_DEFAULT

    @api.depends("state", "expiry_date")
    def _compute_accreditation_validity(self):
        today = fields.Date.context_today(self)
        warning = self._expiry_warning_days()
        for request in self:
            if request.state != "authorized" or not request.expiry_date:
                request.accreditation_validity_state = "not_issued"
                request.days_to_accreditation_expiry = 0
                continue
            days = (request.expiry_date - today).days
            request.days_to_accreditation_expiry = days
            if days < 0:
                request.accreditation_validity_state = "expired"
            elif days <= warning:
                request.accreditation_validity_state = "expiring"
            else:
                request.accreditation_validity_state = "valid"

    # ==================================================================
    # The scheduled watch
    # ==================================================================
    @api.model
    def _cron_document_watch(self):
        """Refresh what has aged overnight, and tell whoever needs to know.

        Idempotent throughout: the two reminders it raises are looked up by
        (record, activity type, assignee) and updated in place, so running it
        twice in one day changes nothing the second time.
        """
        documents = self.env["dma.request.document"]._cron_refresh_validity()
        # The certificate validity is derived from today's date too, so the
        # same argument applies to it: store it, and bring it back in line
        # once a day.
        issued = self.sudo().search([("state", "=", "authorized")])
        issued.modified(["expiry_date"])

        evidence = self._notify_expiring_evidence()
        certificates = self._notify_expiring_accreditations()
        _logger.info(
            "DMA evidence watch: %s document(s) re-evaluated, %s file(s) with "
            "expiring evidence, %s accreditation(s) running out",
            documents, evidence, certificates,
        )
        return True

    def _upsert_watch_activity(self, users, compose, deadline):
        """One expiry reminder per record and per user, updated in place.

        ``compose`` is called once per recipient with a recordset in *their*
        language and returns ``(summary, note)``: the text of an activity is
        stored, so it has to be written in the language of the officer who will
        read it rather than in the language the scheduled job happens to run in.
        """
        self.ensure_one()
        activity_type = self.env.ref(
            "dma_accreditation.mail_activity_type_expiry", raise_if_not_found=False,
        )
        if not activity_type or not users:
            return self.env["mail.activity"]
        Activity = self.env["mail.activity"].sudo()
        existing = Activity.search([
            ("res_model", "=", self._name),
            ("res_id", "=", self.id),
            ("activity_type_id", "=", activity_type.id),
        ])
        by_user = {activity.user_id.id: activity for activity in existing}
        touched = Activity
        for user in users:
            localised = self.sudo().with_context(lang=user.lang or self.env.lang)
            summary, note = compose(localised)
            activity = by_user.get(user.id)
            if activity:
                changes = {
                    key: value for key, value in
                    (("summary", summary), ("note", note), ("date_deadline", deadline))
                    if activity[key] != value
                }
                if changes:
                    activity.write(changes)
                touched |= activity
                continue
            touched |= localised.activity_schedule(
                act_type_xmlid="dma_accreditation.mail_activity_type_expiry",
                date_deadline=deadline,
                summary=summary,
                note=note,
                user_id=user.id,
            )
        return touched

    @api.model
    def _notify_expiring_evidence(self):
        """Tell the Certifications Division which live files carry stale paperwork."""
        at_risk = self.sudo().search([
            ("state", "not in", list(CLOSED_STATES)),
            "|",
            ("expiring_document_count", ">", 0),
            ("expired_document_count", ">", 0),
        ])
        touched = 0
        for request in at_risk:
            lines = request.document_ids.filtered(
                lambda line: line.validity_state in ("expiring", "expired")
            )
            if not lines:
                continue
            soonest = min(lines.mapped("expiry_date"))

            def compose(localised, lines=lines):
                documents = ", ".join(
                    "%s (%s)" % (
                        line.with_env(localised.env).type_id.display_name,
                        fields.Date.to_string(line.expiry_date),
                    ) for line in lines
                )
                return (
                    localised.env._("Expiring evidence: %s document(s)", len(lines)),
                    localised.env._(
                        "%(ref)s (%(partner)s): %(documents)s. The file is on "
                        "\u201c%(step)s\u201d.",
                        ref=localised.name,
                        partner=localised.partner_id.display_name,
                        documents=documents,
                        step=state_label(localised.env, localised.state),
                    ),
                )

            if request._upsert_watch_activity(
                request._responsible_users("cert_officer"), compose, soonest,
            ):
                touched += 1
        return touched

    @api.model
    def _notify_expiring_accreditations(self):
        """Put accreditations that are running out on the manager's desk."""
        horizon = fields.Date.context_today(self) + relativedelta(
            days=self._expiry_warning_days()
        )
        running_out = self.sudo().search([
            ("state", "=", "authorized"),
            ("expiry_date", "!=", False),
            ("expiry_date", "<=", horizon),
        ])
        touched = 0
        for request in running_out:
            days = request.days_to_accreditation_expiry

            def compose(localised, days=days):
                summary = (
                    localised.env._("Accreditation expired") if days < 0
                    else localised.env._("Accreditation expires in %s day(s)", days)
                )
                note = localised.env._(
                    "The operational accreditation %(certificate)s of %(partner)s "
                    "%(verb)s on %(date)s. Renewal is opened by the Directorate; "
                    "the status of the file is not changed automatically.",
                    certificate=localised.certificate_ref or localised.name,
                    partner=localised.partner_id.display_name,
                    verb=localised.env._("expired") if days < 0
                    else localised.env._("expires"),
                    date=fields.Date.to_string(localised.expiry_date),
                )
                return summary, note

            if request._upsert_watch_activity(
                request._responsible_users("manager"), compose, request.expiry_date,
            ):
                touched += 1
        return touched


class DmaAccreditationSettings(models.TransientModel):
    """One more directorate wide default: how early to warn about an expiry."""

    _inherit = "dma.accreditation.settings"

    expiry_warning_days = fields.Integer(
        string="Expiry Warning (days)", default=EXPIRY_WARNING_DEFAULT,
        help="How long before an accreditation certificate runs out the "
             "Accreditation Manager starts being reminded of it.",
    )

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        raw = self.env["ir.config_parameter"].sudo().get_param(
            EXPIRY_WARNING_PARAMETER, EXPIRY_WARNING_DEFAULT,
        )
        try:
            values["expiry_warning_days"] = max(int(float(raw)), 0)
        except (TypeError, ValueError):
            values["expiry_warning_days"] = EXPIRY_WARNING_DEFAULT
        return values

    def action_apply(self):
        """Save the extra parameter alongside the ones the base form owns."""
        self.ensure_one()
        self._check_manager()
        if self.expiry_warning_days < 0:
            raise ValidationError(self.env._(
                "The expiry warning period cannot be negative."
            ))
        self.env["ir.config_parameter"].sudo().set_param(
            EXPIRY_WARNING_PARAMETER, str(int(self.expiry_warning_days)),
        )
        return super().action_apply()
