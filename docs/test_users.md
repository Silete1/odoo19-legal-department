# Government HR test users

These accounts exist only in the local `gov_hr_release_test` database. They are created by `scripts/setup_gov_hr_test_users.py` and are not loaded automatically by either addon.

URL after starting Odoo: `http://127.0.0.1:8079`

Common password: `GovHR-Test-2026!`

| Login | Role | Test action |
| --- | --- | --- |
| `test.requester@gov-hr.test` | Request User | Create and edit a draft, add employees and supporting documents, then submit it. |
| `test.department.manager` | Concerned Department Manager | Approve the first organizational step. |
| `test.director.general` | Director General | Approve the memorandum and later the final mission order. |
| `test.admin.manager` | Administrative Department Manager | Approve both administrative-manager steps and reassign the officer if needed. |
| `test.admin.officer` | Administrative Officer | Verify documents, prepare the mission order, then enter the outgoing number/date and issue it. |
| `test.gov.hr.manager` | Configuration Manager | Inspect routes, basis types, sequence, company settings, and reports. This account does not impersonate business approvals. |

## Suggested test sequence

1. Sign in as `test.requester@gov-hr.test`, open **My Deputations**, create a new deputation, complete its participants and supporting documents, then submit it.
2. Sign out and approve successively as the department manager, Director General, and administrative manager.
3. Sign in as the administrative officer, mark the supporting document verified, confirm verification, and prepare the mission order.
4. Approve as the administrative manager and then as the Director General.
5. Return to the administrative officer, enter a unique outgoing number and date, and issue the order.
6. Open the archived official copy and confirm the red `TEST GOV HR` stamp. Never use this test stamp in production.

Reset or remove all test accounts before cloning this database into another environment.
