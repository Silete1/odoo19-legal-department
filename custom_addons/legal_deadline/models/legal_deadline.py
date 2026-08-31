from odoo import _, fields, models, tools
from odoo.exceptions import UserError


class LegalDeadline(models.Model):
    """The control tower: every clock in the suite, one surface.

    A read-only SQL view that UNIONs the eleven clocks the legal suite runs -
    statutory obligation periods, case SLAs, awaited replies, expiring
    documents, powers of attorney and contracts, upcoming hearings, open
    appeal windows, contract obligation occurrences, request response dates
    and opinion due dates - into one dated board.

    Deliberately a view and not a table: a copied deadline is a deadline that
    can go stale, and a board people cannot trust is a board people stop
    reading. Every row here IS the source row, projected; discharging the
    obligation at its source removes it from the board in the same
    transaction. Each arm carries a literal source index so the synthetic id
    is stable and unique across sources, and every arm projects its source's
    company so the ordinary record rule does the fencing.
    """

    _name = "legal.deadline"
    _description = "Legal Deadline"
    _auto = False
    _order = "date_due asc, id"

    # The ORM flushes these before querying the view, so a row created in the
    # current transaction is visible to a search without a manual flush.
    _depends = {
        "legal.obligation.instance": [
            "due_on", "state", "active", "company_id", "schedule_id", "period_key",
        ],
        "legal.obligation.schedule": ["name", "code"],
        "legal.case": [
            "name", "sla_due_on", "is_closed", "user_id", "company_id",
            "priority", "active",
        ],
        "legal.correspondence": [
            "subject", "our_number", "their_number", "reply_expected",
            "reply_due_on", "reply_to_id", "is_substantive_reply", "state",
            "user_id", "company_id", "active",
        ],
        "legal.document": ["name", "state", "expiry_date", "company_id", "active"],
        "legal.poa": [
            "name", "state", "expiry_date", "agent_user_id", "company_id", "active",
        ],
        "legal.hearing": [
            "date", "is_held", "lawyer_id", "company_id", "lawsuit_id", "active",
        ],
        "legal.judgment": [
            "appeal_deadline", "appeal_state", "lawyer_id", "company_id",
            "lawsuit_id", "active",
        ],
        "legal.lawsuit": ["reference", "title", "is_closed", "priority", "active"],
        "legal.contract": [
            "name", "title", "state", "is_closed", "expiry_date",
            "internal_owner_id", "legal_officer_id", "company_id", "active",
        ],
        "legal.contract.obligation": ["name", "active"],
        "legal.contract.obligation.instance": [
            "due_date", "state", "period_key", "responsible_user_id",
            "company_id", "obligation_id", "active",
        ],
        "legal.request": [
            "reference", "subject", "state", "target_response_date",
            "assigned_officer_id", "urgency", "company_id", "active",
        ],
        "legal.opinion": [
            "name", "subject", "state", "due_date", "legal_officer_id", "company_id",
        ],
    }

    name = fields.Char(
        string="What Is Due",
        readonly=True,
        help="One line naming the thing the clock is attached to.",
    )
    kind = fields.Selection(
        [
            ("obligation", "Statutory Obligation"),
            ("case_sla", "Case SLA"),
            ("correspondence_reply", "Awaited Reply"),
            ("document_expiry", "Document Expiry"),
            ("poa_expiry", "Power Of Attorney Expiry"),
            ("hearing", "Court Hearing"),
            ("appeal_window", "Appeal Window"),
            ("contract_obligation", "Contract Obligation"),
            ("contract_expiry", "Contract Expiry"),
            ("request_due", "Request Response"),
            ("opinion_due", "Opinion Due"),
        ],
        string="Kind",
        readonly=True,
        help="Which register the deadline comes from.",
    )
    date_due = fields.Date(
        string="Due Date",
        readonly=True,
        help="The date the law, the contract or the undertaking sets. "
        "The board is ordered by it.",
    )
    user_id = fields.Many2one(
        "res.users",
        string="Responsible",
        readonly=True,
        help="Who is expected to act. Empty when the source register does "
        "not name a person.",
    )
    company_id = fields.Many2one("res.company", string="Company", readonly=True)
    res_model = fields.Char(string="Source Model", readonly=True)
    res_id = fields.Integer(string="Source ID", readonly=True)
    state = fields.Selection(
        [
            ("open", "Open"),
            ("overdue", "Overdue"),
            ("done", "Done"),
        ],
        string="Status",
        readonly=True,
        help="Overdue the moment the due date is behind today. Rows already "
        "discharged at their source never reach this board.",
    )
    priority = fields.Selection(
        [("0", "Normal"), ("1", "Urgent"), ("2", "Critical")],
        string="Priority",
        readonly=True,
    )

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(
            "CREATE OR REPLACE VIEW %s AS (%s)" % (self._table, self._query())
        )

    @staticmethod
    def _query():
        """The eleven arms, one per clock.

        Each arm projects the same ten columns in the same order and casts
        them to the same types, carries its literal source index in the
        synthetic id, and filters out everything its own register already
        considers discharged - so the board never needs a 'done' filter to
        be readable. Translated jsonb names prefer the ar_001 value (Arabic-first product) and fall back to en_US
        key, which is the base language every value is guaranteed to carry.
        """
        return """
        SELECT 10000000::bigint * 1 + oi.id AS id,
               COALESCE(COALESCE(s.name->>'ar_001', s.name->>'en_US'), s.code) || ' - ' || oi.period_key AS name,
               'obligation' AS kind,
               oi.due_on AS date_due,
               NULL::integer AS user_id,
               oi.company_id AS company_id,
               'legal.obligation.instance' AS res_model,
               oi.id AS res_id,
               CASE WHEN oi.due_on < CURRENT_DATE THEN 'overdue' ELSE 'open' END AS state,
               NULL::varchar AS priority
          FROM legal_obligation_instance oi
          JOIN legal_obligation_schedule s ON s.id = oi.schedule_id
         WHERE oi.active
           AND oi.state NOT IN ('filed', 'waived')
           AND oi.due_on IS NOT NULL

        UNION ALL

        SELECT 10000000::bigint * 2 + c.id,
               c.name,
               'case_sla',
               c.sla_due_on::date,
               c.user_id,
               c.company_id,
               'legal.case',
               c.id,
               CASE WHEN c.sla_due_on::date < CURRENT_DATE THEN 'overdue' ELSE 'open' END,
               c.priority
          FROM legal_case c
         WHERE c.active
           AND c.is_closed = false
           AND c.sla_due_on IS NOT NULL

        UNION ALL

        SELECT 10000000::bigint * 3 + co.id,
               COALESCE(COALESCE(co.subject->>'ar_001', co.subject->>'en_US'), co.our_number, co.their_number),
               'correspondence_reply',
               co.reply_due_on,
               co.user_id,
               co.company_id,
               'legal.correspondence',
               co.id,
               CASE WHEN co.reply_due_on < CURRENT_DATE THEN 'overdue' ELSE 'open' END,
               NULL::varchar
          FROM legal_correspondence co
         WHERE co.active
           AND co.reply_expected
           AND co.state = 'registered'
           AND co.reply_due_on IS NOT NULL
           AND NOT EXISTS (
                   SELECT 1
                     FROM legal_correspondence answer
                    WHERE answer.reply_to_id = co.id
                      AND answer.is_substantive_reply
               )

        UNION ALL

        SELECT 10000000::bigint * 4 + d.id,
               d.name,
               'document_expiry',
               d.expiry_date,
               NULL::integer,
               d.company_id,
               'legal.document',
               d.id,
               CASE WHEN d.expiry_date < CURRENT_DATE THEN 'overdue' ELSE 'open' END,
               NULL::varchar
          FROM legal_document d
          JOIN legal_document_type dt ON dt.id = d.document_type_id
         WHERE d.active
           AND d.state = 'active'
           AND d.expiry_date IS NOT NULL
           -- the filed signed-contract copy mirrors the contract's own expiry
           -- row; one renewal date must not appear twice on the board
           AND COALESCE(dt.code, '') != 'SIGNED-CONTRACT'

        UNION ALL

        SELECT 10000000::bigint * 5 + p.id,
               p.name,
               'poa_expiry',
               p.expiry_date,
               p.agent_user_id,
               p.company_id,
               'legal.poa',
               p.id,
               CASE WHEN p.expiry_date < CURRENT_DATE THEN 'overdue' ELSE 'open' END,
               NULL::varchar
          FROM legal_poa p
         WHERE p.active
           AND p.state = 'active'
           AND p.expiry_date IS NOT NULL

        UNION ALL

        SELECT 10000000::bigint * 6 + h.id,
               COALESCE(l.reference, COALESCE(l.title->>'ar_001', l.title->>'en_US')),
               'hearing',
               h.date::date,
               h.lawyer_id,
               h.company_id,
               'legal.hearing',
               h.id,
               CASE WHEN h.date::date < CURRENT_DATE THEN 'overdue' ELSE 'open' END,
               l.priority
          FROM legal_hearing h
          JOIN legal_lawsuit l ON l.id = h.lawsuit_id
         WHERE h.active
           AND l.active
           AND h.is_held = false
           AND l.is_closed = false
           AND h.date IS NOT NULL
           AND h.date::date >= CURRENT_DATE

        UNION ALL

        SELECT 10000000::bigint * 7 + j.id,
               COALESCE(l.reference, COALESCE(l.title->>'ar_001', l.title->>'en_US')),
               'appeal_window',
               j.appeal_deadline,
               j.lawyer_id,
               j.company_id,
               'legal.judgment',
               j.id,
               CASE WHEN j.appeal_deadline < CURRENT_DATE THEN 'overdue' ELSE 'open' END,
               l.priority
          FROM legal_judgment j
          JOIN legal_lawsuit l ON l.id = j.lawsuit_id
         WHERE j.active
           AND l.active
           AND j.appeal_deadline IS NOT NULL
           AND j.appeal_state IN ('open', 'closing_soon')

        UNION ALL

        SELECT 10000000::bigint * 8 + ct.id,
               COALESCE(COALESCE(ct.title->>'ar_001', ct.title->>'en_US'), ct.name),
               'contract_expiry',
               ct.expiry_date,
               COALESCE(ct.internal_owner_id, ct.legal_officer_id),
               ct.company_id,
               'legal.contract',
               ct.id,
               CASE WHEN ct.expiry_date < CURRENT_DATE THEN 'overdue' ELSE 'open' END,
               NULL::varchar
          FROM legal_contract ct
         WHERE ct.active
           AND ct.state = 'active'
           AND ct.is_closed = false
           AND ct.expiry_date IS NOT NULL

        UNION ALL

        SELECT 10000000::bigint * 9 + coi.id,
               COALESCE(COALESCE(cob.name->>'ar_001', cob.name->>'en_US') || ' - ' || coi.period_key, coi.period_key),
               'contract_obligation',
               coi.due_date,
               coi.responsible_user_id,
               coi.company_id,
               'legal.contract.obligation.instance',
               coi.id,
               CASE WHEN coi.due_date < CURRENT_DATE THEN 'overdue' ELSE 'open' END,
               NULL::varchar
          FROM legal_contract_obligation_instance coi
          JOIN legal_contract_obligation cob ON cob.id = coi.obligation_id
         WHERE coi.active
           AND cob.active
           AND coi.state IN ('pending', 'late')
           AND coi.due_date IS NOT NULL

        UNION ALL

        -- One-off contractual obligations carry their own due date and never
        -- materialise instance rows; without this arm a single bank-guarantee
        -- renewal simply never reached the board (UAT scenario B).
        SELECT 10000000::bigint * 12 + cob2.id,
               COALESCE(cob2.name->>'ar_001', cob2.name->>'en_US'),
               'contract_obligation',
               cob2.due_date,
               cob2.responsible_user_id,
               ct2.company_id,
               'legal.contract.obligation',
               cob2.id,
               CASE WHEN cob2.due_date < CURRENT_DATE THEN 'overdue' ELSE 'open' END,
               NULL::varchar
          FROM legal_contract_obligation cob2
          JOIN legal_contract ct2 ON ct2.id = cob2.contract_id
         WHERE cob2.frequency = 'one_off'
           AND cob2.status = 'pending'
           AND cob2.due_date IS NOT NULL
           AND ct2.state NOT IN ('expired', 'terminated', 'closed')

        UNION ALL

        SELECT 10000000::bigint * 10 + r.id,
               COALESCE(COALESCE(r.subject->>'ar_001', r.subject->>'en_US'), r.reference),
               'request_due',
               r.target_response_date,
               r.assigned_officer_id,
               r.company_id,
               'legal.request',
               r.id,
               CASE WHEN r.target_response_date < CURRENT_DATE THEN 'overdue' ELSE 'open' END,
               CASE r.urgency WHEN 'urgent' THEN '2' WHEN 'high' THEN '1' ELSE '0' END
          FROM legal_request r
         WHERE r.active
           AND r.state NOT IN ('approved', 'closed', 'cancelled')
           AND r.target_response_date IS NOT NULL

        UNION ALL

        SELECT 10000000::bigint * 11 + o.id,
               COALESCE(COALESCE(o.subject->>'ar_001', o.subject->>'en_US'), o.name),
               'opinion_due',
               o.due_date,
               o.legal_officer_id,
               o.company_id,
               'legal.opinion',
               o.id,
               CASE WHEN o.due_date < CURRENT_DATE THEN 'overdue' ELSE 'open' END,
               NULL::varchar
          FROM legal_opinion o
         WHERE o.state NOT IN ('issued', 'closed')
           AND o.due_date IS NOT NULL
        """

    def action_open_origin(self):
        """Open the record the clock actually lives on.

        The board is a projection; the work happens at the source. One click
        lands the reader on the hearing, the period, the letter or the
        contract itself, in its own form view with its own buttons.
        """
        self.ensure_one()
        if not self.res_model or self.res_model not in self.env:
            raise UserError(
                _("The source record of this deadline is no longer installed.")
            )
        return {
            "type": "ir.actions.act_window",
            "res_model": self.res_model,
            "res_id": self.res_id,
            "view_mode": "form",
            "views": [(False, "form")],
            "target": "current",
        }
