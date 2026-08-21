"""Idempotent Odoo shell setup for the local Government HR test database.

Run only on a disposable test database with::

    odoo-bin shell -d DATABASE --shell-file scripts/setup_gov_hr_test_users.py
"""

import base64
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

from odoo import Command, fields


TEST_PASSWORD = "GovHR-Test-2026!"
COMPANY = env.ref("base.main_company").sudo()
BASE_USER = env.ref("base.group_user")
ARABIC_LANGUAGE = (
    env["res.lang"]
    .sudo()
    .with_context(active_test=False)
    .search([("code", "=", "ar_001")], limit=1)
)
if ARABIC_LANGUAGE and not ARABIC_LANGUAGE.active:
    env["base.language.install"].sudo().create(
        {"lang_ids": [Command.set([ARABIC_LANGUAGE.id])], "overwrite": True}
    ).lang_install()


def ensure_user(login, name, group_xmlid=None, legacy_logins=()):
    user = (
        env["res.users"]
        .sudo()
        .search([("login", "in", [login, *legacy_logins])], limit=1)
    )
    groups = [BASE_USER.id]
    if group_xmlid:
        groups.append(env.ref(group_xmlid).id)
    values = {
        "name": name,
        "login": login,
        "email": login if "@" in login else f"{login}@gov-hr.test",
        "password": TEST_PASSWORD,
        "active": True,
        "share": False,
        "company_id": COMPANY.id,
        "company_ids": [Command.set([COMPANY.id])],
        "group_ids": [Command.set(groups)],
        "tz": "Asia/Baghdad",
    }
    if ARABIC_LANGUAGE:
        values["lang"] = ARABIC_LANGUAGE.code
    if user:
        user.write(values)
    else:
        user = env["res.users"].sudo().with_context(no_reset_password=True).create(values)
    return user


def ensure_employee(user, name, job_title):
    employee = user.employee_ids.filtered(lambda item: item.company_id == COMPANY)[:1]
    values = {
        "name": name,
        "user_id": user.id,
        "company_id": COMPANY.id,
        "job_title": job_title,
    }
    if employee:
        employee.sudo().write(values)
    else:
        employee = env["hr.employee"].sudo().create(values)
    return employee


def build_test_stamp():
    image = Image.new("RGBA", (240, 240), (255, 255, 255, 0))
    draw = ImageDraw.Draw(image)
    red = (165, 30, 35, 255)
    draw.ellipse((10, 10, 230, 230), outline=red, width=10)
    draw.ellipse((28, 28, 212, 212), outline=red, width=3)
    try:
        font = ImageFont.truetype("arial.ttf", 32)
    except OSError:
        font = ImageFont.load_default()
    draw.text((120, 88), "TEST", fill=red, font=font, anchor="mm")
    draw.text((120, 138), "GOV HR", fill=red, font=font, anchor="mm")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue())


requester_user = ensure_user(
    "test.requester@gov-hr.test",
    "مقدم طلب الإيفاد",
    "gov_hr_base.group_gov_hr_user",
    legacy_logins=("test.requester",),
)
department_manager_user = ensure_user(
    "test.department.manager", "مدير القسم المعني"
)
administrative_officer_user = ensure_user(
    "test.admin.officer", "الموظف الإداري", "gov_hr_base.group_gov_hr_admin_officer"
)
administrative_manager_user = ensure_user(
    "test.admin.manager", "مدير القسم الإداري", "gov_hr_base.group_gov_hr_admin_manager"
)
director_general_user = ensure_user(
    "test.director.general", "المدير العام", "gov_hr_base.group_gov_hr_director_general"
)
configuration_manager_user = ensure_user(
    "test.gov.hr.manager", "مدير النظام الإداري", "gov_hr_base.group_gov_hr_manager"
)

