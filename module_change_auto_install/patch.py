# Copyright (C) 2021 - Today: GRAP (http://www.grap.coop)
# @author: Sylvain LE GAL (https://twitter.com/legalsylvain)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import logging
import os

from odoo import modules, _
from odoo.exceptions import UserError
from odoo.tools import config

from odoo.addons.base.models.ir_module import (
    Module,
    assert_log_admin_access,
    ACTION_DICT,
)

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


MODULES_AUTO_INSTALL_ENABLED_DICT = _get_modules_dict_auto_install_config(
    config.get(
        "modules_auto_install_enabled",
        os.environ.get("ODOO_MODULES_AUTO_INSTALL_ENABLED"),
    )
)
MODULES_AUTO_INSTALL_DISABLED_DICT = _get_modules_dict_auto_install_config(
    config.get(
        "modules_auto_install_disabled",
        os.environ.get("ODOO_MODULES_AUTO_INSTALL_DISABLED"),
    )
)


@assert_log_admin_access
def button_install(self):
    # domain to select auto-installable (but not yet installed) modules
    auto_domain = [("state", "=", "uninstalled"), ("auto_install", "=", True)]

    # determine whether an auto-install module must be installed:
    #  - all its dependencies are installed or to be installed,
    #  - at least one dependency is 'to install'
    install_states = frozenset(("installed", "to install", "to upgrade"))

    def must_install(module):
        states = {
            dep.state for dep in module.dependencies_id if dep.auto_install_required
        }
        # Check auto install dependencies defined in the modules_auto_install_enabled
        # configuration and check if they are installed
        if module.name in MODULES_AUTO_INSTALL_ENABLED_DICT.keys():
            specific_dependencies = MODULES_AUTO_INSTALL_ENABLED_DICT[module.name]
            if type(specific_dependencies) is list:
                if specific_dependencies:
                    states = set()
                    for dep_name in specific_dependencies:
                        dependency_module = self.search(
                            [("name", "=", dep_name)]
                        )
                        states.add(dependency_module.state or "uninstalled")
                else:
                    states = {"installed"}

        return (
            module.name not in MODULES_AUTO_INSTALL_DISABLED_DICT.keys()
            and states <= install_states
            and "installed" in states
        )

    modules = self
    while modules:
        # Mark the given modules and their dependencies to be installed.
        modules._state_update("to install", ["uninstalled"])

        # Determine which auto-installable modules must be installed.
        modules = self.search(auto_domain).filtered(must_install)
    # the modules that are installed/to install/to upgrade
    install_mods = self.search([("state", "in", list(install_states))])

    # check individual exclusions
    install_names = {module.name for module in install_mods}
    for module in install_mods:
        for exclusion in module.exclusion_ids:
            if exclusion.name in install_names:
                msg = _('Modules "%s" and "%s" are incompatible.')
                raise UserError(
                    msg % (module.shortdesc, exclusion.exclusion_id.shortdesc)
                )

    # check category exclusions
    def closure(module):
        todo = result = module
        while todo:
            result |= todo
            todo = todo.dependencies_id.depend_id
        return result

    exclusives = self.env["ir.module.category"].search([("exclusive", "=", True)])
    for category in exclusives:
        # retrieve installed modules in category and sub-categories
        categories = category.search([("id", "child_of", category.ids)])
        modules = install_mods.filtered(lambda mod: mod.category_id in categories)
        # the installation is valid if all installed modules in categories
        # belong to the transitive dependencies of one of them
        if modules and not any(modules <= closure(module) for module in modules):
            msg = _('You are trying to install incompatible modules in category "%s":')
            labels = dict(self.fields_get(["state"])["state"]["selection"])
            raise UserError(
                "\n".join(
                    [msg % category.name]
                    + [
                        "- %s (%s)" % (module.shortdesc, labels[module.state])
                        for module in modules
                    ]
                )
            )

    return dict(ACTION_DICT, name=_("Install"))


def post_load():
    _logger.info("Applying patch module_change_auto_intall ...")
    modules.module.load_manifest = _overload_load_manifest
    modules.load_manifest = _overload_load_manifest
    Module.button_install = button_install
