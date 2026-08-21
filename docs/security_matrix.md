# Security matrix

| Action | User | Dept Manager | Admin Officer | Admin Manager | DG | Gov HR Manager |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Create draft | Yes | With request-user role | Yes | Yes | No | Yes |
| Edit own draft/returned correction | Yes | Organizational | Assigned | Yes | No | Controlled |
| Department approve | No | Yes | No | No | No | No |
| Verify documents | No | No | Yes | No | No | No |
| Administrative Manager approve | No | No | No | Yes | No | No |
| Director General approve | No | No | No | No | Yes | No |
| Enter outgoing number/date | No | No | Yes | No | No | No |
| Issue final order | No | No | Yes | No | No | No |
| Configure route/stamp | No | No | No | No | No | Yes |
| Reporting | limited | department | operational | all company | all company | all company |

The Government HR Manager has technical visibility and configuration authority but does not impersonate a business approval. Approval methods require the user resolved for the active step even when the caller has broad CRUD access.

All case, deputation, basis, participant, and log rules include allowed companies. Group rules are deliberately additive: a user's union of legitimate roles expands read visibility, while public methods still enforce the exact active actor. Submitted records are locked in Python because ACL write permission alone cannot express state and field-level workflow rules.

Administrative Officer and Administrative Manager groups imply the basic request-user group so those operational users can create a draft when policy permits. Concerned-department management is resolved from `hr.department.manager_id`; it is not a global approval group and does not by itself grant draft creation.
