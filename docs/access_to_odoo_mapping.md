# Access-to-Odoo mapping

No Access database was present, so the source labels below are migration aliases to confirm when a file becomes available; they are not claimed findings.

| Access candidate | Odoo target | Native Odoo reused? | Notes |
| --- | --- | --- | --- |
| Employee / EmployeeID | `hr.employee` | Yes | Match by a confirmed stable identifier; never duplicate employees. |
| Department / DepartmentID | `hr.department` | Yes | Match normalized names/codes and company; never duplicate departments blindly. |
| DepartmentManager | `hr.department.manager_id.user_id` | Yes | Organizational configuration, not historical free text. |
| Subject | `gov.hr.deputation.subject` | No | Required business field. |
| ActivityType | `gov.hr.deputation.deputation_activity_type_id` | No | Configurable deputation lookup; named distinctly from the native `mail.activity.mixin.activity_type_id`. |
| Activity / Description | `activity_description` | No | Narrative activity. |
| Destination / Location | `destination` | No | Searchable reporting dimension. |
| DateFrom | `date_from` | No | Inclusive start. |
| DateTo | `date_to` | No | Inclusive end; validated. |
| Duration | `duration_days` | No | Stored computed inclusive days. |
| Participants | `gov.hr.deputation.participant` | No | Lines reference employees and preserve snapshots. |
| BasisType | `gov.hr.basis.type` | No | Configurable lookup. |
| BasisNumber | `gov.hr.case.basis.reference_number` | No | Structured evidence metadata. |
| BasisDate | `reference_date` | No | Structured evidence metadata. |
| BasisFile | attachment-backed `file_data` | Yes | Odoo attachment storage. |
| Status | case `state` + current step | No | Map semantically; do not copy opaque legacy codes. |
| OutgoingNo | `outgoing_number` | No | Manual; unique per company when set. |
| OutgoingDate | `outgoing_date` | No | Required at issuance. |
| MemoPDF / OrderPDF | `ir.attachment` links | Yes | Historical source PDFs may be attached and marked migrated. |

Historical import should be a one-time script outside the production addon. Unmapped legacy fields should first be assessed for legal/reporting value; necessary but low-frequency fields belong in backend notes or migration metadata, not automatically on the creation form.
