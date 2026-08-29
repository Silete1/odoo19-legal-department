# Part of the DMA Accreditation module. See LICENSE file for full copyright and licensing details.
"""Shared selections and role/state mappings for the accreditation workflow.

Keeping them in one place guarantees that the request, the approval log and the
security guards always talk about the very same steps.
"""

# ---------------------------------------------------------------------------
# Workflow states - the ordering below is also the order of the status bar.
# ---------------------------------------------------------------------------
STATE_SELECTION = [
    ("draft", "Draft"),
    ("submitted", "Submitted"),
    ("gd_review", "General Director Initial Acceptance"),
    ("legal_review", "Legal Department Review"),
    ("cert_check", "Certifications Division Check"),
    ("office_granted", "Office Accreditation Granted"),
    ("sop_submission", "SOP Submission"),
    ("sop_fee", "SOP Reading Fee"),
    ("dual_confirm", "Dual Confirmation"),
    ("demo_fee", "Operational Demonstration Fee"),
    ("committee", "Accreditation Committee"),
    ("legal_refine", "Legal Refinement"),
    ("authorized", "Operational Accreditation Granted"),
    ("returned", "Returned to Applicant"),
    ("rejected", "Rejected"),
]

#: The linear path shown in the status bar (the two exception states are hidden
#: until the record actually reaches them).
MAIN_PATH_STATES = [
    "draft", "submitted", "gd_review", "legal_review", "cert_check",
    "office_granted", "sop_submission", "sop_fee", "dual_confirm",
    "demo_fee", "committee", "legal_refine", "authorized",
]

#: States a request can be returned or rejected from.
REVIEWABLE_STATES = [
    "submitted", "gd_review", "legal_review", "cert_check", "office_granted",
    "sop_submission", "sop_fee", "dual_confirm", "demo_fee", "committee",
    "legal_refine",
]

# ---------------------------------------------------------------------------
# Roles - one entry per security group of the module.
# ---------------------------------------------------------------------------
ROLE_SELECTION = [
    ("reception", "Reception Officer"),
    ("general_director", "General Director"),
    ("legal_director", "Legal Department Director"),
    ("cert_officer", "Certifications Division Officer"),
    ("operations", "Operations Department"),
    ("finance", "Finance Department"),
    ("committee", "Accreditation Committee"),
    ("manager", "Accreditation Manager"),
]

#: role key -> fully qualified security group used by the server side guards.
ROLE_GROUP = {
    "reception": "dma_accreditation.group_dma_reception",
    "general_director": "dma_accreditation.group_dma_general_director",
    "legal_director": "dma_accreditation.group_dma_legal_director",
    "cert_officer": "dma_accreditation.group_dma_cert_officer",
    "operations": "dma_accreditation.group_dma_operations",
    "finance": "dma_accreditation.group_dma_finance",
    "committee": "dma_accreditation.group_dma_committee",
    "manager": "dma_accreditation.group_dma_manager",
}

#: state -> role expected to act on it. Used by ``pending_group`` and to decide
#: which users get the "next step" activity.
STATE_PENDING_ROLE = {
    "draft": "reception",
    "submitted": "reception",
    "gd_review": "general_director",
    "legal_review": "legal_director",
    "cert_check": "cert_officer",
    "office_granted": "operations",
    "sop_submission": "operations",
    "sop_fee": "finance",
    "dual_confirm": "finance",
    "demo_fee": "finance",
    "committee": "committee",
    "legal_refine": "legal_director",
    "authorized": False,
    "returned": "reception",
    "rejected": False,
}

#: role -> states that show up in that role's "My Queue" / "My Turn" filter.
ROLE_QUEUE_STATES = {
    "reception": ["draft", "submitted", "returned"],
    "general_director": ["gd_review", "cert_check"],
    "legal_director": ["legal_review", "legal_refine"],
    "cert_officer": ["cert_check"],
    "operations": ["office_granted", "sop_submission", "dual_confirm"],
    "finance": ["sop_fee", "dual_confirm", "demo_fee"],
    "committee": ["committee"],
    "manager": MAIN_PATH_STATES + ["returned"],
}


def state_label(env, state):
    """Return the *translated* label of ``state`` for the current user language."""
    field = env["dma.accreditation.request"]._fields["state"]
    return dict(field._description_selection(env)).get(state, state)


def role_label(env, role):
    """Return the *translated* label of ``role`` for the current user language."""
    field = env["dma.approval.line"]._fields["role"]
    return dict(field._description_selection(env)).get(role, role)
