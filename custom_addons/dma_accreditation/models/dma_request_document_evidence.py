# Part of the DMA Accreditation module. See LICENSE file for full copyright and licensing details.
"""Turning the prerequisites checklist into an evidence file.

A checklist line used to answer one question - has the Certifications Division
accepted this document? This adds the rest of what an accreditation officer and
an auditor actually need to know about a piece of evidence:

* what the document itself says (its number, who issued it, when it expires);
* whether it is still valid, expiring or out of date;
* which version is current and what the previous ones were;
* whether the very same file has already been handed in somewhere else;
* and, for the officer standing at the gate, precisely why this line is the one
  holding the office accreditation up.

The one behavioural change, and why it is a defect fix
-------------------------------------------------------
``review_result`` used to survive a change of the files behind it. Reception has
full write access to the checklist (it assembles the file), so an accepted line
could have its evidence swapped for something nobody had looked at and the hard
gate would still open on it. A sign-off says "I checked *this* on that day", so
from now on replacing the evidence of a reviewed line files the old version
away, resets the line to pending and says so in the chatter. Nothing else about
the workflow moves.
"""
import logging
from collections import defaultdict

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

#: The three answers to "can this document still be relied on?" plus the very
#: common fourth: most accreditation prerequisites simply do not expire.
VALIDITY_STATE_SELECTION = [
    ("no_expiry", "No Expiry"),
    ("valid", "Valid"),
    ("expiring", "Expiring Soon"),
    ("expired", "Expired"),
]

#: Review outcomes that are an actual verdict rather than "not looked at yet".
DECIDED_REVIEW_RESULTS = ("accepted", "invalid", "missing")


