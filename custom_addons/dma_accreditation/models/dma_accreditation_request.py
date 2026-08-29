# Part of the DMA Accreditation module. See LICENSE file for full copyright and licensing details.
import logging
import uuid

from dateutil.relativedelta import relativedelta
from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.fields import Domain
from odoo.tools import is_html_empty

from .dma_constants import (
    MAIN_PATH_STATES,
    REVIEWABLE_STATES,
    ROLE_GROUP,
    ROLE_QUEUE_STATES,
    ROLE_SELECTION,
    STATE_PENDING_ROLE,
    STATE_SELECTION,
    role_label,
    state_label,
)

_logger = logging.getLogger(__name__)

#: A returned request goes back exactly one logical step. The keys are exactly
#: the states of :data:`REVIEWABLE_STATES`.
RETURN_TARGET_STATE = {
    "submitted": "draft",
    "gd_review": "submitted",
    "legal_review": "gd_review",
    "cert_check": "legal_review",
    "office_granted": "cert_check",
    "sop_submission": "office_granted",
    "sop_fee": "sop_submission",
    "dual_confirm": "sop_fee",
    "demo_fee": "dual_confirm",
    "committee": "demo_fee",
    "legal_refine": "committee",
}


#: Fields the workflow owns. They carry the legal meaning of the file - the
#: status, the official references and the departmental sign-offs - so they may
#: only ever change through the ``action_*`` methods, which guard the status and
#: the role and append to the approval log. ``readonly=True`` is a client side
#: hint in Odoo 19 and stops nothing over RPC, hence the ``write`` override.
WORKFLOW_OWNED_FIELDS = frozenset({
    "name",
    "state",
    "return_to_state",
    "submission_date",
    "office_ref",
    "office_date",
    "certificate_ref",
    "issue_date",
    "expiry_date",
    "sop_paper_received",
    "sop_paper_received_by",
    "sop_paper_received_date",
    "finance_confirmed_sop_fee",
    "finance_confirmed_by",
    "finance_confirmed_on",
    "operations_confirmed_sop",
    "operations_confirmed_by",
    "operations_confirmed_on",
    "legal_refined_by",
    "legal_refined_on",
    "reject_reason",
    "return_reason",
    "verification_token",
})


