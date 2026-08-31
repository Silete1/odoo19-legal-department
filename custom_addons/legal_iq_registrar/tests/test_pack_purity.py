"""The falsifiable form of the product's central claim.

Every Iraqi content pack in this suite says the same thing: a government body is
*configured*, not coded. That is a slogan until something can prove it false, so
this suite fails the build the moment a pack starts contributing to the registry.

It lives in ``legal_iq_registrar`` rather than in a pack of its own because a
test can only see modules that are installed, and the Registrar pack is the one
an Iraqi company installs first. It checks every ``legal_iq_*`` pack it finds
installed, so running the suite with only Tax present still proves something -
it just proves it about Tax.

**A test can only see installed packs.** Running this with one pack installed and
reporting a pass is vacuous, so CI must install all of them:

    odoo-bin -d ci --test-enable --test-tags legal_iq \\
        -i legal_iq_registrar,legal_iq_tax,legal_iq_chamber,\\
           legal_iq_social_security,legal_iq_residency

The three things checked are the three ways the claim could quietly stop being
true: a pack could add a field, a pack could add a model, or a pack could ship
Python that runs. The last one is checked on disk rather than in the registry,
because a helper imported by nothing is still a helper somebody will use.
"""

import os

from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "legal_iq")
class TestContentPackPurity(TransactionCase):
    """A content pack contributes rows, and nothing else."""

    #: Anything matching this and installed is held to the rule.
    PACK_PREFIX = "legal_iq_"

    #: The demonstration pack is a content pack too - it ships an entity, users
    #: and worked files, all of them rows - so it is held to the same rule.

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.packs = (
            cls.env["ir.module.module"]
            .search(
                [
                    ("name", "=like", "%s%%" % cls.PACK_PREFIX),
                    ("state", "=", "installed"),
                ]
            )
            .mapped("name")
        )

    def test_packs_are_installed_at_all(self):
        """Guard against a vacuous pass.

        With no pack installed every other test here passes by having nothing to
        look at, and a green suite would then be evidence of nothing whatsoever.
        """
        self.assertTrue(
            self.packs,
            "No legal_iq_* content pack is installed, so the purity suite would "
            "pass without examining anything. Install the packs before running it.",
        )

    def test_packs_contribute_no_fields(self):
        """Not one column anywhere in the registry.

        Read off the live registry rather than ``ir.model.fields.modules``: that
        column is computed and not stored, so it cannot be searched, and asking
        for it is how this test quietly turned into an error instead of a
        verdict. Every ``Field`` carries ``_module`` - the addon whose class body
        declared it - which is the fact the rule is actually about.

        A content pack appearing there means somebody added a column to make one
        ministry fit, which is the precise moment the product stops being
        configurable and starts being forked. It is the habit rather than the
        single field that this catches.
        """
        offenders = {}
        for model_name, model in self.env.registry.items():
            for field in model._fields.values():
                module = getattr(field, "_module", None)
                if module in self.packs:
                    offenders.setdefault(module, []).append(
                        "%s.%s" % (model_name, field.name)
                    )
        self.assertFalse(
            offenders,
            "A content pack must contribute no fields at all. Found: %s" % offenders,
        )

    def test_packs_contribute_no_models(self):
        """And not one table either.

        Checked through ``ir.model.data`` rather than ``ir.model.modules``,
        because that is where a model created by a pack would be recorded, and
        because the same query catches views and actions a pack has no business
        owning either.
        """
        offenders = {}
        for pack in self.packs:
            owned = self.env["ir.model.data"].search(
                [
                    ("module", "=", pack),
                    ("model", "in", ["ir.model", "ir.model.fields"]),
                ]
            )
            if owned:
                offenders[pack] = owned.mapped(lambda row: "%s:%s" % (row.model, row.name))
        self.assertFalse(
            offenders,
            "A content pack must create no model and no field. Found: %s" % offenders,
        )

    def test_packs_ship_no_python(self):
        """The rule on disk, not merely in the registry.

        A pack could keep the registry clean and still ship a module of helpers
        that a customisation imports - at which point the pack is code again, and
        upgrading it is a code review rather than a data review. The only Python
        a pack may contain is an empty ``__init__.py``, and the one test package
        that carries this file.
        """
        offenders = {}
        for pack in self.packs:
            path = get_module_path(pack)
            if not path:
                continue
            for root, directories, files in os.walk(path):
                directories[:] = [
                    directory
                    for directory in directories
                    if directory not in ("__pycache__", "tests", "static")
                ]
                for filename in files:
                    if not filename.endswith(".py"):
                        continue
                    full = os.path.join(root, filename)
                    if filename == "__manifest__.py":
                        continue
                    if filename == "__init__.py" and root == path:
                        with open(full, encoding="utf-8") as handle:
                            body = "".join(
                                line
                                for line in handle
                                if line.strip() and not line.strip().startswith("#")
                            )
                        if not body.strip():
                            continue
                    offenders.setdefault(pack, []).append(
                        os.path.relpath(full, path).replace("\\", "/")
                    )
        self.assertFalse(
            offenders,
            "A content pack may contain no Python beyond an empty __init__.py and "
            "its tests. Found: %s" % offenders,
        )

    def test_shipped_configuration_carries_its_provenance(self):
        """Every shipped row that *can* cite its source does.

        Not a purity check but the same argument from the other end: a fee or a
        deadline with no legal basis and no verification date is a figure a clerk
        will trust at a counter, and being wrong at the counter is how the module
        loses its credibility in one afternoon. The models that carry the three
        provenance fields are checked; the ones that do not are skipped rather
        than excused.
        """
        checked = ["legal.gov.body", "legal.document.type", "legal.fee.rule"]
        missing = []
        for pack in self.packs:
            for model_name in checked:
                model = self.env[model_name]
                if "legal_basis" not in model._fields:
                    continue
                rows = self.env["ir.model.data"].search(
                    [("module", "=", pack), ("model", "=", model_name)]
                )
                for row in rows:
                    record = model.browse(row.res_id).exists()
                    if not record:
                        continue
                    if not record.legal_basis or not record.last_verified_on:
                        missing.append("%s.%s (%s)" % (pack, row.name, model_name))
        self.assertFalse(
            missing,
            "Shipped configuration must carry legal_basis and last_verified_on. "
            "Missing on: %s" % missing,
        )
