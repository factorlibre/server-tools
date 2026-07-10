# Copyright 2015-2017 Camptocamp SA
# Copyright 2020 Onestein (<https://www.onestein.eu>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.tests.common import TransactionCase

from odoo.addons.module_change_auto_install.patch import (
    _get_modules_dict_auto_install_config,
)

# from ..models.base import disable_changeset


class TestModule(TransactionCase):

    _EXPECTED_RESULTS = {
        "web_responsive": {"web_responsive": True},
        "sale, purchase,": {"sale": True, "purchase": True},
        "web_responsive:web,base_technical_features:,"
        "point_of_sale:sale/purchase,account_usability": {
            "web_responsive": ["web"],
            "base_technical_features": [],
            "point_of_sale": ["sale", "purchase"],
            "account_usability": True,
        },
    }

    def test_config_parsing(self):
        for k, v in self._EXPECTED_RESULTS.items():
            self.assertEqual(_get_modules_dict_auto_install_config(k), v)


class TestConfigGluePending(TransactionCase):
    """Reconciliation of config-declared glue modules on button_install.

    The hook only targets entries with >=2 specific dependencies
    (``glue:pkg_a/pkg_b``). Unconditional (``module:``) and single-dependency
    (``module:dep``) entries are out of scope and must never be selected.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.module_obj = cls.env["ir.module.module"]
        vals = [
            {"name": name, "state": "uninstalled"}
            for name in (
                "mcai_pkg_a",
                "mcai_pkg_b",
                "mcai_pkg_x",
                "mcai_glue",
                "mcai_glue_b",
                "mcai_single",
                "mcai_uncond",
            )
        ]
        records = cls.module_obj.create(vals)
        (
            cls.pkg_a,
            cls.pkg_b,
            cls.pkg_x,
            cls.glue,
            cls.glue_b,
            cls.single,
            cls.uncond,
        ) = records

    def _pending(self, enabled, disabled=""):
        from unittest import mock

        from odoo.tools import config

        from .. import patch as mcai_patch

        with mock.patch.dict(
            config.options,
            {
                "modules_auto_install_enabled": enabled,
                "modules_auto_install_disabled": disabled,
            },
        ):
            return mcai_patch._get_config_glue_pending(self.env)

    def test_02_glue_pending_when_all_deps_installed(self):
        (self.pkg_a | self.pkg_b).write({"state": "installed"})
        pending = self._pending("mcai_glue:mcai_pkg_a/mcai_pkg_b")
        self.assertIn(self.glue, pending)

    def test_03_glue_pending_when_deps_to_install(self):
        (self.pkg_a | self.pkg_b).write({"state": "to install"})
        pending = self._pending("mcai_glue:mcai_pkg_a/mcai_pkg_b")
        self.assertIn(self.glue, pending)

    def test_04_glue_not_pending_with_missing_dep(self):
        self.pkg_a.write({"state": "installed"})
        # pkg_b stays uninstalled
        pending = self._pending("mcai_glue:mcai_pkg_a/mcai_pkg_b")
        self.assertNotIn(self.glue, pending)
        # dependency that does not exist in ir.module.module at all
        pending = self._pending("mcai_glue:mcai_pkg_a/mcai_does_not_exist")
        self.assertNotIn(self.glue, pending)

    def test_05_disabled_list_respected(self):
        (self.pkg_a | self.pkg_b).write({"state": "installed"})
        pending = self._pending("mcai_glue:mcai_pkg_a/mcai_pkg_b", disabled="mcai_glue")
        self.assertNotIn(self.glue, pending)

    def test_06_out_of_scope_entries_ignored(self):
        (self.pkg_a | self.pkg_b).write({"state": "installed"})
        pending = self._pending("mcai_uncond:,mcai_single:mcai_pkg_a")
        self.assertNotIn(self.uncond, pending)
        self.assertNotIn(self.single, pending)

    def test_07_chained_glue_fixpoint(self):
        from unittest import mock

        from odoo.tools import config

        from .. import patch as mcai_patch

        def fake_original(records):
            records._state_update("to install", ["uninstalled"])

        enabled = "mcai_glue:mcai_pkg_a/mcai_pkg_b," "mcai_glue_b:mcai_pkg_x/mcai_glue"
        with mock.patch.dict(
            config.options,
            {
                "modules_auto_install_enabled": enabled,
                "modules_auto_install_disabled": "",
            },
        ), mock.patch.object(
            mcai_patch, "_original_button_install", side_effect=fake_original
        ):
            # This operation installs the packages; the chained glue must then
            # reconcile to a fixpoint within the SAME operation (each glue is
            # "affected" because a dependency was just installed here).
            mcai_patch._button_install_patched(self.pkg_a | self.pkg_b | self.pkg_x)
        self.assertEqual(self.glue.state, "to install")
        self.assertEqual(self.glue_b.state, "to install")

    def test_08_empty_config_noop(self):
        from unittest import mock

        from odoo.tools import config

        from .. import patch as mcai_patch

        pending = self._pending("")
        self.assertFalse(pending)
        with mock.patch.dict(
            config.options,
            {
                "modules_auto_install_enabled": "",
                "modules_auto_install_disabled": "",
            },
        ), mock.patch.object(mcai_patch, "_original_button_install") as fake_original:
            mcai_patch._button_install_patched(self.module_obj.browse())
        fake_original.assert_called_once()
        self.assertEqual(self.glue.state, "uninstalled")

    def test_09_unrelated_install_leaves_ready_glue_untouched(self):
        """A glue whose packages were already installed BEFORE the operation
        must NOT be reconciled by an unrelated ``button_install`` — that is
        delegated to the deploy script. This is what keeps an unrelated,
        possibly-failing glue from aborting the user's install.
        """
        from unittest import mock

        from odoo.tools import config

        from .. import patch as mcai_patch

        (self.pkg_a | self.pkg_b).write({"state": "installed"})

        def fake_original(records):
            records._state_update("to install", ["uninstalled"])

        enabled = "mcai_glue:mcai_pkg_a/mcai_pkg_b"
        with mock.patch.dict(
            config.options,
            {
                "modules_auto_install_enabled": enabled,
                "modules_auto_install_disabled": "",
            },
        ), mock.patch.object(
            mcai_patch, "_original_button_install", side_effect=fake_original
        ):
            # Install an unrelated module (not a dependency of the glue).
            mcai_patch._button_install_patched(self.uncond)
        self.assertEqual(self.glue.state, "uninstalled")

    def test_10_glue_reconciled_when_operation_completes_deps(self):
        """When THIS operation installs the dependency that completes the
        glue, the glue is reconciled (scoped, non-chained case).
        """
        from unittest import mock

        from odoo.tools import config

        from .. import patch as mcai_patch

        # pkg_a already there; the operation installs pkg_b, completing the deps
        self.pkg_a.write({"state": "installed"})

        def fake_original(records):
            records._state_update("to install", ["uninstalled"])

        enabled = "mcai_glue:mcai_pkg_a/mcai_pkg_b"
        with mock.patch.dict(
            config.options,
            {
                "modules_auto_install_enabled": enabled,
                "modules_auto_install_disabled": "",
            },
        ), mock.patch.object(
            mcai_patch, "_original_button_install", side_effect=fake_original
        ):
            mcai_patch._button_install_patched(self.pkg_b)
        self.assertEqual(self.glue.state, "to install")
