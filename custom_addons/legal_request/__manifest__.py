{
    "name": "Legal Department - Requests",
    "summary": "The intake front door: internal requests to the legal department, triaged, assigned, worked, approved and closed",
    "description": """
Legal Department - Requests (طلبات الشؤون القانونية)
=====================================================

The **front door** of the legal department. Every other module in the suite
answers a question the department has already decided to work on - a file to
walk, a letter to send, a power of attorney to check. This one is where the
work *arrives*: the finance department asking for a supply contract to be
vetted, HR asking whether a termination is safe, a branch asking for a legal
opinion before it signs.

Three decisions carry the design.

**Intake is first class, because the request exists before the answer does.**
A department does not open a ``legal.case`` - it does not know the procedure,
the counter or the fee. It writes a question. The request is that question
given a number, a clock and an owner, and the triage desk decides what it
becomes.

**Triage, work and approval are three different people, enforced on the
server.** A clerk registers what came in; an officer triages and assigns it; an
approver signs off the answer. The buttons are gated by group *and* re-checked
in the action, because a button a user cannot see is not a control - a control
is a rule the RPC layer also refuses to break.

**What a request becomes is a clean hook, not a hard-coded branch.** A vetted
contract, an issued opinion, an official letter and a litigation file are all
downstream artefacts a later integrator wires in; ``action_convert`` is the
single seam they extend, and the base spawns the one artefact that is always
available - an official letter on the correspondence register.
""",
    "version": "19.0.1.0.0",
    "category": "Services/Legal",
    "license": "LGPL-3",
    "author": "Legal Department",
    "depends": ["legal_correspondence"],
    "data": [
        "security/ir.model.access.csv",
        "security/legal_request_rules.xml",
        "data/legal_request_sequence.xml",
        "data/legal_request_category_data.xml",
        "views/legal_request_category_views.xml",
        "views/legal_request_views.xml",
        "wizard/legal_request_cancel_views.xml",
        "wizard/legal_request_return_views.xml",
        "wizard/legal_request_approve_views.xml",
        "views/legal_request_menus.xml",
    ],
    "installable": True,
    "application": True,
    "auto_install": False,
}
