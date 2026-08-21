# Access schema analysis

## Scan result

A recursive read-only scan of `C:\Users\Lenovo\Documents\odoo19` on 2026-08-20 found no `.accdb` or `.mdb` file. Consequently there are no source table names, columns, keys, relationships, lookup values, status values, or sample rows to report. No Access driver or production dependency was added.

## Re-run procedure

If a database is later placed in the workspace, inspect it read-only in this order:

1. ACE ODBC metadata through `pyodbc` when an Access driver exists.
2. `mdb-schema` / `mdb-tables` / `mdb-export` when `mdbtools` exists.
3. Export schema and representative, non-sensitive lookup samples only.

Do not update the file. Reconcile people and departments to native Odoo records instead of importing duplicate masters. Production deployment never needs an Access driver.

## Business fields covered without an Access source

The implemented schema covers the explicit brief: subject, requester, concerned department/company, activity type/description, destination, dates/duration, participant snapshots, structured basis documents and verification, assignment, workflow state/step/round, outgoing registration, timestamps, approval history, and archived memorandum/final mission order.
