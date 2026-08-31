from odoo import _, api, fields, models


class LegalCorrespondence(models.Model):
    """The edge from the register to the file.

    ``legal_correspondence`` deliberately does not know that procedures exist: a
    customer may want the mail room, the register and the official letter with
    no workflow at all, and a ``Many2one('legal.case')`` declared there would
    make that module unloadable on its own. So the field is added from this side,
    which is also the side that can explain why it is nullable.

    **It is nullable because the letter arrives before the file exists.** An
    unprompted tax assessment, a summons, a circular changing a fee - each lands
    in the mail room addressed to a company with no open case for it. A design
    that demanded a parent before an entry could be written would force the clerk
    to invent a file or leave the letter in a drawer, and both of those lose
    letters.
    """

    _inherit = "legal.correspondence"

    case_id = fields.Many2one(
        "legal.case",
        string="File",
        ondelete="set null",
        index=True,
        help="The file this entry belongs to. Empty for a letter that arrived "
        "before anybody opened a file for it - which is most of the interesting "
        "post.",
    )
    case_step_id = fields.Many2one(
        "legal.procedure.step",
        string="Step",
        ondelete="set null",
        index=True,
        readonly=True,
        help="Where the file was standing when this letter was written. "
        "Snapshotted rather than read live, because the letter is evidence of "
        "what was said at that point in the walk.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        entries = super().create(vals_list)
        for entry in entries:
            if entry.case_id and not entry.case_step_id:
                entry.case_step_id = entry.case_id.step_id
            if entry.case_id:
                entry.case_id._log(
                    "contact" if entry.is_contact_note else "letter",
                    entry.display_name,
                    closes_step=False,
                )
        return entries

    def action_open_case(self):
        self.ensure_one()
        if not self.case_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "res_model": "legal.case",
            "res_id": self.case_id.id,
            "view_mode": "form",
        }


class LegalCaseCorrespondence(models.Model):
    """The other half of the edge, plus the search index it feeds.

    ``reference_index`` on the file exists so that a clerk handed a scrap of
    paper with a number on it can find the file without first knowing whether the
    number is ours, theirs, a deed or a receipt. The register numbers are the
    half of that index this module owns.
    """

    _inherit = "legal.case"

    correspondence_ids = fields.One2many(
        "legal.correspondence", "case_id", string="Letters", copy=False
    )
    correspondence_count = fields.Integer(compute="_compute_correspondence_count")
    last_letter_id = fields.Many2one(
        "legal.correspondence",
        string="Last Letter",
        compute="_compute_correspondence_count",
        help="The most recent entry on the file, which is what a desk panel shows "
        "and what a chase is written against.",
    )
    reply_overdue = fields.Boolean(
        compute="_compute_correspondence_count",
        help="Whether anything on this file is waiting on a body past its reply "
        "date. Read live rather than stored, because it changes at midnight with "
        "nobody writing to the record.",
    )

    @api.depends("correspondence_ids.reply_state", "correspondence_ids.our_date")
    def _compute_correspondence_count(self):
        for case in self:
            entries = case.correspondence_ids
            case.correspondence_count = len(entries)
            case.last_letter_id = entries.sorted(
                lambda entry: (entry.our_date or entry.their_date or fields.Date.today(), entry.id)
            )[-1:]
            case.reply_overdue = any(
                entry.reply_state == "late" for entry in entries
            )

    def _reference_index_parts(self):
        """Add the register numbers to the file's search index.

        Extending the hook rather than redefining the compute, so neither module
        has to know the other's field names and a third module can add its own
        numbers the same way.
        """
        parts = super()._reference_index_parts()
        for entry in self.correspondence_ids:
            parts.append(entry.our_number or "")
            parts.append(entry.their_number or "")
            parts.append(entry.body_reference or "")
        return parts

    def action_open_correspondence(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Letters"),
            "res_model": "legal.correspondence",
            "view_mode": "list,form",
            "domain": [("case_id", "=", self.id)],
            "context": {
                "default_case_id": self.id,
                "default_gov_body_id": self.current_body_id.id or self.body_id.id,
                "default_entity_id": self.entity_id.id,
                "default_subject": self.subject or "",
            },
        }


class LegalProcedureTypeLetter(models.Model):
    """Which letter a procedure writes.

    Added from this file rather than on the procedure type itself for the same
    reason as ``case_id``: it is the edge between the two modules, and keeping
    both halves of an edge in one file is what makes it removable.
    """

    _inherit = "legal.procedure.type"

    letter_template_id = fields.Many2one(
        "legal.letter.template",
        string="Letter Template",
        ondelete="set null",
        help="The default official letter this procedure sends. A step may override it "
        "where the walk writes to more than one body.",
    )


class LegalProcedureStepLetter(models.Model):
    _inherit = "legal.procedure.step"

    letter_template_id = fields.Many2one(
        "legal.letter.template",
        string="Letter Template",
        ondelete="set null",
        help="Overrides the procedure's template for this step, which is what a "
        "referral to a second directorate needs: the same file, a different "
        "addressee block and a different salutation.",
    )