class DmaRequestDocument(models.Model):
    _inherit = "dma.request.document"

    # ==================================================================
    # What the document says about itself
    # ==================================================================
    reference = fields.Char(
        string="Document Number",
        help="The number printed on the document itself - the registration "
             "number, the policy number, the certificate number.",
    )
    issuer = fields.Char(
        string="Issued By",
        help="The authority or company that issued the document.",
    )
    issue_date = fields.Date(string="Issue Date")
    expiry_date = fields.Date(string="Expiry Date")
    has_validity = fields.Boolean(
        related="type_id.has_validity", string="Expires", readonly=True,
    )
    blocks_on_expiry = fields.Boolean(
        related="type_id.blocks_on_expiry", readonly=True,
    )

    validity_state = fields.Selection(
        VALIDITY_STATE_SELECTION, string="Validity",
        compute="_compute_validity_state", store=True, index=True,
        help="Valid, expiring soon or expired, measured against the expiry "
             "date written on the document.",
    )
    days_to_expiry = fields.Integer(
        string="Days to Expiry", compute="_compute_validity_state", store=True,
        help="Negative once the document has expired.",
    )

    # ==================================================================
    # Versions
    # ==================================================================
    submission_ids = fields.One2many(
        "dma.document.submission", "document_id", string="Previous Versions",
        readonly=True,
    )
    version = fields.Integer(
        string="Version", compute="_compute_version", store=True, default=1,
        help="1 while the first set of files is still the one on file.",
    )
    superseded_count = fields.Integer(
        string="Replaced Versions", compute="_compute_version", store=True,
    )

    # ==================================================================
    # Files
    # ==================================================================
    attachment_count = fields.Integer(
        string="Number of Files", compute="_compute_attachment_count", store=True,
    )
    duplicate_of_id = fields.Many2one(
        "dma.request.document", string="Same File As",
        compute="_compute_duplicate",
        help="Another requirement of this same accreditation file that carries "
             "byte for byte the same document.",
    )
    duplicate_warning = fields.Char(
        string="Duplicate Warning", compute="_compute_duplicate",
        depends_context=("lang",),
    )

    # ==================================================================
    # The gate
    # ==================================================================
    is_blocking = fields.Boolean(
        string="Blocking", compute="_compute_is_blocking", store=True, index=True,
        help="This line is required and is not in a state that lets the office "
             "accreditation be granted.",
    )
    blocking_reason = fields.Char(
        string="Why", compute="_compute_blocking_reason", depends_context=("lang",),
    )

    # ==================================================================
    # Computes
    # ==================================================================
    @api.depends("expiry_date", "type_id.has_validity", "type_id.expiry_warning_days")
    def _compute_validity_state(self):
        today = fields.Date.context_today(self)
        for line in self:
            if not line.type_id.has_validity or not line.expiry_date:
                line.validity_state = "no_expiry"
                line.days_to_expiry = 0
                continue
            days = (line.expiry_date - today).days
            line.days_to_expiry = days
            if days < 0:
                line.validity_state = "expired"
            elif days <= (line.type_id.expiry_warning_days or 0):
                line.validity_state = "expiring"
            else:
                line.validity_state = "valid"

    @api.depends("submission_ids")
    def _compute_version(self):
        for line in self:
            line.superseded_count = len(line.submission_ids)
            line.version = len(line.submission_ids) + 1

    @api.depends("attachment_ids")
    def _compute_attachment_count(self):
        for line in self:
            line.attachment_count = len(line.attachment_ids)

    @api.depends("attachment_ids", "request_id.document_ids.attachment_ids")
    def _compute_duplicate(self):
        """Flag a file that has already been handed in for another requirement.

        Matched on the checksum ir.attachment computes server side, so it is
        the bytes that are compared and not the name an applicant chose. This
        is a *warning*, never a refusal: one PDF can legitimately be both the
        registration certificate and the proof of legal representation, and it
        is the Certifications Division that decides whether that is acceptable.
        """
        # One pass over the whole checklist of the files concerned rather than
        # one query per line: this compute runs on every render of the tab.
        by_request = defaultdict(lambda: self.browse())
        for line in self:
            by_request[line.request_id] |= line

        for request, lines in by_request.items():
            siblings = request.document_ids
            checksums = defaultdict(lambda: self.browse())
            for sibling in siblings:
                for checksum in sibling.attachment_ids.mapped("checksum"):
                    if checksum:
                        checksums[checksum] |= sibling
            for line in lines:
                twin = self.browse()
                for checksum in line.attachment_ids.mapped("checksum"):
                    others = checksums.get(checksum, self.browse()) - line
                    if others:
                        twin = others[0]
                        break
                line.duplicate_of_id = twin
                line.duplicate_warning = self.env._(
                    "The very same file is already on file as “%s”.",
                    twin.type_id.display_name,
                ) if twin else False

    @api.depends(
        "is_required", "is_provided", "review_result", "validity_state",
        "type_id.blocks_on_expiry",
    )
    def _compute_is_blocking(self):
        for line in self:
            line.is_blocking = bool(line.is_required and not line._is_satisfied())

    # A separate method from the one above on purpose: one is stored and one is
    # not, and the ORM refuses to reason about a compute that writes both.
    @api.depends(
        "is_required", "is_provided", "review_result", "expiry_date",
        "type_id.has_validity", "type_id.blocks_on_expiry",
    )
    def _compute_blocking_reason(self):
        for line in self:
            line.blocking_reason = (
                line._blocking_reason()
                if line.is_required and not line._is_satisfied() else False
            )

    # ==================================================================
    # The gate, in one place
    # ==================================================================
    def _is_satisfied(self):
        """Whether this line lets the office accreditation through.

        The review outcome stays authoritative - "a file is attached" has never
        been the same thing as "the Certifications Division accepted it". An
        expiry only adds to that, and only for the document types the
        Accreditation Manager has marked as blocking.
        """
        self.ensure_one()
        if not (self.is_provided and self.review_result == "accepted"):
            return False
        if self.type_id.blocks_on_expiry and self._is_expired():
            return False
        return True

    def _is_expired(self):
        """Read the calendar, not the stored column.

        ``validity_state`` is stored so it can be filtered and grouped on, and
        a stored value computed from "today" is a day stale by tomorrow. The
        hard gate must never be a day out, so it asks the question directly.
        """
        self.ensure_one()
        return bool(
            self.type_id.has_validity
            and self.expiry_date
            and self.expiry_date < fields.Date.context_today(self)
        )

    def _blocking_reason(self):
        self.ensure_one()
        # The explicit verdict comes first: "the Certifications Division looked
        # and recorded it as missing" and "nobody has handed anything in" send
        # an officer to two different places.
        if self.review_result == "missing":
            return self.env._("Recorded as missing")
        if not self.is_provided:
            return self.env._("Not provided")
        if self.review_result == "invalid":
            return self.env._("Rejected as invalid")
        if self.review_result == "pending":
            return self.env._("Provided but not reviewed yet")
        if self._is_expired():
            return self.env._("Expired on %s", fields.Date.to_string(self.expiry_date))
        return self.env._("Not accepted")

    # ==================================================================
    # Versioning
    # ==================================================================
    def _register_evidence_change(self, previous_attachment_ids, previous_result):
        """React to the files behind a reviewed line having been replaced."""
        self.ensure_one()
        if not previous_attachment_ids:
            # The first upload is not a replacement of anything.
            return False
        reason = self.env.context.get("dma_replacement_reason")
        # The snapshot has to describe the *previous* state, so it is taken
        # against the attachments as they were.
        previous = self.env["ir.attachment"].sudo().browse(sorted(previous_attachment_ids))
        submission = self.env["dma.document.submission"].sudo().create({
            "document_id": self.id,
            "version": self.version,
            "attachment_ids": [fields.Command.set(previous.exists().ids)],
            "review_result": previous_result,
            "reviewed_by": self.reviewed_by.id,
            "reviewed_on": self.reviewed_on,
            "notes": self.notes,
            "reference": self.reference,
            "issuer": self.issuer,
            "issue_date": self.issue_date,
            "expiry_date": self.expiry_date,
            "replacement_reason": reason or False,
        })
        body = self.env._(
            "Evidence replaced for “%(document)s” (version %(old)s → %(new)s).",
            document=self.type_id.display_name,
            old=submission.version,
            new=submission.version + 1,
        )
        if previous_result in DECIDED_REVIEW_RESULTS:
            # The verdict was about the files that have just gone. It has to be
            # given again rather than silently carrying over to new evidence.
            self._reset_review()
            body = "%s %s" % (body, self.env._(
                "The previous review is no longer valid; the document is back "
                "with the Certifications Division."
            ))
        if reason:
            body = "%s %s" % (body, self.env._("Reason: %s", reason))
        self.request_id.message_post(body=body)
        return submission

    def _reset_review(self):
        """Put the line back in front of the Certifications Division.

        Two writes rather than one: the base model stamps the acting user as
        the reviewer whenever ``review_result`` changes, and the person who
        swapped a file is precisely not the person who reviewed it.
        """
        self.ensure_one()
        line = self.sudo()
        super(DmaRequestDocument, line).write({"review_result": "pending"})
        super(DmaRequestDocument, line).write({
            "reviewed_by": False, "reviewed_on": False,
        })
        return True

    # ==================================================================
    # CRUD
    # ==================================================================
    def write(self, vals):
        """Keep the review verdict tied to the evidence it was given on."""
        if "attachment_ids" not in vals:
            return super().write(vals)
        before = {
            line.id: (set(line.attachment_ids.ids), line.review_result)
            for line in self
        }
        result = super().write(vals)
        for line in self:
            previous_ids, previous_result = before.get(line.id, (set(), "pending"))
            if set(line.attachment_ids.ids) != previous_ids:
                line._register_evidence_change(previous_ids, previous_result)
        return result

    # ==================================================================
    # Keeping the stored validity column fresh
    # ==================================================================
    @api.model
    def _cron_refresh_validity(self):
        """Re-evaluate the validity of the evidence of every live file.

        ``validity_state`` is derived from today's date, so a stored value is
        one day stale by tomorrow. It is stored anyway - a manager has to be
        able to filter and group on it - and this brings it back in line once a
        day. Nothing that gates the workflow reads it: see :meth:`_is_expired`.
        """
        live = self.sudo().search([
            ("expiry_date", "!=", False),
            ("request_id.state", "not in", ("authorized", "rejected")),
        ])
        live.modified(["expiry_date"])
        return len(live)

    # ==================================================================
    # Actions
    # ==================================================================
    def action_open_version_history(self):
        """The full trail of what was submitted for this requirement."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Versions of %s", self.type_id.display_name),
            "res_model": "dma.document.submission",
            "view_mode": "list,form",
            "domain": [("document_id", "=", self.id)],
            "context": {"create": False},
        }

    def action_open_replacement_wizard(self):
        """Ask for the replacement, its metadata and the reason, in one dialog."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Replace %s", self.type_id.display_name),
            "res_model": "dma.document.replacement",
            "view_mode": "form",
            "target": "new",
            "context": {"default_document_id": self.id},
        }


