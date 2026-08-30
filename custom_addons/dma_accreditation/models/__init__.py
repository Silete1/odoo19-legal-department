# Part of the DMA Accreditation module. See LICENSE file for full copyright and licensing details.
from . import dma_constants
from . import dma_accreditation_scope
from . import dma_document_type
from . import dma_approval_line
from . import dma_request_document
from . import dma_fee_payment
from . import dma_accreditation_request
from . import dma_dashboard
from . import dma_role_workspace
from . import dma_accreditation_demo
from . import dma_accreditation_settings

# Document intelligence, time control and process performance. They extend the
# models above, so they are loaded after them.
from . import dma_document_policy
from . import dma_document_submission
from . import dma_request_document_evidence
from . import dma_process_log
from . import dma_sla_rule
from . import dma_sla_escalation
from . import dma_accreditation_sla
from . import dma_accreditation_dossier
from . import dma_accreditation_watch
from . import dma_process_analytics
