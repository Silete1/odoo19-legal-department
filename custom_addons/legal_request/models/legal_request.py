from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

#: States in which a request is finished and no longer counts against a clock.
#: A request awaiting approval is still *open* and can still run late; an
#: approved (issued) one has been answered and a closed one is filed.
_DONE_STATES = ("approved", "closed", "cancelled")


class LegalRequest(models.Model):
    """A question put to the legal department - طلب إلى الشؤون القانونية.

    This is the surface the rest of the company sees, and it is first class
    rather than a line on a file for one blunt reason: **the request exists
    before the answer does**. The finance department that wants a supply
    contract vetted does not know the procedure, the counter or the fee; it has
    a question and a deadline. A design that made it open a ``legal.case`` before
    the legal department had even read the request would push the department's
    filing decision onto a requester who cannot make it.

    So a request carries only what a requester can honestly supply - a subject, a
    category, an urgency, a description - plus the three things the legal
    department adds as it works: who owns it, what its clock is, and what it
    became. The lifecycle is a plain state machine with server-enforced gates:

    * **triage and assignment are an officer's job**, not a clerk's. A clerk logs
      what arrived; an officer decides who works it.
    * **approval is an approver's job**. The officer prepares the answer and
      submits it; only an approver may sign it off, and the decision is recorded
      with a reason, because the requester, the manager and the auditor will each
      ask what was decided and why.
    * **the auditor may read every request and mutate none**, enforced by the
      access rules rather than by hope.

    ``action_convert`` is the single seam onto the rest of the suite. What a
    request becomes - a vetted contract, an issued opinion, a litigation file -
    is downstream work a later integrator wires in by overriding one method; the
    base spawns the one artefact that is always installed, an official letter on
    the correspondence register.
    """

    _name = "legal.request"
    _description = "Legal Department Request"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "request_date desc, id desc"
    _rec_names_search = ["reference", "subject"]

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------
    reference = fields.Char(
        string="Reference",
        default=lambda self: _("New"),
        readonly=True,
        copy=False,
        index="trigram",
        tracking=True,
        help="The department's number for this request, REQ/YYYY/####. Allocated "
        "when the request leaves draft, so a discarded draft burns no number.",
    )
    subject = fields.Char(
        required=True,
        translate=True,
        tracking=True,
        help="One line naming what is being asked, e.g. Review of the fuel supply contract.",
    )
    category_id = fields.Many2one(
        "legal.request.category",
        string="Category",
        ondelete="restrict",
        index=True,
        tracking=True,
        help="What class of request this is. Drives the triage desk's first guess "
        "at what it will become.",
    )
    description = fields.Html(
        string="Request Detail",
        translate=True,
        help="The full question, in the requester's own words.",
    )

    # ------------------------------------------------------------------
    # Who asked
    # ------------------------------------------------------------------
    requesting_department = fields.Char(
        string="Requesting Department",
        tracking=True,
        help="The section that raised this, e.g. Finance, Human Resources, Procurement.",
    )
    requester_id = fields.Many2one(
        "res.users",
        string="Requested By",
        default=lambda self: self.env.user,
        index=True,
        tracking=True,
        help="The person who asked. Defaults to whoever is logging the request.",
    )
    request_date = fields.Date(
        string="Request Date",
        default=fields.Date.context_today,
        tracking=True,
        help="The day the request was raised. Age and lateness are counted from here.",
    )
    related_partner_id = fields.Many2one(
        "res.partner",
        string="Related Party",
        index=True,
        help="A counterparty the request concerns - a supplier, a claimant, an employee.",
    )

    # ------------------------------------------------------------------
    # Priority and secrecy
    # ------------------------------------------------------------------
    urgency = fields.Selection(
        [
            ("low", "Low"),
            ("normal", "Normal"),
            ("high", "High"),
            ("urgent", "Urgent"),
        ],
        default="normal",
        required=True,
        index=True,
        tracking=True,
    )
    confidentiality = fields.Selection(
        [
            ("normal", "Normal"),
            ("restricted", "Restricted"),
            ("highly_restricted", "Highly Restricted"),
        ],
        default="normal",
        required=True,
        index=True,
        tracking=True,
        help="A restricted request is hidden from clerks and officers who are not "
        "on it; only its requester, its assigned officer, its manager and the "
        "legal manager see it.",
    )

    # ------------------------------------------------------------------
    # Ownership and the clock
    # ------------------------------------------------------------------
    assigned_officer_id = fields.Many2one(
        "res.users",
        string="Assigned Officer",
        index=True,
        tracking=True,
        help="The legal officer who works the request. Set at triage.",
    )
    manager_id = fields.Many2one(
        "res.users",
        string="Responsible Manager",
        index=True,
        tracking=True,
        help="The manager accountable for the answer.",
    )
    target_response_date = fields.Date(
        string="Target Response Date",
        tracking=True,
        help="When the department has undertaken to respond. Lateness is measured against this.",
    )
    age = fields.Integer(
        string="Age (days)",
        compute="_compute_age",
        help="How many days the request has been open. Recomputed on read, never "
        "stored, because it changes every midnight.",
    )
    is_overdue = fields.Boolean(
        string="Overdue",
        compute="_compute_is_overdue",
        search="_search_is_overdue",
        help="Open, and past its target response date. Read live, so it turns true "
        "at midnight with nobody writing to the record.",
    )

    # ------------------------------------------------------------------
    # The answer
    # ------------------------------------------------------------------
    response = fields.Html(
        string="Response / Outcome",
        translate=True,
        help="What the department answered. Filled in as the officer works and "
        "frozen at approval.",
    )
    decision = fields.Selection(
        [
            ("approved", "Approved"),
            ("approved_conditional", "Approved With Conditions"),
        ],
        string="Approval Decision",
        readonly=True,
        copy=False,
        tracking=True,
        help="What the approver decided. Recorded by the approval dialog.",
    )
    decision_note = fields.Text(
        string="Decision Note",
        readonly=True,
        copy=False,
        help="The approver's words - the conditions attached, or why it was signed as it stands.",
    )
    approved_by_id = fields.Many2one(
        "res.users", string="Approved By", readonly=True, copy=False, tracking=True
    )
    approved_on = fields.Datetime(
        string="Approved On", readonly=True, copy=False, tracking=True
    )
    cancel_reason = fields.Text(
        string="Cancellation Reason", readonly=True, copy=False
    )
    return_reason = fields.Text(
        string="Last Return Reason", readonly=True, copy=False
    )

    # ------------------------------------------------------------------
    # What it became - the conversion hook
    # ------------------------------------------------------------------
    converted_ref = fields.Reference(
        selection="_selection_converted_ref",
        string="Became",
        readonly=True,
        copy=False,
        help="The downstream record this request turned into - an official letter, "
        "a registered document, a procedure file. Set by the conversion.",
    )
    converted_model = fields.Char(
        string="Conversion Target",
        readonly=True,
        copy=False,
        help="The model of the downstream record, kept alongside the reference so "
        "a report can group on it without dereferencing every row.",
    )

    # ------------------------------------------------------------------
    # Letters raised from this request
    # ------------------------------------------------------------------
    correspondence_ids = fields.One2many(
        "legal.correspondence", "request_id", string="Letters", copy=False
    )
    correspondence_count = fields.Integer(compute="_compute_correspondence_count")

    # ------------------------------------------------------------------
    # Scope
    # ------------------------------------------------------------------
    entity_id = fields.Many2one(
        "legal.entity",
        string="Legal Entity",
        default=lambda self: self.env.company.legal_entity_id,
        index=True,
        help="Which of the company's legal entities the request concerns.",
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    active = fields.Boolean(default=True)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("received", "Received"),
            ("triage", "Under Triage"),
            ("assigned", "Assigned"),
            ("in_progress", "In Progress"),
            ("waiting_requester", "Waiting On Requester"),
            ("waiting_external", "Waiting On External Body"),
            ("ready_for_approval", "Ready For Approval"),
            ("approved", "Approved / Issued"),
            ("closed", "Closed"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        required=True,
        index=True,
        tracking=True,
        copy=False,
        group_expand="_group_expand_state",
    )

    # ==================================================================
    # Selections and display
    # ==================================================================
    @api.model
    def _selection_converted_ref(self):
        """Only offer conversion targets whose model is actually installed.

        ``legal.case`` lives in ``legal_procedure``, which this module does not
        depend on; listing it unconditionally would make the Reference field
        point at a model that may not exist. ``legal.correspondence`` and
        ``legal.document`` are always present through the dependency chain.
        """
        candidates = [
            ("legal.correspondence", _("Official Letter")),
            ("legal.document", _("Registered Document")),
            ("legal.case", _("Procedure File")),
        ]
        return [(model, label) for model, label in candidates if model in self.env]

    @api.model
    def _group_expand_state(self, states, domain):
        """Show every lifecycle column on the kanban, even the empty ones."""
        return [key for key, _label in self._fields["state"].selection]

    @api.depends("reference", "subject")
    def _compute_display_name(self):
        for request in self:
            ref = request.reference if request.reference and request.reference != _("New") else ""
            if ref and request.subject:
                request.display_name = "%s - %s" % (ref, request.subject)
            else:
                request.display_name = request.subject or ref or _("New Request")

    # ==================================================================
    # Computes
    # ==================================================================
    def _compute_age(self):
        today = fields.Date.context_today(self)
        for request in self:
            start = request.request_date or today
            end = today
            if request.state in _DONE_STATES and request.approved_on:
                end = fields.Date.context_today(self, request.approved_on)
            request.age = max((end - start).days, 0)

    @api.depends("target_response_date", "state")
    def _compute_is_overdue(self):
        today = fields.Date.context_today(self)
        for request in self:
            request.is_overdue = bool(
                request.target_response_date
                and request.state not in _DONE_STATES
                and request.target_response_date < today
            )

    def _search_is_overdue(self, operator, value):
        if operator not in ("=", "!="):
            raise UserError(_("Overdue can only be searched for equality."))
        today = fields.Date.context_today(self)
        overdue_domain = [
            "&",
            ("state", "not in", list(_DONE_STATES)),
            "&",
            ("target_response_date", "!=", False),
            ("target_response_date", "<", today),
        ]
        want_overdue = (operator == "=" and value) or (operator == "!=" and not value)
        return overdue_domain if want_overdue else ["!"] + overdue_domain

    def _compute_correspondence_count(self):
        counts = dict(
            self.env["legal.correspondence"]._read_group(
                [("request_id", "in", self.ids)], ["request_id"], ["__count"]
            )
        )
        for request in self:
            request.correspondence_count = counts.get(request, 0)

    # ==================================================================
    # Constraints
    # ==================================================================
    @api.constrains("target_response_date", "request_date")
    def _check_target_after_request(self):
        for request in self:
            if (
                request.target_response_date
                and request.request_date
                and request.target_response_date < request.request_date
            ):
                raise ValidationError(
                    _(
                        "The target response date cannot fall before the request was "
                        "raised. The clock starts on the request date, not before it."
                    )
                )

    # ==================================================================
    # Sequence allocation
    # ==================================================================
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # A request created straight into the queue (the mail room, an import,
            # the showcase data) skips the draft and takes its number at once.
            if (
                not vals.get("reference") or vals.get("reference") == _("New")
            ) and vals.get("state") and vals["state"] != "draft":
                vals["reference"] = self._next_reference()
        return super().create(vals_list)

    @api.model
    def _next_reference(self):
        return self.env["ir.sequence"].next_by_code("legal.request") or _("New")

    def _assign_reference(self):
        """Give the request its number the moment it leaves draft."""
        for request in self:
            if not request.reference or request.reference == _("New"):
                request.reference = request._next_reference()

    # ==================================================================
    # Gates
    # ==================================================================
    def _ensure_officer(self):
        if not self.env.user.has_group("legal_core.group_legal_officer"):
            raise UserError(
                _(
                    "Triage and assignment are a legal officer's decision. A clerk "
                    "registers what arrived; an officer decides who works it."
                )
            )

    def _ensure_approver(self):
        if not self.env.user.has_group("legal_core.group_legal_approver"):
            raise UserError(
                _(
                    "Only an approver or the legal manager may sign off a request. "
                    "The officer prepares the answer; the approver stands behind it."
                )
            )

    def _ensure_state(self, allowed, action_label):
        for request in self:
            if request.state not in allowed:
                raise UserError(
                    _(
                        "“%(ref)s” is %(state)s, and cannot be %(action)s from there.",
                        ref=request.display_name,
                        state=dict(self._fields["state"].selection).get(request.state),
                        action=action_label,
                    )
                )

    # ==================================================================
    # Workflow
    # ==================================================================
    def action_submit(self):
        """Draft -> received. The requester hands the question to the department."""
        self._ensure_state(("draft",), _("submitted"))
        self._assign_reference()
        self.write({"state": "received"})
        for request in self:
            request.message_post(body=_("Request submitted to the legal department."))
        return True

    def action_triage(self):
        """Received -> triage. An officer picks the request up to sort it."""
        self._ensure_officer()
        self._ensure_state(("received",), _("triaged"))
        self.write({"state": "triage"})
        return True

    def action_assign(self):
        """Triage -> assigned. An officer names who works it and by when.

        Assignable straight from *received* too - a small department triages and
        assigns in one motion, and forcing an intermediate click helps nobody.
        """
        self._ensure_officer()
        self._ensure_state(("received", "triage", "assigned", "in_progress"), _("assigned"))
        for request in self:
            if not request.assigned_officer_id:
                raise UserError(
                    _(
                        "Name the officer who will work “%s” before assigning it. An "
                        "assignment with no owner is a request nobody is watching.",
                        request.display_name,
                    )
                )
            request.state = "assigned"
            request.message_post(
                body=_(
                    "Assigned to %s.",
                    request.assigned_officer_id.display_name,
                )
            )
        return True

    def action_start(self):
        """Assigned -> in progress. The officer starts work."""
        self._ensure_state(
            ("assigned", "waiting_requester", "waiting_external"), _("started")
        )
        self.write({"state": "in_progress"})
        return True

    def action_wait_requester(self):
        """In progress -> waiting on the requester. The clock is theirs now."""
        self._ensure_state(("in_progress", "assigned"), _("put on hold"))
        self.write({"state": "waiting_requester"})
        for request in self:
            request.message_post(
                body=_("Waiting on the requester for further information.")
            )
        return True

    def action_wait_external(self):
        """In progress -> waiting on an external body."""
        self._ensure_state(("in_progress", "assigned"), _("put on hold"))
        self.write({"state": "waiting_external"})
        for request in self:
            request.message_post(body=_("Waiting on an external body to respond."))
        return True

    def action_submit_for_approval(self):
        """In progress -> ready for approval. The officer submits the answer."""
        self._ensure_state(
            ("in_progress", "waiting_requester", "waiting_external"),
            _("submitted for approval"),
        )
        for request in self:
            if not request._response_has_content():
                raise UserError(
                    _(
                        "“%s” has no response to approve. Write the department's answer "
                        "before sending it up - an approver cannot sign a blank.",
                        request.display_name,
                    )
                )
            request.state = "ready_for_approval"
            request.message_post(body=_("Submitted for approval."))
        return True

    def _response_has_content(self):
        self.ensure_one()
        text = (self.response or "").strip()
        # A stripped Html field is never truly empty - an empty editor still
        # leaves <p><br></p> - so measure the text, not the markup.
        stripped = (
            text.replace("<p>", "")
            .replace("</p>", "")
            .replace("<br>", "")
            .replace("<br/>", "")
            .replace("&nbsp;", "")
            .strip()
        )
        return bool(stripped)

    def action_approve(self):
        """Ready for approval -> approved. Approver+ only; opens the decision dialog."""
        self.ensure_one()
        self._ensure_approver()
        self._ensure_state(("ready_for_approval",), _("approved"))
        return {
            "type": "ir.actions.act_window",
            "name": _("Approve Request"),
            "res_model": "legal.request.approve",
            "view_mode": "form",
            "target": "new",
            "context": {"default_request_id": self.id},
        }

    def _apply_approval(self, decision, note):
        """The write behind the approval dialog. Records who, when and what."""
        self.ensure_one()
        self._ensure_approver()
        self._ensure_state(("ready_for_approval",), _("approved"))
        self.write(
            {
                "state": "approved",
                "decision": decision,
                "decision_note": note,
                "approved_by_id": self.env.user.id,
                "approved_on": fields.Datetime.now(),
            }
        )
        label = dict(self._fields["decision"].selection).get(decision)
        body = _("Approved (%s).", label)
        if note:
            body += "\n" + note
        self.message_post(body=body)
        return True

    def action_return(self):
        """Ready for approval -> in progress, with a reason. Approver+ only.

        The reason is mandatory and captured by a dialog, because a request sent
        back with no explanation is a request the officer reworks by guessing.
        """
        self.ensure_one()
        self._ensure_approver()
        self._ensure_state(("ready_for_approval",), _("returned"))
        return {
            "type": "ir.actions.act_window",
            "name": _("Return For Rework"),
            "res_model": "legal.request.return",
            "view_mode": "form",
            "target": "new",
            "context": {"default_request_id": self.id},
        }

    def _apply_return(self, reason):
        self.ensure_one()
        self._ensure_approver()
        self._ensure_state(("ready_for_approval",), _("returned"))
        self.write({"state": "in_progress", "return_reason": reason})
        self.message_post(body=_("Returned for rework: %s", reason))
        return True

    def action_close(self):
        """Approved -> closed. The answer has been delivered and filed."""
        self._ensure_officer()
        self._ensure_state(("approved",), _("closed"))
        self.write({"state": "closed"})
        for request in self:
            request.message_post(body=_("Request closed."))
        return True

    def action_cancel(self):
        """Cancel with a reason, from any live state. Opens the reason dialog.

        A clerk may cancel their own draft; past draft, cancellation is an
        officer's call. The reason is mandatory either way.
        """
        self.ensure_one()
        if self.state in ("closed", "cancelled"):
            raise UserError(
                _("“%s” is already finished and cannot be cancelled.", self.display_name)
            )
        if self.state != "draft":
            self._ensure_officer()
        return {
            "type": "ir.actions.act_window",
            "name": _("Cancel Request"),
            "res_model": "legal.request.cancel",
            "view_mode": "form",
            "target": "new",
            "context": {"default_request_id": self.id},
        }

    def _apply_cancel(self, reason):
        self.ensure_one()
        if self.state in ("closed", "cancelled"):
            raise UserError(
                _("“%s” is already finished and cannot be cancelled.", self.display_name)
            )
        if self.state != "draft":
            self._ensure_officer()
        self.write({"state": "cancelled", "cancel_reason": reason})
        self.message_post(body=_("Cancelled: %s", reason))
        return True

    def action_reset_to_draft(self):
        """Cancelled -> draft, so a mistaken cancellation is not a dead end."""
        self._ensure_officer()
        self._ensure_state(("cancelled",), _("reopened"))
        self.write({"state": "draft"})
        return True

    # ==================================================================
    # Conversion hook
    # ==================================================================
    def action_convert(self):
        """Turn the request into the artefact it called for. The clean seam.

        What a request becomes - a vetted contract, an issued opinion, a
        litigation file - is downstream work a later integrator wires in by
        overriding :meth:`_convert_action`. The base spawns the one artefact
        always installed: an official letter on the correspondence register,
        prefilled from the request and linked back to it.
        """
        self.ensure_one()
        self._ensure_officer()
        if self.state in ("cancelled",):
            raise UserError(
                _("A cancelled request has nothing to convert.")
            )
        return self._convert_action()

    def _convert_action(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("New Letter From Request"),
            "res_model": "legal.correspondence",
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_request_id": self.id,
                "default_subject": self.subject or "",
                "default_entity_id": self.entity_id.id,
                "default_direction": "out",
            },
        }

    def _record_conversion(self, record):
        """Note what the request became. Called by the downstream create.

        Kept as a helper rather than baked into the correspondence create so a
        request that raises several letters is not mislabelled as "becoming" the
        first of them - the integrator records the *primary* artefact (usually a
        case), and only that one.
        """
        self.ensure_one()
        self.write(
            {
                "converted_ref": "%s,%s" % (record._name, record.id),
                "converted_model": record._name,
            }
        )
        self.message_post(body=_("Converted into %s.", record.display_name))
        return True

    def action_open_correspondence(self):
        """The smart button: the letters raised from this request."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Letters"),
            "res_model": "legal.correspondence",
            "view_mode": "list,form",
            "domain": [("request_id", "=", self.id)],
            "context": {
                "default_request_id": self.id,
                "default_subject": self.subject or "",
                "default_entity_id": self.entity_id.id,
                "default_direction": "out",
            },
        }

    def action_open_converted(self):
        """Open whatever the request became."""
        self.ensure_one()
        if not self.converted_ref:
            return False
        return {
            "type": "ir.actions.act_window",
            "res_model": self.converted_ref._name,
            "res_id": self.converted_ref.id,
            "view_mode": "form",
        }

    # ==================================================================
    # Deletion guard
    # ==================================================================
    def unlink(self):
        # Let a module uninstall (and the demo teardown that rides on it) delete
        # the showcase records; the block is for a person at a keyboard, not for
        # the framework tearing the module down.
        if self.env.context.get("_force_unlink"):
            return super().unlink()
        for request in self:
            if request.reference and request.reference != _("New"):
                raise UserError(
                    _(
                        "“%s” has a register number and is part of the department's "
                        "record. Cancel it with a reason instead of deleting it - a "
                        "gap in the numbering is a question nobody can answer later.",
                        request.display_name,
                    )
                )
        return super().unlink()
