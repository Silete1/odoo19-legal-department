from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models

#: The notice ladder every expiring artefact in the department is measured
#: against. A single "expires soon" flag is useless: a residency permit needs
#: chasing months ahead because the procedure that renews it is itself long,
#: while a tax no-objection letter is produced in a day. The ladder is a
#: default; a document type may override it, and a procedure type may say how
#: long its own renewal takes so the board can work backwards from the deadline
#: rather than forwards from today.
NOTICE_LADDER = (180, 90, 60, 30, 14, 7, 0)


class LegalExpiryMixin(models.AbstractModel):
    """Everything a legal department chases is a dated artefact that expires.

    Licences, identities, permits, powers of attorney, guarantees, passports and
    residencies all answer the same four questions - when does it lapse, how
    long have we got, is that inside the notice window, and when must we *start*
    the renewal to be safe - so the arithmetic is written once here and
    inherited, rather than re-implemented per model with slightly different
    off-by-one behaviour.

    Two rules are load bearing and are the reason this is a mixin rather than a
    handful of copied computes:

    * ``expiry_state`` is stored and indexed so a board can be grouped and
      searched on it, but :meth:`_is_expired` reads the clock live. A stored
      value derived from "today" is a day stale by tomorrow, and a gate that
      lets an expired document through for a few hours because a cron has not
      run yet is worse than no gate at all.

    * ``start_by_date`` - not ``expiry_date`` - is what an urgency board buckets
      on. "Expires in sixty days" is decoration; "you had to start this last
      Tuesday" is actionable, and the two differ by however long the renewal
      procedure actually takes at that body.
    """

    _name = "legal.expiry.mixin"
    _description = "Expiring Artefact Mixin"

    expiry_date = fields.Date(
        string="Expiry Date",
        index=True,
        tracking=True,
        help="The date the artefact ceases to be in force. Empty means it does not expire. "
        "Tracked: quietly moving an expiry date is how a lapsed licence hides.",
    )
    #: Days before expiry at which this artefact starts being chased. Defaults
    #: from the type where the inheriting model provides one.
    notice_days = fields.Integer(
        string="Notice Period (days)",
        default=30,
        help="How long before expiry this begins to appear on the renewal board.",
    )
    #: How long the renewal procedure itself takes at that body, in working
    #: days. Set from the procedure type when one is linked.
    renewal_lead_days = fields.Integer(
        string="Renewal Lead Time (days)",
        default=0,
        help="How long the renewal takes at the body, so the board can say when to start rather than when it ends.",
    )
    start_by_date = fields.Date(
        string="Start Renewal By",
        compute="_compute_expiry_state",
        store=True,
        index=True,
        help="Expiry minus the renewal lead time - the date the renewal must begin to be safe.",
    )
    days_to_expiry = fields.Integer(
        string="Days Remaining",
        compute="_compute_days_to_expiry",
        search="_search_days_to_expiry",
        help="Recomputed on read, never stored, because it changes every midnight.",
    )
    expiry_state = fields.Selection(
        [
            ("no_expiry", "Does Not Expire"),
            ("valid", "Valid"),
            ("due_soon", "Renewal Due"),
            ("expiring", "Expiring"),
            ("expired", "Expired"),
        ],
        string="Validity",
        compute="_compute_expiry_state",
        store=True,
        index=True,
        default="no_expiry",
    )

    @api.depends("expiry_date", "notice_days", "renewal_lead_days")
    def _compute_expiry_state(self):
        """Bucket the artefact, and work out when its renewal has to start.

        ``due_soon`` fires on the *start by* date and ``expiring`` on the notice
        window, so a document with a long renewal procedure starts shouting
        earlier than a document with a short one even though both expire on the
        same day. That distinction is the whole point of holding a lead time.
        """
        today = fields.Date.context_today(self)
        for record in self:
            if not record.expiry_date:
                record.expiry_state = "no_expiry"
                record.start_by_date = False
                continue
            lead = max(record.renewal_lead_days or 0, 0)
            record.start_by_date = record.expiry_date - relativedelta(days=lead)
            remaining = (record.expiry_date - today).days
            if remaining < 0:
                record.expiry_state = "expired"
            elif remaining <= (record.notice_days or 0):
                record.expiry_state = "expiring"
            elif record.start_by_date <= today:
                record.expiry_state = "due_soon"
            else:
                record.expiry_state = "valid"

    def _compute_days_to_expiry(self):
        today = fields.Date.context_today(self)
        for record in self:
            record.days_to_expiry = (record.expiry_date - today).days if record.expiry_date else 0

    def _search_days_to_expiry(self, operator, value):
        """Let a filter say "expiring within 30 days" without a stored column.

        Translating the day count into a date bound keeps the search on the
        indexed ``expiry_date`` column, and inverts the operator because a
        *smaller* number of days remaining is an *earlier* date.
        """
        if not isinstance(value, int):
            raise ValueError(_("Days remaining can only be compared with a whole number of days."))
        bound = fields.Date.context_today(self) + relativedelta(days=value)
        inverted = {"<": "<", "<=": "<=", ">": ">", ">=": ">=", "=": "=", "!=": "!="}.get(operator)
        if not inverted:
            raise ValueError(_("Unsupported comparison on days remaining."))
        return [("expiry_date", inverted, bound)]

    def _is_expired(self, on_date=None):
        """The authoritative gate. Reads the clock, never the stored column.

        Every hard block in the product - you may not file on a lapsed power of
        attorney, you may not submit a tender with an expired Chamber identity -
        goes through here, and every one of them may be asked about a *future*
        date, because an Iraqi tender demands documents that are نافذ الصلاحية
        عند تاريخ الغلق: valid as at the closing date, not valid today.
        """
        self.ensure_one()
        if not self.expiry_date:
            return False
        return self.expiry_date < (on_date or fields.Date.context_today(self))

    def _is_valid_on(self, on_date):
        """Was / will this artefact be in force on a given date? Used by the
        tender readiness matrix, which is the reason the whole mixin exists in
        this shape."""
        self.ensure_one()
        return not self._is_expired(on_date)