class DmaAccreditationRequest(models.Model):
    """Accreditation file of a demining organisation (IMAS/TNMA 07.30).

    The record walks through the two accreditation phases; each transition is
    guarded server side (state *and* security group) and appended to the
    immutable ``dma.approval.line`` log.
    """

    _name = "dma.accreditation.request"
    _description = "Accreditation Request"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "priority desc, id desc"

    # ------------------------------------------------------------------
    # Identification
    # ------------------------------------------------------------------
    name = fields.Char(
        string="Reference", required=True, readonly=True, copy=False,
        default=lambda self: self.env._("New"), index="trigram",
    )
    active = fields.Boolean(default=True)
    priority = fields.Selection(
        [("0", "Normal"), ("1", "Urgent")], default="0", string="Priority",
    )
    company_id = fields.Many2one(
        "res.company", string="Company", required=True, index=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        "res.currency", string="Currency",
        default=lambda self: self.env.company.currency_id,
    )

    # ------------------------------------------------------------------
    # Applicant
    # ------------------------------------------------------------------
    partner_id = fields.Many2one(
        "res.partner", string="Applicant Company", required=True, tracking=True,
        index=True, help="Demining organisation applying for accreditation.",
    )
    contact_partner_id = fields.Many2one(
        "res.partner", string="Contact Person",
        domain="['|', ('parent_id', '=', partner_id), ('id', '=', partner_id)]",
    )
    contact_name = fields.Char(
        string="Contact Name", compute="_compute_contact_details",
        store=True, readonly=False,
    )
    contact_email = fields.Char(
        string="Contact Email", compute="_compute_contact_details",
        store=True, readonly=False,
    )
    contact_phone = fields.Char(
        string="Contact Phone", compute="_compute_contact_details",
        store=True, readonly=False,
    )
    request_type = fields.Selection(
        [("new", "New Accreditation"), ("renewal", "Renewal"), ("amendment", "Amendment")],
        string="Request Type", default="new", required=True, tracking=True,
    )
    scope_ids = fields.Many2many(
        "dma.accreditation.scope", string="Requested Scopes", tracking=True,
    )
    submission_date = fields.Date(string="Submission Date", copy=False, readonly=True)

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------
    state = fields.Selection(
        STATE_SELECTION, string="Status", default="draft", required=True,
        tracking=True, copy=False, index=True, group_expand="_group_expand_state",
    )
    return_to_state = fields.Selection(
        STATE_SELECTION, string="Return Target", copy=False, readonly=True,
        help="Step the request goes back to once the applicant resubmits it.",
    )
    pending_group = fields.Selection(
        ROLE_SELECTION, string="Pending With", compute="_compute_pending_group",
        store=True, index=True,
        help="Role that has to act on the request at its current step.",
    )
    # Technical payload of the progress widget: the steps, who signed each of
    # them and what is blocking the current one. Deliberately without `help`:
    # the widget has no label, so a help text would only surface as a stray
    # tooltip over the form.
    progress_payload = fields.Json(
        string="Progress", compute="_compute_progress_payload",
    )
    is_my_turn = fields.Boolean(
        string="My Turn", compute="_compute_is_my_turn", search="_search_is_my_turn",
        # The answer depends on the groups of the reader, so the value must
        # never be shared between two users through the ORM cache.
        compute_sudo=False, depends_context=("uid",),
    )
    approval_line_ids = fields.One2many(
        "dma.approval.line", "request_id", string="Approvals Log",
        readonly=True, copy=False,
    )
    verification_token = fields.Char(
        string="Verification Code", readonly=True, copy=False, index=True,
        default=lambda self: uuid.uuid4().hex,
        help="Code encoded in the QR of the official documents; it lets a third "
             "party verify the authenticity of a letter or a certificate.",
    )

    # ------------------------------------------------------------------
    # Phase 1 - office accreditation
    # ------------------------------------------------------------------
    document_ids = fields.One2many(
        "dma.request.document", "request_id", string="Prerequisite Documents",
    )
    required_document_count = fields.Integer(
        string="Required Documents", compute="_compute_checklist_progress", store=True,
    )
    accepted_document_count = fields.Integer(
        string="Accepted Documents", compute="_compute_checklist_progress", store=True,
    )
    checklist_complete = fields.Boolean(
        string="Checklist Complete", compute="_compute_checklist_progress", store=True,
    )
    checklist_progress = fields.Char(
        string="Checklist Progress", compute="_compute_checklist_progress",
        help="Accepted required documents over the total of required documents.",
    )
    office_ref = fields.Char(string="Office Accreditation Reference", readonly=True, copy=False)
    office_date = fields.Date(string="Office Accreditation Date", readonly=True, copy=False)

    # ------------------------------------------------------------------
    # Phase 2 - operational accreditation
    # ------------------------------------------------------------------
    sop_reference = fields.Char(string="SOP Reference")
    sop_version = fields.Char(string="SOP Version")
    sop_attachment_ids = fields.Many2many(
        "ir.attachment",
        "dma_request_sop_attachment_rel",
        "request_id",
        "attachment_id",
        string="Electronic SOP",
        help="Electronic copy of the Standing Operating Procedures.",
    )
    sop_paper_received = fields.Boolean(string="Paper SOP Received", copy=False, tracking=True)
    sop_paper_received_by = fields.Many2one(
        "res.users", string="Paper SOP Received By", readonly=True, copy=False,
    )
    sop_paper_received_date = fields.Date(
        string="Paper SOP Received On", readonly=True, copy=False,
    )

    fee_ids = fields.One2many("dma.fee.payment", "request_id", string="Fees")
    sop_fee_paid = fields.Boolean(
        compute="_compute_fee_status", store=True, string="SOP Reading Fee Confirmed",
    )
    demo_fee_paid = fields.Boolean(
        compute="_compute_fee_status", store=True, string="Demonstration Fee Confirmed",
    )
    total_fees_confirmed = fields.Monetary(
        string="Total Fees Confirmed", compute="_compute_fee_status", store=True,
        currency_field="currency_id",
    )

    finance_confirmed_sop_fee = fields.Boolean(
        string="Finance Confirmation", copy=False, tracking=True,
        help="Finance confirms receipt of the request and of the SOP reading fee.",
    )
    finance_confirmed_by = fields.Many2one(
        "res.users", string="Finance Confirmed By", readonly=True, copy=False,
    )
    finance_confirmed_on = fields.Datetime(
        string="Finance Confirmed On", readonly=True, copy=False,
    )
    operations_confirmed_sop = fields.Boolean(
        string="Operations Confirmation", copy=False, tracking=True,
        help="Operations confirms receipt of the company SOP for appraisal.",
    )
    operations_confirmed_by = fields.Many2one(
        "res.users", string="Operations Confirmed By", readonly=True, copy=False,
    )
    operations_confirmed_on = fields.Datetime(
        string="Operations Confirmed On", readonly=True, copy=False,
    )
    dual_confirm_complete = fields.Boolean(
        string="Both Parties Confirmed", compute="_compute_dual_confirm_complete", store=True,
    )

    committee_decision = fields.Selection(
        [
            ("approve", "Approved"),
            ("conditional", "Approved with Conditions"),
            ("reject", "Rejected"),
        ],
        string="Committee Decision", copy=False, tracking=True,
    )
    committee_date = fields.Date(string="Committee Date", copy=False)
    committee_minutes_ids = fields.Many2many(
        "ir.attachment",
        "dma_request_minutes_attachment_rel",
        "request_id",
        "attachment_id",
        string="Committee Minutes",
    )
    decision_text = fields.Html(
        string="Committee Decision Text", sanitize=True, copy=False,
    )
    refined_decision_text = fields.Html(
        string="Refined Decision Text", sanitize=True, copy=False,
        help="Decision text after the refinement of the Legal Department.",
    )
    legal_refined_by = fields.Many2one(
        "res.users", string="Refined By", readonly=True, copy=False,
    )
    legal_refined_on = fields.Datetime(string="Refined On", readonly=True, copy=False)

    certificate_ref = fields.Char(string="Certificate Number", readonly=True, copy=False)
    issue_date = fields.Date(string="Issue Date", readonly=True, copy=False)
    expiry_date = fields.Date(string="Expiry Date", readonly=True, copy=False)

    # ------------------------------------------------------------------
    # Exceptions
    # ------------------------------------------------------------------
    reject_reason = fields.Text(string="Rejection Reason", readonly=True, copy=False)
    return_reason = fields.Text(string="Return Reason", readonly=True, copy=False)

    _check_validity_dates = models.Constraint(
        "CHECK(expiry_date IS NULL OR issue_date IS NULL OR expiry_date >= issue_date)",
        "The expiry date of an accreditation cannot precede its issue date.",
    )

    # ==================================================================
    # Compute / onchange
    # ==================================================================
    @api.depends("name", "partner_id.display_name")
    def _compute_display_name(self):
        for request in self:
            if request.partner_id:
                request.display_name = f"{request.name} - {request.partner_id.display_name}"
            else:
                request.display_name = request.name or ""

    @api.depends("partner_id", "contact_partner_id")
    def _compute_contact_details(self):
        for request in self:
            contact = request.contact_partner_id or request.partner_id
            request.contact_name = contact.name or False
            request.contact_email = contact.email or False
            request.contact_phone = contact.phone or False

    @api.depends("state", "finance_confirmed_sop_fee", "operations_confirmed_sop")
    def _compute_pending_group(self):
        for request in self:
            roles = request._pending_roles()
            request.pending_group = roles[0] if roles else False

    @api.depends("state", "finance_confirmed_sop_fee", "operations_confirmed_sop")
    def _compute_is_my_turn(self):
        roles = self._user_roles(self.env.user)
        for request in self:
            request.is_my_turn = request._matches_user_queue(roles)

    @api.depends(
        "document_ids.is_required",
        "document_ids.is_provided",
        "document_ids.review_result",
    )
    def _compute_checklist_progress(self):
        for request in self:
            required = request.document_ids.filtered("is_required")
            accepted = required.filtered(
                lambda line: line.is_provided and line.review_result == "accepted"
            )
            request.required_document_count = len(required)
            request.accepted_document_count = len(accepted)
            request.checklist_complete = bool(required) and len(required) == len(accepted)
            # Rendered as one atomic "7 / 10" chip: keeping the two numbers out
            # of the surrounding sentence is what makes the banner readable in
            # a right-to-left interface.
            request.checklist_progress = f"{len(accepted)} / {len(required)}"

    @api.depends("fee_ids.state", "fee_ids.fee_type", "fee_ids.amount")
    def _compute_fee_status(self):
        for request in self:
            confirmed = request.fee_ids.filtered(lambda fee: fee.state == "confirmed")
            request.sop_fee_paid = bool(
                confirmed.filtered(lambda fee: fee.fee_type == "sop_reading")
            )
            request.demo_fee_paid = bool(
                confirmed.filtered(lambda fee: fee.fee_type == "operational_demo")
            )
            request.total_fees_confirmed = sum(confirmed.mapped("amount"))

    @api.depends("finance_confirmed_sop_fee", "operations_confirmed_sop")
    def _compute_dual_confirm_complete(self):
        for request in self:
            request.dual_confirm_complete = bool(
                request.finance_confirmed_sop_fee and request.operations_confirmed_sop
            )

    @api.model
    def _group_expand_state(self, states, domain):
        """Always show the whole pipeline in the grouped kanban."""
        # A copy: the ORM is free to sort this list in place.
        return list(MAIN_PATH_STATES)

    # ==================================================================
    # "My turn" helpers
    # ==================================================================
    @api.model
    def _user_roles(self, user):
        """Return the set of module roles ``user`` belongs to."""
        return {
            role for role, xmlid in ROLE_GROUP.items()
            if role != "manager" and user.has_group(xmlid)
        }

    def _matches_user_queue(self, roles):
        """Whether the record currently waits for one of ``roles``."""
        self.ensure_one()
        if self.state == "dual_confirm":
            # The parallel step is the one place where the queue is finer than
            # the status: each side drops out once it has signed, and whoever
            # still has to push the file on keeps it.
            return bool(set(self._pending_roles()) & set(roles))
        return any(self.state in ROLE_QUEUE_STATES.get(role, []) for role in roles)

    @api.model
    def _my_turn_domain(self, user):
        """The SQL counterpart of :meth:`_matches_user_queue`.

        Built with :class:`odoo.fields.Domain` rather than by splicing prefix
        operators by hand: ``|`` is binary and ``!`` unary, so concatenating a
        multi-leaf sub-domain behind one of them silently ANDs the leftovers
        onto the whole expression.
        """
        parts = []
        for role in self._user_roles(user):
            role_states = ROLE_QUEUE_STATES.get(role, [])
            states = [state for state in role_states if state != "dual_confirm"]
            if states:
                parts.append(Domain("state", "in", states))
            if "dual_confirm" not in role_states:
                continue
            on_step = Domain("state", "=", "dual_confirm")
            if role == "finance":
                # Finance is due while it has not signed, and again once both
                # sides have, because someone has to move the file on.
                parts.append(on_step & (
                    Domain("finance_confirmed_sop_fee", "=", False)
                    | Domain("operations_confirmed_sop", "=", True)
                ))
            else:
                parts.append(on_step & Domain("operations_confirmed_sop", "=", False))
        return Domain.OR(parts) if parts else Domain.FALSE

    def _search_is_my_turn(self, operator, value):
        if operator not in ("=", "!=", "in", "not in"):
            raise UserError(self.env._("Unsupported operator on the My Turn filter."))
        if operator in ("in", "not in"):
            truthy = bool(value) and any(value)
            positive = (operator == "in") == truthy
        else:
            positive = (operator == "=") == bool(value)
        domain = self._my_turn_domain(self.env.user)
        return domain if positive else ~domain

    # ==================================================================
    # CRUD
    # ==================================================================
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals["name"] in ("/", self.env._("New")):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "dma.accreditation.request"
                ) or self.env._("New")
            if not vals.get("verification_token"):
                vals["verification_token"] = uuid.uuid4().hex
        requests = super().create(vals_list)
        for request in requests:
            if not request.document_ids:
                request._populate_checklist()
        return requests

    def copy_data(self, default=None):
        vals_list = super().copy_data(default=default)
        for vals in vals_list:
            vals["name"] = self.env._("New")
            vals["verification_token"] = uuid.uuid4().hex
        return vals_list

    def _workflow_write(self, vals):
        """Write fields the workflow owns; see :data:`WORKFLOW_OWNED_FIELDS`."""
        return self.with_context(dma_workflow=True).write(vals)

    def write(self, vals):
        """Refuse direct writes to the fields that carry the legal meaning.

        Every department needs write access to the request (to fill in the SOP
        references, the committee minutes, the contact...), but that same right
        would otherwise let anyone set ``state`` to ``authorized`` over RPC and
        walk past every guard, every hard gate and the approval log. The
        workflow methods go through :meth:`_workflow_write`, which sets the
        ``dma_workflow`` context key; nothing else may touch those fields, not
        even privileged code that has not gone through an action.
        """
        if not self.env.context.get("dma_workflow"):
            protected = WORKFLOW_OWNED_FIELDS.intersection(vals)
            if protected:
                raise AccessError(self.env._(
                    "The fields %(fields)s are set by the accreditation workflow "
                    "itself and cannot be written directly. Use the buttons of "
                    "the request.",
                    fields=", ".join(sorted(protected)),
                ))
        return super().write(vals)

    def unlink(self):
        """Only a never-decided draft may be deleted.

        ``dma.approval.line`` cascades on the request, so deleting a file that
        already carries decisions would destroy its audit trail through the
        back door - including a file an administrator has reset to draft.
        Anything that has been decided on can only be archived.
        """
        for request in self:
            if request.state != "draft":
                raise UserError(self.env._(
                    "Only draft accreditation requests can be deleted; %(request)s is "
                    "in status %(state)s. Archive it instead.",
                    request=request.display_name,
                    state=state_label(self.env, request.state),
                ))
            if request.approval_line_ids:
                raise UserError(self.env._(
                    "%(request)s already carries %(count)s decision(s) in its "
                    "approvals log and can no longer be deleted. Archive it instead.",
                    request=request.display_name,
                    count=len(request.approval_line_ids),
                ))
        return super().unlink()

    # ==================================================================
    # Guards - the view level groups= is only cosmetic, this is authoritative
    # ==================================================================
    def _check_workflow_state(self, allowed_states, action_label):
        for request in self:
            if request.state not in allowed_states:
                raise ValidationError(self.env._(
                    "%(action)s is not available while %(request)s is in status "
                    "%(state)s.",
                    action=action_label,
                    request=request.display_name,
                    state=state_label(self.env, request.state),
                ))

    def _check_workflow_role(self, allowed_roles, action_label):
        user = self.env.user
        if self.env.su:
            return
        if any(user.has_group(ROLE_GROUP[role]) for role in allowed_roles):
            return
        raise AccessError(self.env._(
            "%(action)s may only be performed by: %(roles)s.",
            action=action_label,
            roles=", ".join(role_label(self.env, role) for role in allowed_roles),
        ))

    def _guard(self, allowed_states, allowed_roles, action_label):
        self._check_workflow_role(tuple(allowed_roles) + ("manager",), action_label)
        self._check_workflow_state(allowed_states, action_label)

    # ==================================================================
    # Audit trail / notifications
    # ==================================================================
    def _log_approval(self, step, role, decision, notes=False):
        """Append an immutable entry to the approval log."""
        self.ensure_one()
        return self.env["dma.approval.line"].sudo().create({
            "request_id": self.id,
            "step": step,
            "role": role,
            "decision": decision,
            "user_id": self.env.uid,
            "date": fields.Datetime.now(),
            "notes": notes or False,
        })

    def _acting_role(self, allowed_roles):
        """The role the current user is acting as, for the approval log."""
        user = self.env.user
        for role in allowed_roles:
            if user.has_group(ROLE_GROUP[role]):
                return role
        return "manager"

    def _close_automated_activities(self):
        """Clear the next-step activities scheduled by the previous transition."""
        self.ensure_one()
        self.env["mail.activity"].sudo().search([
            ("res_model", "=", self._name),
            ("res_id", "=", self.id),
            ("automated", "=", True),
        ]).unlink()

    def _responsible_users(self, role):
        group = self.env.ref(ROLE_GROUP[role], raise_if_not_found=False)
        if not group:
            return self.env["res.users"]
        users = group.sudo().user_ids.filtered(
            lambda user: user.active and not user.share
        )
        if not users:
            users = group.sudo().all_user_ids.filtered(
                lambda user: user.active and not user.share
            )
        return users[:20]

    # ==================================================================
    # Payload of the department dashboard
    # ==================================================================
    @api.model
    def get_dashboard_data(self):
        """Everything the dashboard shows, counted server side.

        Aggregating here rather than in the browser keeps the queue definitions
        in one place (they are the same ``ROLE_QUEUE_STATES`` the menus and the
        "My Turn" filter use), lets the record rules do their work, and makes
        the whole dashboard testable in Python.
        """
        self.check_access("read")
        user = self.env.user
        today = fields.Date.context_today(self)
        horizon = today + relativedelta(days=90)

        def count(domain):
            return self.search_count(domain)

        queues = []
        for role in ROLE_SELECTION:
            key = role[0]
            if key == "manager" or not user.has_group(ROLE_GROUP[key]):
                continue
            states = ROLE_QUEUE_STATES.get(key, [])
            if not states:
                continue
            domain = [("state", "in", states)]
            queues.append({
                "role": key,
                "label": role_label(self.env, key),
                "count": count(domain),
                "domain": domain,
            })

        pipeline = []
        for key in MAIN_PATH_STATES:
            pipeline.append({
                "key": key,
                "label": state_label(self.env, key),
                "count": count([("state", "=", key)]),
                "domain": [("state", "=", key)],
            })
        busiest = max((step["count"] for step in pipeline), default=0)
        for step in pipeline:
            step["percent"] = round(100.0 * step["count"] / busiest) if busiest else 0

        expiring = []
        soon = self.search([
            ("state", "=", "authorized"),
            ("expiry_date", "!=", False),
            ("expiry_date", "<=", horizon),
        ], order="expiry_date asc", limit=10)
        for request in soon:
            days = (request.expiry_date - today).days
            expiring.append({
                "id": request.id,
                "name": request.name,
                "partner": request.partner_id.display_name,
                "expiry_date": fields.Date.to_string(request.expiry_date),
                "days": days,
                # Status, not a series colour: it ships with a label, never
                # colour alone.
                "level": "critical" if days < 0 else ("serious" if days <= 30 else "warning"),
                "level_label": (
                    self.env._("Expired") if days < 0
                    else self.env._("%s days left", days)
                ),
            })

        return {
            "my_turn": count([("is_my_turn", "=", True)]),
            "queues": queues,
            "pipeline": pipeline,
            "expiring": expiring,
            "totals": {
                "in_progress": count([
                    ("state", "not in", ("draft", "authorized", "rejected")),
                ]),
                "authorized": count([("state", "=", "authorized")]),
                "rejected": count([("state", "=", "rejected")]),
                "returned": count([("state", "=", "returned")]),
            },
        }

    # ==================================================================
    # Payload of the progress widget
    # ==================================================================
    def _progress_blockers(self):
        """Everything standing between this file and its next step.

        Computed here rather than in the browser so it is covered by the
        Python tests and translated with the rest of the module.
        """
        self.ensure_one()
        blockers = []
        if self.state == "draft" and not self.scope_ids:
            blockers.append(self.env._("No accreditation scope has been requested."))
        elif self.state == "cert_check":
            for line in self._missing_checklist_lines():
                if not line.is_provided:
                    blockers.append(self.env._(
                        "%s has not been provided.", line.type_id.display_name,
                    ))
                else:
                    blockers.append(self.env._(
                        "%s is provided but not accepted yet.",
                        line.type_id.display_name,
                    ))
            if not self.required_document_count:
                blockers.append(self.env._("The prerequisites checklist is empty."))
        elif self.state == "sop_submission":
            if not self.sudo().sop_attachment_ids:
                blockers.append(self.env._("The electronic copy of the SOP is missing."))
            if not self.sop_paper_received:
                blockers.append(self.env._("The paper copy of the SOP is not registered."))
        elif self.state == "sop_fee" and not self._confirmed_fees("sop_reading"):
            blockers.append(self.env._("The SOP reading fee is not confirmed."))
        elif self.state == "dual_confirm":
            if not self.finance_confirmed_sop_fee:
                blockers.append(self.env._("The Finance Department has not signed off."))
            if not self.operations_confirmed_sop:
                blockers.append(self.env._("The Operations Department has not signed off."))
        elif self.state == "demo_fee" and not self._confirmed_fees("operational_demo"):
            blockers.append(self.env._(
                "The operational demonstration fee is not confirmed."
            ))
        elif self.state == "committee":
            if not self.committee_decision:
                blockers.append(self.env._("The committee decision is missing."))
            if not self.committee_date:
                blockers.append(self.env._("The date of the committee session is missing."))
            if is_html_empty(self.decision_text):
                blockers.append(self.env._("The decision text is empty."))
        elif self.state == "legal_refine" and is_html_empty(self.refined_decision_text):
            blockers.append(self.env._("The refined decision text is empty."))
        return blockers

    @api.depends(
        "state", "scope_ids", "approval_line_ids",
        "checklist_complete", "required_document_count",
        "sop_paper_received", "sop_attachment_ids",
        "sop_fee_paid", "demo_fee_paid",
        "finance_confirmed_sop_fee", "operations_confirmed_sop",
        "committee_decision", "committee_date", "decision_text",
        "refined_decision_text",
    )
    def _compute_progress_payload(self):
        """Feed the progress widget: one entry per step of the main path."""
        rtl = self.env["res.lang"]._lang_get(self.env.lang or "en_US").direction == "rtl"
        for request in self:
            decided = {}
            for line in request.approval_line_ids.sorted("id"):
                decided.setdefault(line.step, line)
            current = request.state
            reached = (
                MAIN_PATH_STATES.index(current)
                if current in MAIN_PATH_STATES
                else len(MAIN_PATH_STATES)
            )
            steps = []
            for index, key in enumerate(MAIN_PATH_STATES):
                line = decided.get(key)
                if key == current:
                    status = "current"
                elif index < reached or line:
                    status = "done"
                else:
                    status = "todo"
                steps.append({
                    "key": key,
                    "number": index + 1,
                    "label": state_label(self.env, key),
                    "role": role_label(self.env, STATE_PENDING_ROLE.get(key) or "manager"),
                    "status": status,
                    "user": line.user_id.display_name if line else False,
                    "date": fields.Datetime.to_string(line.date) if line else False,
                })
            steps_done = sum(1 for step in steps if step["status"] == "done")
            request.progress_payload = {
                "rtl": rtl,
                "current": current,
                "current_label": state_label(self.env, current),
                "closed": current in ("authorized", "rejected"),
                "exception": current if current in ("returned", "rejected") else False,
                "exception_label": (
                    state_label(self.env, current)
                    if current in ("returned", "rejected") else False
                ),
                "steps": steps,
                "steps_done": steps_done,
                "steps_total": len(steps),
                "percent": round(100.0 * steps_done / len(steps)) if steps else 0,
                "pending_role": (
                    role_label(self.env, request.pending_group)
                    if request.pending_group else False
                ),
                # The technical key alongside the label, so automation can
                # target a role without matching translated text.
                "pending_role_key": request.pending_group or False,
                "blockers": request._progress_blockers(),
            }

    def _pending_roles(self):
        """Roles that still have to act on the request at its current step.

        The dual confirmation is the one step with *two* responsible
        departments at the same time, and each of them drops off the list as
        soon as it has signed.
        """
        self.ensure_one()
        if self.state == "dual_confirm":
            roles = []
            if not self.finance_confirmed_sop_fee:
                roles.append("finance")
            if not self.operations_confirmed_sop:
                roles.append("operations")
            # Both signed: someone still has to push the file to the next step.
            return roles or ["finance"]
        role = STATE_PENDING_ROLE.get(self.state)
        return [role] if role else []

    def _schedule_next_step_activity(self):
        """Re-arm the to-do of every department that still has to act.

        Always called after a change of status *or* of a dual confirmation
        flag: it first clears the automated activities of the previous step so
        an officer never keeps a to-do for something already done, and never
        collects a duplicate one.
        """
        self.ensure_one()
        self._close_automated_activities()
        roles = self._pending_roles()
        if not roles:
            return
        summary = self.env._(
            "Accreditation step: %s", state_label(self.env, self.state),
        )
        for role in roles:
            users = self._responsible_users(role)
            if not users:
                continue
            note = self.env._(
                "Request %(ref)s of %(partner)s is waiting for %(role)s.",
                ref=self.name,
                partner=self.partner_id.display_name,
                role=role_label(self.env, role),
            )
            for user in users:
                self.sudo().activity_schedule(
                    "mail.mail_activity_data_todo",
                    user_id=user.id,
                    summary=summary,
                    note=note,
                )

    def _apply_transition(self, new_state, role, decision, notes=False, body=None):
        """Single funnel for every state change: log, chatter, activities."""
        self.ensure_one()
        old_state = self.state
        self._workflow_write({"state": new_state})
        self._log_approval(old_state, role, decision, notes)
        message = body or self.env._(
            "%(from_state)s to %(to_state)s by %(user)s (%(role)s).",
            from_state=state_label(self.env, old_state),
            to_state=state_label(self.env, new_state),
            user=self.env.user.name,
            role=role_label(self.env, role),
        )
        if notes:
            message = Markup("%s<br/><b>%s</b> %s") % (
                message, self.env._("Notes:"), notes,
            )
        self.message_post(body=message)
        self._schedule_next_step_activity()

    def _mail_get_partner_fields(self, introspect_fields=False):
        """Address the applicant's representative, not just the organisation.

        Odoo picks the default recipient of a mail template from these fields
        (``use_default_to`` is True by default on ``mail.template``), so without
        this the notifications - and the "Send message" recipients in the
        chatter - would go to the company address instead of the person who
        filed the application. ``contact_partner_id`` comes first;
        ``partner_id`` stays as the fallback when no contact is known.
        """
        return ["contact_partner_id", "partner_id"]

    def _send_template(self, template_xmlid):
        """Send a ``mail.template`` to the applicant, tolerating a missing address."""
        self.ensure_one()
        template = self.env.ref(template_xmlid, raise_if_not_found=False)
        if not template:
            _logger.warning("Mail template %s is missing", template_xmlid)
            return False
        if not (self.contact_email or self.partner_id.email):
            self.message_post(body=self.env._(
                "No e-mail address is known for the applicant; the notification "
                "could not be sent."
            ))
            return False
        return template.sudo().send_mail(self.id, force_send=False)

    def _generate_report_attachment(self, report_xmlid, filename):
        """Render a QWeb report to PDF and attach it to the request.

        Rendering is best effort: on a server without ``wkhtmltopdf`` the
        workflow must still complete, so a failure is logged and reported in the
        chatter instead of blocking the officer.
        """
        self.ensure_one()
        report = self.env.ref(report_xmlid, raise_if_not_found=False)
        if not report:
            _logger.warning("Report %s is missing", report_xmlid)
            return False
        try:
            content, _content_type = report.sudo()._render_qweb_pdf(
                report_xmlid, res_ids=self.ids,
            )
        except Exception:  # noqa: BLE001 - a PDF engine must never block the workflow
            _logger.warning(
                "Could not render %s for %s; is wkhtmltopdf installed?",
                report_xmlid, self.display_name, exc_info=True,
            )
            self.message_post(body=self.env._(
                "The PDF of %s could not be generated on this server. It can be "
                "printed again from the Print menu.", filename,
            ))
            return False
        attachment = self.env["ir.attachment"].sudo().create({
            "name": filename,
            "type": "binary",
            "raw": content,
            "res_model": self._name,
            "res_id": self.id,
            "mimetype": "application/pdf",
        })
        self.message_post(
            body=self.env._("Official document generated: %s", filename),
            attachment_ids=attachment.ids,
        )
        return attachment

    # ==================================================================
    # Checklist / fee helpers
    # ==================================================================
    def _populate_checklist(self):
        """Create one checklist line per active document type."""
        self.ensure_one()
        doc_types = self.env["dma.document.type"].sudo().search([])
        existing = self.document_ids.type_id
        commands = [
            fields.Command.create({
                "type_id": doc_type.id,
                "is_required": doc_type.required_default,
                "sequence": doc_type.sequence,
            })
            for doc_type in doc_types if doc_type not in existing
        ]
        if commands:
            self.sudo().write({"document_ids": commands})

    def action_reload_checklist(self):
        """Add the document types that were created after the request."""
        for request in self:
            request._check_workflow_role(
                ("reception", "cert_officer", "manager"),
                self.env._("Reload Checklist"),
            )
            request._populate_checklist()
        return True

    def action_mark_all_provided(self):
        """Tick every checklist line as provided (Reception assembling a file)."""
        for request in self:
            request._check_workflow_role(
                ("reception", "cert_officer", "manager"),
                self.env._("Mark the checklist as provided"),
            )
            request.document_ids.filtered(lambda line: not line.is_provided).write({
                "is_provided": True,
            })
        return True

    def action_accept_all_provided(self):
        """Accept every provided line at once (Certifications Division)."""
        for request in self:
            request._check_workflow_role(
                ("cert_officer",), self.env._("Accept the checklist"),
            )
            pending = request.document_ids.filtered(
                lambda line: line.is_provided and line.review_result != "accepted"
            )
            if not pending:
                raise UserError(self.env._(
                    "There is no provided document waiting to be accepted on %s.",
                    request.display_name,
                ))
            pending.write({"review_result": "accepted"})
            request.message_post(body=self.env._(
                "%(count)s document(s) accepted by %(user)s.",
                count=len(pending), user=self.env.user.name,
            ))
        return True

    def _missing_checklist_lines(self):
        self.ensure_one()
        return self.document_ids.filtered(
            lambda line: line.is_required
            and not (line.is_provided and line.review_result == "accepted")
        )

    def _confirmed_fees(self, fee_type):
        self.ensure_one()
        return self.fee_ids.filtered(
            lambda fee: fee.fee_type == fee_type and fee.state == "confirmed"
        )

    # ==================================================================
    # Phase 1 - Office Accreditation
    # ==================================================================
    def action_submit(self):
        """Reception registers the application (draft -> submitted)."""
        label = self.env._("Submit Request")
        for request in self:
            request._guard(("draft",), ("reception",), label)
            if not request.scope_ids:
                raise ValidationError(self.env._(
                    "At least one accreditation scope must be requested before "
                    "submitting %s.", request.display_name,
                ))
            request._workflow_write({
                "submission_date": fields.Date.context_today(request),
            })
            request._apply_transition(
                "submitted", request._acting_role(("reception", "manager")), "confirmed",
            )
        return True

    def action_send_to_general_director(self):
        """Reception forwards the file for the initial acceptance of the GD."""
        label = self.env._("Send to General Director")
        for request in self:
            request._guard(("submitted",), ("reception",), label)
            request._apply_transition(
                "gd_review", request._acting_role(("reception", "manager")), "confirmed",
            )
        return True

    def action_gd_accept(self):
        """General Director initial acceptance (gd_review -> legal_review)."""
        label = self.env._("Initial Acceptance")
        for request in self:
            request._guard(("gd_review",), ("general_director",), label)
            request._apply_transition(
                "legal_review",
                request._acting_role(("general_director", "manager")),
                "approved",
            )
        return True

    def action_legal_approve(self):
        """Legal Department Director approval (legal_review -> cert_check)."""
        label = self.env._("Legal Approval")
        for request in self:
            request._guard(("legal_review",), ("legal_director",), label)
            request._apply_transition(
                "cert_check",
                request._acting_role(("legal_director", "manager")),
                "approved",
            )
        return True

    def action_grant_office_accreditation(self):
        """Hard gate: grant the office accreditation (cert_check -> office_granted).

        Every *required* checklist line must be both provided and accepted by
        the Certifications Division, otherwise the transition is refused.
        """
        label = self.env._("Grant Office Accreditation")
        for request in self:
            request._guard(
                ("cert_check",), ("cert_officer", "general_director"), label,
            )
            missing = request._missing_checklist_lines()
            if missing:
                raise ValidationError(self.env._(
                    "The office accreditation cannot be granted: the following "
                    "required documents are not provided and accepted yet:\n%s",
                    "\n".join("- %s" % line.type_id.display_name for line in missing),
                ))
            if not request.required_document_count:
                raise ValidationError(self.env._(
                    "The prerequisites checklist of %s is empty; load the document "
                    "types before granting the office accreditation.",
                    request.display_name,
                ))
            request._workflow_write({
                "office_ref": request.office_ref or self.env["ir.sequence"].next_by_code(
                    "dma.accreditation.office"
                ),
                "office_date": fields.Date.context_today(request),
            })
            request._apply_transition(
                "office_granted",
                request._acting_role(("cert_officer", "general_director", "manager")),
                "approved",
            )
            # (a) notify the applicant, (b) issue the official letter.
            request._send_template("dma_accreditation.mail_template_office_granted")
            request._generate_report_attachment(
                "dma_accreditation.action_report_office_letter",
                self.env._("Office Accreditation Letter - %s.pdf", request.name),
            )
        return True

    # ==================================================================
    # Phase 2 - Operational Accreditation
    # ==================================================================
    def action_start_operational_phase(self):
        """Open the SOP submission step (office_granted -> sop_submission)."""
        label = self.env._("Start Operational Accreditation")
        for request in self:
            request._guard(
                ("office_granted",), ("operations", "reception"), label,
            )
            request._apply_transition(
                "sop_submission",
                request._acting_role(("operations", "reception", "manager")),
                "confirmed",
            )
        return True

    def action_register_paper_sop(self):
        """Operations records the reception of the paper SOP."""
        label = self.env._("Register Paper SOP")
        for request in self:
            request._guard(("sop_submission",), ("operations",), label)
            request._workflow_write({
                "sop_paper_received": True,
                "sop_paper_received_by": self.env.uid,
                "sop_paper_received_date": fields.Date.context_today(request),
            })
            request.message_post(body=self.env._(
                "Paper copy of the SOP received by %s.", self.env.user.name,
            ))
        return True

    def action_sop_received(self):
        """Both SOP copies are in (sop_submission -> sop_fee)."""
        label = self.env._("Confirm SOP Submission")
        for request in self:
            request._guard(("sop_submission",), ("operations",), label)
            if not request.sudo().sop_attachment_ids:
                raise ValidationError(self.env._(
                    "The electronic copy of the SOP of %s is missing.",
                    request.display_name,
                ))
            if not request.sop_paper_received:
                raise ValidationError(self.env._(
                    "The paper copy of the SOP of %s has not been registered yet.",
                    request.display_name,
                ))
            request._apply_transition(
                "sop_fee",
                request._acting_role(("operations", "manager")),
                "confirmed",
            )
        return True

    def action_sop_fee_registered(self):
        """Finance registered the SOP reading fee (sop_fee -> dual_confirm)."""
        label = self.env._("Confirm SOP Reading Fee")
        for request in self:
            request._guard(("sop_fee",), ("finance",), label)
            if not request._confirmed_fees("sop_reading"):
                raise ValidationError(self.env._(
                    "A confirmed SOP reading fee is required before %s can move on.",
                    request.display_name,
                ))
            request._apply_transition(
                "dual_confirm",
                request._acting_role(("finance", "manager")),
                "confirmed",
            )
        return True

    def action_finance_confirm(self):
        """Finance side of the parallel dual confirmation."""
        label = self.env._("Finance Confirmation")
        for request in self:
            request._guard(("dual_confirm",), ("finance",), label)
            if request.finance_confirmed_sop_fee:
                raise UserError(self.env._(
                    "Finance already confirmed %s.", request.display_name,
                ))
            request._workflow_write({
                "finance_confirmed_sop_fee": True,
                "finance_confirmed_by": self.env.uid,
                "finance_confirmed_on": fields.Datetime.now(),
            })
            request._log_approval(
                "dual_confirm",
                request._acting_role(("finance", "manager")),
                "confirmed",
                self.env._("Receipt of the request and of the SOP reading fee confirmed."),
            )
            request.message_post(body=self.env._(
                "Finance confirmed the receipt of the request and of the SOP "
                "reading fee (%s).", self.env.user.name,
            ))
            request._schedule_next_step_activity()
        return True

    def action_operations_confirm(self):
        """Operations side of the parallel dual confirmation."""
        label = self.env._("Operations Confirmation")
        for request in self:
            request._guard(("dual_confirm",), ("operations",), label)
            if request.operations_confirmed_sop:
                raise UserError(self.env._(
                    "Operations already confirmed %s.", request.display_name,
                ))
            request._workflow_write({
                "operations_confirmed_sop": True,
                "operations_confirmed_by": self.env.uid,
                "operations_confirmed_on": fields.Datetime.now(),
            })
            request._log_approval(
                "dual_confirm",
                request._acting_role(("operations", "manager")),
                "confirmed",
                self.env._("Receipt of the company SOP for appraisal confirmed."),
            )
            request.message_post(body=self.env._(
                "Operations confirmed the receipt of the company SOP for "
                "appraisal (%s).", self.env.user.name,
            ))
            request._schedule_next_step_activity()
        return True

    def action_dual_confirm_done(self):
        """Hard gate: both parties must have signed off (dual_confirm -> demo_fee)."""
        label = self.env._("Proceed to the Demonstration Fee")
        for request in self:
            request._guard(("dual_confirm",), ("finance", "operations"), label)
            if not request.finance_confirmed_sop_fee:
                raise ValidationError(self.env._(
                    "Finance has not confirmed the receipt of the request and of "
                    "the SOP reading fee of %s yet.", request.display_name,
                ))
            if not request.operations_confirmed_sop:
                raise ValidationError(self.env._(
                    "Operations has not confirmed the receipt of the SOP of %s yet.",
                    request.display_name,
                ))
            request._apply_transition(
                "demo_fee",
                request._acting_role(("finance", "operations", "manager")),
                "confirmed",
            )
        return True

    def action_demo_fee_registered(self):
        """Finance confirmed the operational demonstration fee (demo_fee -> committee)."""
        label = self.env._("Confirm Demonstration Fee")
        for request in self:
            request._guard(("demo_fee",), ("finance",), label)
            if not request._confirmed_fees("operational_demo"):
                raise ValidationError(self.env._(
                    "A confirmed operational demonstration fee is required before "
                    "%s can be sent to the Accreditation Committee.",
                    request.display_name,
                ))
            request._apply_transition(
                "committee",
                request._acting_role(("finance", "manager")),
                "confirmed",
            )
        return True

    def action_committee_decision(self):
        """The Accreditation Committee records its decision."""
        label = self.env._("Record Committee Decision")
        for request in self:
            request._guard(("committee",), ("committee",), label)
            if not request.committee_decision:
                raise ValidationError(self.env._(
                    "The decision of the Accreditation Committee on %s is missing.",
                    request.display_name,
                ))
            if not request.committee_date:
                raise ValidationError(self.env._(
                    "The date of the Accreditation Committee session on %s is missing.",
                    request.display_name,
                ))
            if is_html_empty(request.decision_text):
                raise ValidationError(self.env._(
                    "The decision text of the Accreditation Committee on %s is missing.",
                    request.display_name,
                ))
            role = request._acting_role(("committee", "manager"))
            if request.committee_decision == "reject":
                request._workflow_write({"reject_reason": self.env._(
                    "Rejected by the Accreditation Committee on %s.",
                    request.committee_date,
                )})
                request._apply_transition("rejected", role, "rejected")
                request._send_template(
                    "dma_accreditation.mail_template_request_returned"
                )
            else:
                request._apply_transition("legal_refine", role, "approved")
        return True

    def action_issue_authorization(self):
        """Legal refinement is done: issue the operational accreditation."""
        label = self.env._("Issue Operational Accreditation")
        for request in self:
            request._guard(
                ("legal_refine",), ("legal_director", "general_director"), label,
            )
            if is_html_empty(request.refined_decision_text):
                raise ValidationError(self.env._(
                    "The Legal Department has to refine the decision text of %s "
                    "before the operational accreditation can be issued.",
                    request.display_name,
                ))
            issue_date = fields.Date.context_today(request)
            request._workflow_write({
                "legal_refined_by": self.env.uid,
                "legal_refined_on": fields.Datetime.now(),
                "certificate_ref": request.certificate_ref or self.env[
                    "ir.sequence"
                ].next_by_code("dma.accreditation.certificate"),
                "issue_date": issue_date,
                "expiry_date": request._compute_expiry_date(issue_date),
            })
            request._apply_transition(
                "authorized",
                request._acting_role(("legal_director", "general_director", "manager")),
                "approved",
            )
            request._send_template(
                "dma_accreditation.mail_template_operational_granted"
            )
            request._generate_report_attachment(
                "dma_accreditation.action_report_certificate",
                self.env._("Operational Accreditation Certificate - %s.pdf", request.name),
            )
        return True

    def _compute_expiry_date(self, issue_date):
        """Validity of an operational accreditation, in months, from the settings."""
        self.ensure_one()
        raw = self.env["ir.config_parameter"].sudo().get_param(
            "dma_accreditation.validity_months", "12",
        )
        try:
            months = int(float(raw))
        except (TypeError, ValueError):
            months = 12
        months = max(months, 1)
        return issue_date + relativedelta(months=months, days=-1)

    # ==================================================================
    # Cross cutting - return / reject / resume
    # ==================================================================
    def _open_reason_wizard(self, mode):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": (
                self.env._("Return to Applicant") if mode == "return"
                else self.env._("Reject Request")
            ),
            "res_model": "dma.decision.reason",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_request_id": self.id,
                "default_mode": mode,
            },
        }

    def action_open_return_wizard(self):
        return self._open_reason_wizard("return")

    def action_open_reject_wizard(self):
        return self._open_reason_wizard("reject")

    def _reviewer_roles_for_state(self, state):
        """Roles allowed to return or reject a request sitting in ``state``."""
        role = STATE_PENDING_ROLE.get(state)
        return (role,) if role else ("manager",)

    def action_return_to_applicant(self, reason):
        """Send the request one step back with a mandatory reason."""
        label = self.env._("Return to Applicant")
        if not reason or not reason.strip():
            raise ValidationError(self.env._(
                "A reason is required to return a request to the applicant."
            ))
        for request in self:
            roles = request._reviewer_roles_for_state(request.state)
            request._guard(REVIEWABLE_STATES, roles, label)
            target = RETURN_TARGET_STATE.get(request.state, "draft")
            request._workflow_write({
                "return_reason": reason, "return_to_state": target,
            })
            request._apply_transition(
                "returned", request._acting_role(roles + ("manager",)), "returned", reason,
            )
            request._send_template("dma_accreditation.mail_template_request_returned")
        return True

    def action_reject(self, reason):
        """Definitively reject the request with a mandatory reason."""
        label = self.env._("Reject Request")
        if not reason or not reason.strip():
            raise ValidationError(self.env._(
                "A reason is required to reject a request."
            ))
        for request in self:
            roles = request._reviewer_roles_for_state(request.state)
            request._guard(REVIEWABLE_STATES, roles, label)
            request._workflow_write({"reject_reason": reason})
            request._apply_transition(
                "rejected", request._acting_role(roles + ("manager",)), "rejected", reason,
            )
            request._send_template("dma_accreditation.mail_template_request_returned")
        return True

    def action_resume_from_return(self):
        """Put a returned request back on its step once the applicant answered."""
        label = self.env._("Resume Request")
        for request in self:
            request._guard(("returned",), ("reception",), label)
            target = request.return_to_state or "draft"
            request._workflow_write({"return_to_state": False})
            request._apply_transition(
                target, request._acting_role(("reception", "manager")), "confirmed",
            )
        return True

    def action_reset_to_draft(self):
        """Administrative reset, restricted to the Accreditation Manager.

        The evidence stays on the file - the documents, the fees, the SOP and
        the whole approval log - but the *attestations* of the previous pass are
        dropped: a sign-off says "I checked this on that day", so it has to be
        given again rather than silently satisfying the gates a second time.
        """
        label = self.env._("Reset to Draft")
        for request in self:
            request._check_workflow_role(("manager",), label)
            if request.state == "draft":
                continue
            request._workflow_write({
                "sop_paper_received": False,
                "sop_paper_received_by": False,
                "sop_paper_received_date": False,
                "finance_confirmed_sop_fee": False,
                "finance_confirmed_by": False,
                "finance_confirmed_on": False,
                "operations_confirmed_sop": False,
                "operations_confirmed_by": False,
                "operations_confirmed_on": False,
                "return_to_state": False,
            })
            request._apply_transition(
                "draft", "manager", "returned",
                notes=self.env._(
                    "Administrative reset: the sign-offs of the previous pass "
                    "have to be given again."
                ),
            )
        return True

    # ==================================================================
    # Reporting helpers used by the QWeb templates
    # ==================================================================
    def get_verification_url(self):
        """Absolute URL a verifier reaches by scanning the QR of a document."""
        self.ensure_one()
        base = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "")
        return f"{base}/dma/verify/{self.verification_token or ''}"

    def action_print_office_letter(self):
        return self.env.ref(
            "dma_accreditation.action_report_office_letter"
        ).report_action(self)

    def action_print_certificate(self):
        return self.env.ref(
            "dma_accreditation.action_report_certificate"
        ).report_action(self)

    def action_print_summary(self):
        return self.env.ref(
            "dma_accreditation.action_report_request_summary"
        ).report_action(self)
