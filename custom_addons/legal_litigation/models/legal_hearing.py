from odoo import _, api, fields, models
from odoo.exceptions import UserError


class LegalHearing(models.Model):
    """جلسة المرافعة - one sitting in a case, and the hinge that sets the next.

    An Iraqi case is a chain of hearings, and the court almost never closes a
    sitting without fixing the date of the one after it. So the interesting field
    on a hearing is not what happened at it but ``next_hearing_date``: setting it
    rolls the following ``legal.hearing`` forward and puts the date on the
    advocate's activity list. That roll-forward is done **once** - a
    ``next_hearing_id`` link records the child it created, so minuting the same
    sitting twice, or a second save, never breeds a duplicate.
    """

    _name = "legal.hearing"
    _description = "Court Hearing"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"

    lawsuit_id = fields.Many2one(
        "legal.lawsuit",
        string="Lawsuit",
        required=True,
        ondelete="cascade",
        index=True,
    )
    lawyer_id = fields.Many2one(
        "res.users",
        string="Advocate",
        related="lawsuit_id.lawyer_id",
        store=True,
        index=True,
    )
    company_id = fields.Many2one(
        "res.company", related="lawsuit_id.company_id", store=True, index=True
    )
    date = fields.Datetime(
        string="Sitting Date",
        required=True,
        index=True,
        tracking=True,
        help="When the court sits. What the calendar and the activity are keyed on.",
    )
    court_id = fields.Many2one(
        "legal.court",
        string="Court",
        ondelete="restrict",
        index=True,
        help="The court sitting. Defaults to the case's court; set it when a "
        "sitting is held elsewhere - a referral to an expert, say.",
    )
    location = fields.Char(
        translate=True,
        help="The chamber or hall, where it matters: القاعة رقم ٣ / الطابق الثاني.",
    )
    purpose = fields.Selection(
        [
            ("pleading", "Pleading (مرافعة)"),
            ("witnesses", "Hearing Witnesses (استماع شهود)"),
            ("expert", "Expert Report (خبرة)"),
            ("verdict", "Pronouncement Of Judgment (نطق بالحكم)"),
            ("postponed", "Postponed (تأجيل)"),
        ],
        default="pleading",
        required=True,
        index=True,
        tracking=True,
        help="Why the court is sitting. Drives what the advocate must prepare.",
    )
    required_preparation = fields.Text(
        string="Required Preparation",
        translate=True,
        help="What has to be ready for this sitting - a memo, a witness, a fee "
        "paid, an original produced.",
    )
    attendance = fields.Selection(
        [
            ("we_attended", "We Attended (حضرنا)"),
            ("opponent_absent", "Opponent Absent (غياب الخصم)"),
            ("we_absent", "We Were Absent (تغيبنا)"),
            ("both_absent", "Both Absent (غياب الطرفين)"),
        ],
        help="Who was there. Absence is not a footnote in Iraqi procedure - it "
        "decides whether a judgment is in absentia and which challenge it invites.",
    )
    minutes = fields.Text(
        string="Minutes / Notes",
        translate=True,
        help="What was said and done, in our own note - not the court's record.",
    )
    result = fields.Text(
        string="Result",
        translate=True,
        tracking=True,
        help="What the sitting produced. Once this is recorded the sitting counts "
        "as held, and the case's “next hearing” rolls to the sitting after it.",
    )
    next_step = fields.Text(
        string="Next Step",
        translate=True,
        help="What has to happen before the next sitting.",
    )
    next_hearing_date = fields.Datetime(
        string="Next Hearing Set For",
        index=True,
        tracking=True,
        help="The date the court fixed for the next sitting. Recording it opens "
        "that sitting as its own row and puts it on the advocate's activity list.",
    )
    next_hearing_id = fields.Many2one(
        "legal.hearing",
        string="Next Sitting",
        readonly=True,
        copy=False,
        help="The follow-up sitting this one bred, if any. Its existence is what "
        "stops the roll-forward happening twice.",
    )
    is_held = fields.Boolean(
        compute="_compute_is_held", store=True, string="Held"
    )
    active = fields.Boolean(default=True)

    @api.depends("result")
    def _compute_is_held(self):
        for hearing in self:
            hearing.is_held = bool(hearing.result)

    @api.model_create_multi
    def create(self, vals_list):
        hearings = super().create(vals_list)
        for hearing in hearings:
            if not hearing.court_id and hearing.lawsuit_id.court_id:
                hearing.court_id = hearing.lawsuit_id.court_id
            hearing._roll_forward()
        return hearings

    def write(self, vals):
        result = super().write(vals)
        if "next_hearing_date" in vals:
            self._roll_forward()
        return result

    def action_schedule_next(self):
        """Open the next sitting explicitly - the manual twin of the roll-forward.

        Idempotent for the same reason: it defers to ``_roll_forward``, which
        does nothing if the child already exists.
        """
        for hearing in self:
            if not hearing.next_hearing_date:
                raise UserError(
                    _(
                        "Set the date the court fixed before opening the next "
                        "sitting."
                    )
                )
            hearing._roll_forward()
        return True

    def _roll_forward(self):
        """Create the next sitting and put it on the advocate's list - once.

        The whole method is guarded by ``next_hearing_id``: if this sitting has
        already bred its follow-up, nothing happens, so it is safe to call from
        create, from write, and from the button without ever producing a
        duplicate row or a duplicate activity.
        """
        for hearing in self:
            if not hearing.next_hearing_date or hearing.next_hearing_id:
                continue
            child = self.create(
                {
                    "lawsuit_id": hearing.lawsuit_id.id,
                    "court_id": hearing.court_id.id or hearing.lawsuit_id.court_id.id,
                    "date": hearing.next_hearing_date,
                    "purpose": "pleading",
                    "required_preparation": hearing.next_step or "",
                }
            )
            hearing.next_hearing_id = child
            hearing._schedule_activity(child)

    def _schedule_activity(self, child):
        """Put the next sitting on the advocate's activity list.

        Scheduled on the case, not the hearing, because the case is where the
        advocate looks and where the activity has to be answered. The deadline is
        the sitting date; the summary names it so it reads without opening
        anything.
        """
        self.ensure_one()
        lawyer = self.lawsuit_id.lawyer_id
        if not lawyer:
            return
        self.lawsuit_id.activity_schedule(
            "mail.mail_activity_data_todo",
            date_deadline=fields.Date.to_date(child.date),
            summary=_(
                "Hearing on %(date)s - %(case)s",
                date=fields.Date.to_string(fields.Date.to_date(child.date)),
                case=self.lawsuit_id.reference,
            ),
            note=self.next_step or _("Next sitting of the case."),
            user_id=lawyer.id,
        )

    @api.depends("date", "lawsuit_id.reference", "purpose")
    def _compute_display_name(self):
        # A calendar event title is read by a human: the date renders in the
        # reader's language and timezone, never as a raw ISO timestamp.
        from odoo.tools.misc import format_datetime

        for hearing in self:
            when = (
                format_datetime(self.env, hearing.date, dt_format="short")
                if hearing.date
                else _("unscheduled")
            )
            hearing.display_name = "%s - %s" % (
                hearing.lawsuit_id.reference or _("Hearing"),
                when,
            )
