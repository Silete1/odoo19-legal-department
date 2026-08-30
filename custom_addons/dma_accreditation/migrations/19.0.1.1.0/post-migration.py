# Part of the DMA Accreditation module. See LICENSE file for full copyright and licensing details.
"""Bring an existing accreditation database up to the document/SLA release.

Two things a data file cannot do on an upgrade:

1. The prerequisite document types were seeded with ``noupdate="1"`` - rightly,
   so an upgrade never overwrites a Directorate's own wording - which also
   means the new validity policy in ``data/dma_document_validity_data.xml``
   would never reach a database that already had them. It is applied here
   instead, and only to types nobody has touched.

2. Everything else the release adds is a stored *computed* field
   (``stage_entered_on``, the durations on the approval log, the document
   validity states), so the ORM backfills every historical file by itself
   during the upgrade. Nothing to do here for those - which is precisely why
   they were built that way.
"""
import logging

_logger = logging.getLogger(__name__)

#: xml id -> (code, has_validity, expiry_warning_days). Kept in step with
#: data/dma_document_validity_data.xml.
VALIDITY_POLICY = {
    "document_type_registration": ("registration", True, 60),
    "document_type_org_structure": ("org-structure", False, 30),
    "document_type_staff_cv": ("staff-cv", False, 30),
    "document_type_equipment": ("equipment", False, 30),
    "document_type_insurance": ("insurance", True, 30),
    "document_type_safety_policy": ("safety-policy", False, 30),
    "document_type_quality": ("quality", True, 60),
    "document_type_experience": ("experience", False, 30),
    "document_type_financial": ("financial", True, 30),
    "document_type_power_of_attorney": ("power-of-attorney", True, 30),
}


def migrate(cr, version):
    if not version:
        return
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    applied = 0
    for xmlid, (code, has_validity, warning_days) in VALIDITY_POLICY.items():
        doc_type = env.ref(
            "dma_accreditation.%s" % xmlid, raise_if_not_found=False,
        )
        if not doc_type:
            continue
        # Only ever fill in a blank. A Directorate that has already decided
        # this document does not expire keeps its decision.
        if doc_type.code:
            continue
        doc_type.write({
            "code": code,
            "has_validity": has_validity,
            "expiry_warning_days": warning_days,
        })
        applied += 1
    _logger.info(
        "DMA accreditation: validity policy applied to %s document type(s)", applied,
    )
