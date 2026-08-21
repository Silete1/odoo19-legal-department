# Government HR Deputations — UI direction

The interface is a purpose-built administrative workflow inside the standard Odoo 19 web client. It uses restrained Odoo/Bootstrap styling, responsive form groups, native relational and attachment fields, native buttons and dialogs, and a single readonly Owl field widget for workflow comprehension.

## Hierarchy

1. The form header presents the case reference, human state, and the actions the current actor may perform.
2. A concise “What do I need to do?” panel explains the active task without exposing route IDs or technical state codes.
3. Business facts are grouped into deputation information, participants, and structured supporting documents.
4. Official-document actions are grouped separately from editable data.
5. The compact workflow widget shows current/completed/returned steps and decision metadata; full immutable logs remain available in a readonly tab and the chatter retains narrative audit messages.

## Interaction rules

- Native Odoo fields handle employee search, dates, files, and outgoing data.
- Return uses a native modal wizard with a mandatory reason.
- All buttons call protected Python methods; Owl is presentation-only.
- The final stamp never appears as an editable operational field and never appears on draft output.
- Dense configuration is separated from the operational deputation form and restricted to Government HR Managers.

## Responsive and RTL behavior

The layout relies on Odoo's responsive grid and avoids fixed page widths. The workflow widget switches from a horizontal row to a stacked presentation on narrower screens, uses text and icons together rather than color alone, and inherits the active text direction. Report templates set RTL explicitly and use local system font fallbacks without external assets.
