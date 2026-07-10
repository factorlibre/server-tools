# Copyright (C) 2021 - Today: GRAP (http://www.grap.coop)
# @author: Sylvain LE GAL (https://twitter.com/legalsylvain)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import logging
import os

from odoo import modules
from odoo.tools import config

_logger = logging.getLogger(__name__)
_original_load_manifest = modules.module.load_manifest


def _get_modules_dict_auto_install_config(config_value):
    """Given a configuration parameter name, return a dict of
    {module_name: modules_list or False}

    if the odoo.cfg file contains

        modules_auto_install_enabled =
            web_responsive:web,
            base_technical_features:,
            point_of_sale:sale/purchase,
            account_usability

    >>> split_strip('modules_auto_install_enabled')
    {
        'web_responsive': ['web'],
        'base_technical_features': [],
        'point_of_sale': ['sale', 'purchase'],
        'account_usability': False,
    }


    """
    res = {}
    config_value = (config_value or "").strip(" ,")
    config_list = [x.strip() for x in config_value.split(",")]
    for item in config_list:
        if ":" in item:
            res[item.split(":")[0]] = (
                item.split(":")[1] and item.split(":")[1].split("/") or []
            )
        else:
            res[item] = True
    return res


def _overload_load_manifest(module, mod_path=None):

    res = _original_load_manifest(module, mod_path=None)
    auto_install = res.get("auto_install", False)

    modules_auto_install_enabled_dict = _get_modules_dict_auto_install_config(
        config.get(
            "modules_auto_install_enabled",
            os.environ.get("ODOO_MODULES_AUTO_INSTALL_ENABLED"),
        )
    )
    modules_auto_install_disabled_dict = _get_modules_dict_auto_install_config(
        config.get(
            "modules_auto_install_disabled",
            os.environ.get("ODOO_MODULES_AUTO_INSTALL_DISABLED"),
        )
    )

    if auto_install and module in modules_auto_install_disabled_dict.keys():
        _logger.info("Module '%s' has been marked as NOT auto installable." % module)
        res["auto_install"] = False

    if not auto_install and module in modules_auto_install_enabled_dict.keys():
        specific_dependencies = modules_auto_install_enabled_dict.get(module)
        if type(specific_dependencies) is bool:
            # Classical case
            _logger.info("Module '%s' has been marked as auto installable." % module)
            res["auto_install"] = set(res["depends"])
        else:
            if specific_dependencies:
                _logger.info(
                    "Module '%s' has been marked as auto installable if '%s' are installed"
                    % (module, ",".join(specific_dependencies))
                )
            else:
                _logger.info(
                    "Module '%s' has been marked as auto installable in ALL CASES."
                    % module
                )

            res["auto_install"] = set(specific_dependencies)

    return res


INSTALL_STATES = frozenset(("installed", "to install", "to upgrade"))

_original_button_install = None  # captured in post_load()


def _get_config_glue_pending(env):
    """Return uninstalled glue modules whose config dependencies are all met.

    Only entries with >=2 specific dependencies (``glue:pkg_a/pkg_b``) are
    considered: they are the AND-glue between functional packages that the
    native ``auto_install`` mechanism cannot handle (their dependencies are
    not part of the manifest ``depends``). Unconditional (``module:``) and
    single-dependency (``module:dep``) entries are out of scope.

    Dependencies are resolved by module name against ``ir.module.module``;
    a dependency missing from the database counts as uninstalled. A glue is
    pending when every dependency state is within ``INSTALL_STATES`` — this
    covers both retroactive reconciliation (dependencies already installed)
    and dependencies being installed in the current transaction.

    The nested name-based searches are bounded by the configuration size
    (a few dozen entries at most) and only run on explicit install actions,
    never on data-volume flows.
    """
    enabled = _get_modules_dict_auto_install_config(
        config.get(
            "modules_auto_install_enabled",
            os.environ.get("ODOO_MODULES_AUTO_INSTALL_ENABLED"),
        )
    )
    disabled = _get_modules_dict_auto_install_config(
        config.get(
            "modules_auto_install_disabled",
            os.environ.get("ODOO_MODULES_AUTO_INSTALL_DISABLED"),
        )
    )
    module_obj = env["ir.module.module"]
    names = [
        name
        for name, deps in enabled.items()
        if name and name not in disabled and isinstance(deps, list) and len(deps) >= 2
    ]
    if not names:
        return module_obj.browse()
    candidates = module_obj.search(
        [("state", "=", "uninstalled"), ("name", "in", names)]
    )
    pending = module_obj.browse()
    for module in candidates:
        states = set()
        for dep_name in enabled[module.name]:
            dep = module_obj.search([("name", "=", dep_name)], limit=1)
            states.add(dep.state or "uninstalled")
        if states <= INSTALL_STATES:
            pending |= module
    return pending


def _button_install_patched(self):
    res = _original_button_install(self)
    # Post-cascade reconciliation, iterated to a fixpoint so that a glue
    # whose dependencies include another glue installed in this same pass
    # (``glue_b:pkg_x/glue_a``) is caught as well. The upper bound is the
    # number of configured entries: each iteration must mark at least one
    # new module or stop.
    enabled = _get_modules_dict_auto_install_config(
        config.get(
            "modules_auto_install_enabled",
            os.environ.get("ODOO_MODULES_AUTO_INSTALL_ENABLED"),
        )
    )
    for _unused in range(len(enabled) + 1):
        pending = _get_config_glue_pending(self.env)
        if not pending:
            break
        _logger.info("Config auto-install glue to install: %s", pending.mapped("name"))
        # Re-use the core cascade (exclusion and category checks included).
        _original_button_install(pending)
    return res


def post_load():
    global _original_button_install
    _logger.info("Applying patch module_change_auto_intall ...")
    modules.module.load_manifest = _overload_load_manifest
    modules.load_manifest = _overload_load_manifest
    # Import here: at post_load time ``odoo.addons.base`` is already
    # importable, while importing it at module level would be premature for
    # a server-wide module loaded at startup.
    from odoo.addons.base.models.ir_module import Module

    if getattr(Module.button_install, "_mcai_patched", False):
        return
    # The captured original is already decorated with
    # assert_log_admin_access in the core: every call to the wrapper goes
    # through it first, so decorating the wrapper again would only
    # duplicate the admin check and its access log.
    _original_button_install = Module.button_install
    _button_install_patched._mcai_patched = True
    Module.button_install = _button_install_patched