class DmaAccreditationRequest(models.Model):
    """The request's own view of its evidence."""

    _inherit = "dma.accreditation.request"

    blocking_document_count = fields.Integer(
        string="Blocking Documents", compute="_compute_checklist_progress", store=True,
    )
    expiring_document_count = fields.Integer(
        string="Expiring Documents", compute="_compute_document_validity", store=True,
    )
    expired_document_count = fields.Integer(
        string="Expired Documents", compute="_compute_document_validity", store=True,
    )
    document_replacement_count = fields.Integer(
        string="Replaced Documents", compute="_compute_document_validity", store=True,
        help="How many prerequisites had their evidence replaced at least once.",
    )

    @api.depends(
        "document_ids.is_required",
        "document_ids.is_provided",
        "document_ids.review_result",
        "document_ids.is_blocking",
    )
    def _compute_checklist_progress(self):
        """Count an accepted-but-expired document as not accepted.

        The base version asks only whether the Certifications Division ticked
        the line. Where the Accreditation Manager has declared a document type
        blocking on expiry, a lapsed copy is no longer evidence of anything, so
        it stops counting - and the "7 / 10" chip, the completion flag and the
        hard gate all move together, because they all read this one answer.
        """
        for request in self:
            required = request.document_ids.filtered("is_required")
            accepted = required.filtered(lambda line: line._is_satisfied())
            request.required_document_count = len(required)
            request.accepted_document_count = len(accepted)
            request.blocking_document_count = len(required) - len(accepted)
            request.checklist_complete = bool(required) and len(required) == len(accepted)
            request.checklist_progress = f"{len(accepted)} / {len(required)}"

    @api.depends(
        "document_ids.validity_state", "document_ids.superseded_count",
    )
    def _compute_document_validity(self):
        for request in self:
            states = request.document_ids.mapped("validity_state")
            request.expiring_document_count = states.count("expiring")
            request.expired_document_count = states.count("expired")
            request.document_replacement_count = len(
                request.document_ids.filtered(lambda line: line.superseded_count)
            )

    def _missing_checklist_lines(self):
        """Every required line that is not in a state the gate accepts."""
        self.ensure_one()
        return self.document_ids.filtered(
            lambda line: line.is_required and not line._is_satisfied()
        )

    def _progress_blockers(self):
        """Say *why* each document is holding the file up, not just that it is.

        "Insurance is provided but not accepted yet" and "Insurance expired on
        2026-03-01" send an officer to two entirely different places, and the
        checklist already knows which of the two it is.
        """
        self.ensure_one()
        if self.state != "cert_check":
            return super()._progress_blockers()
        blockers = [
            self.env._(
                "%(document)s: %(reason)s",
                document=line.type_id.display_name,
                reason=line.blocking_reason or self.env._("Not accepted"),
            )
            for line in self._missing_checklist_lines()
        ]
        if not self.required_document_count:
            blockers.append(self.env._("The prerequisites checklist is empty."))
        return blockers

    def action_open_blocking_documents(self):
        """Jump straight to what is wrong with this company's paperwork."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Blocking Documents"),
            "res_model": "dma.request.document",
            "view_mode": "list,form",
            "domain": [("request_id", "=", self.id), ("is_blocking", "=", True)],
            "context": {"create": False},
        }