requester_employee = ensure_employee(requester_user, "أحمد محمد", "مهندس نظم")
department_manager_employee = ensure_employee(
    department_manager_user, "علي حسن", "مدير قسم المعلومات"
)
administrative_officer_employee = ensure_employee(
    administrative_officer_user, "سارة كريم", "موظف إداري"
)
administrative_manager_employee = ensure_employee(
    administrative_manager_user, "حسين جاسم", "مدير القسم الإداري"
)
director_general_employee = ensure_employee(
    director_general_user, "محمد عبد الله", "المدير العام"
)
configuration_manager_employee = ensure_employee(
    configuration_manager_user, "نور عباس", "مدير النظام الإداري"
)

information_department = env["hr.department"].sudo().search(
    [("company_id", "=", COMPANY.id), ("manager_id", "=", department_manager_employee.id)],
    limit=1,
)
if information_department:
    information_department.write({"name": "قسم المعلومات"})
else:
    information_department = env["hr.department"].sudo().create(
        {
            "name": "قسم المعلومات",
            "company_id": COMPANY.id,
            "manager_id": department_manager_employee.id,
        }
    )

administrative_department = env["hr.department"].sudo().search(
    [("company_id", "=", COMPANY.id), ("manager_id", "=", administrative_manager_employee.id)],
    limit=1,
)
if administrative_department:
    administrative_department.write({"name": "قسم الشؤون الإدارية"})
else:
    administrative_department = env["hr.department"].sudo().create(
        {
            "name": "قسم الشؤون الإدارية",
            "company_id": COMPANY.id,
            "manager_id": administrative_manager_employee.id,
        }
    )

(requester_employee | department_manager_employee).write(
    {"department_id": information_department.id}
)
(
    administrative_officer_employee
    | administrative_manager_employee
    | configuration_manager_employee
).write({"department_id": administrative_department.id})

COMPANY.write(
    {
        "name": "الجهة الحكومية التجريبية",
        "gov_hr_administrative_department_id": administrative_department.id,
        "gov_hr_director_general_user_id": director_general_user.id,
        "gov_hr_default_administrative_officer_id": administrative_officer_employee.id,
        "gov_hr_official_stamp": build_test_stamp(),
        "gov_hr_official_stamp_filename": "TEST-ONLY-stamp.png",
    }
)

sample = env["gov.hr.deputation"].sudo().search(
    [
        ("company_id", "=", COMPANY.id),
        ("requester_user_id", "=", requester_user.id),
        ("subject", "=", "طلب إيفاد تجريبي"),
        ("state", "=", "draft"),
    ],
    limit=1,
)
if not sample:
    sample = env["gov.hr.deputation"].with_user(requester_user).create(
        {
            "subject": "طلب إيفاد تجريبي",
            "requester_employee_id": requester_employee.id,
            "department_id": information_department.id,
            "company_id": COMPANY.id,
            "deputation_activity_type_id": env.ref(
                "gov_hr_deputation.activity_type_official_mission"
            ).id,
            "activity_description": "مراجعة منظومة المعلومات الحكومية",
            "destination": "البصرة",
            "date_from": fields.Date.today(),
            "date_to": fields.Date.add(fields.Date.today(), days=3),
            "participant_ids": [
                Command.create(
                    {
                        "employee_public_id": requester_employee.id,
                        "employee_id": requester_employee.id,
                        "role_note": "عضو فريق",
                    }
                )
            ],
            "basis_line_ids": [
                Command.create(
                    {
                        "type_id": env.ref(
                            "gov_hr_deputation.basis_type_work_order"
                        ).id,
                        "reference_number": "TEST-125",
                        "reference_date": fields.Date.today(),
                        "required": True,
                        "file_data": base64.b64encode(
                            "مستند اختبار فقط".encode("utf-8")
                        ),
                        "filename": "test-work-order.txt",
                    }
                )
            ],
        }
    )

env.cr.commit()

print("Government HR test users are ready.")
print("Database: gov_hr_release_test")
print(f"Common password: {TEST_PASSWORD}")
for user in (
    requester_user,
    department_manager_user,
    administrative_officer_user,
    administrative_manager_user,
    director_general_user,
    configuration_manager_user,
):
    print(f"- {user.login}")
print(f"Sample draft reference: {sample.name}")
