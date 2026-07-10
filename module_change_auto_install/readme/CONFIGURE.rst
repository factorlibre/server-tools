* Edit your ``odoo.cfg`` configuration file:

* Add the module ``module_change_auto_install`` in the ``server_wide_modules`` list.

* (optional) Add a new entry ``modules_auto_install_disabled`` to mark
  a list of modules as NOT auto installable.
  The environment variable ``ODOO_MODULES_AUTO_INSTALL_DISABLED`` can also be set.

* (optional) Add a new entry ``modules_auto_install_enabled`` to mark
  a list of modules as auto installable. This feature can be usefull for companies
  that are hosting a lot of Odoo instances for many customers, and want some modules
  to be always installed.
  The environment variable ``ODOO_MODULES_AUTO_INSTALL_ENABLED`` can also be set.

The values in the configuration file takes precedence over the environment variable
values.

**Typical Settings**

.. code-block:: cfg

    server_wide_modules = web,module_change_auto_install

    modules_auto_install_disabled =
        partner_autocomplete,
        iap,
        mail_bot

    modules_auto_install_enabled =
        web_responsive:web,
        base_technical_features,
        disable_odoo_online,
        account_usability

When using environment variables, the same configuration is:

.. code-block:: shell

   export ODOO_MODULES_AUTO_INSTALL_DISABLED=partner_autocomplete,iap,mail_bot
   export ODOO_MODULES_AUTO_INSTALL_ENABLED=web_responsive:web,base_technical_features,disable_odoo_online,account_usability

Run your instance and check logs. Modules that has been altered should be present in your log, at the load of your instance:

.. code-block:: shell

    INFO db_name odoo.addons.module_change_auto_install.patch: Module 'iap' has been marked as NOT auto installable.
    INFO db_name odoo.addons.module_change_auto_install.patch: Module 'mail_bot' has been marked as NOT auto installable.
    INFO db_name odoo.addons.module_change_auto_install.patch: Module 'partner_autocomplete' has been marked as NOT auto installable.
    INFO db_name odoo.modules.loading: 42 modules loaded in 0.32s, 0 queries (+0 extra)

**Advanced Configuration Possibilities**

if your ``odoo.cfg`` file contains the following configuration:

.. code-block:: cfg

    modules_auto_install_enabled =
        account_usability,
        web_responsive:web,
        base_technical_features:,
        point_of_sale:sale/purchase

The behaviour will be the following:

* ``account_usability`` module will be installed as soon as all the default dependencies are installed. (here ``account``)

* ``web_responsive`` module will be installed as soon as ``web`` is installed. (Althought ``web_responsive`` depends on ``web`` and ``mail``)

* ``base_technical_features`` will be ALWAYS installed

* ``point_of_sale`` module will be installed as soon as ``sale`` and ``purchase`` module are installed.

When using environment variables, the same configuration is:

.. code-block:: shell

   export ODOO_MODULES_AUTO_INSTALL_ENABLED=account_usability,web_responsive:web,base_technical_features:,point_of_sale:sale/purchase


**Installation of glue entries when installing modules from the Apps UI**

Entries with **two or more** specific dependencies (``glue:pkg_a/pkg_b``) are
also reconciled at runtime: every call to ``ir.module.module.button_install``
(for instance installing a module from the Apps menu) triggers a
post-cascade pass that installs any such glue module whose dependencies are
all installed — or being installed in that same transaction. The pass
iterates to a fixpoint, so a glue depending on another glue installed in the
same pass is caught as well. The reconciliation is also retroactive: if the
dependencies were already installed beforehand, the glue is installed on the
next ``button_install`` call, whatever module it targets. Installed glue
modules are logged::

    INFO db_name odoo.addons.module_change_auto_install.patch: Config auto-install glue to install: ['point_of_sale']

Notes and limitations:

* This runtime hook only applies to entries with >=2 specific dependencies.
  Unconditional entries (``module:``) and single-dependency entries
  (``module:dep``) keep the load-time ``auto_install`` behaviour only.
* The module MUST be listed in ``server_wide_modules``: the hook is applied
  in ``post_load()``, before the registry evaluates any installation.
* The hook wraps ``Module.button_install`` on the Python class of the
  ``base`` addon. A third-party addon overriding ``button_install`` through
  ``_inherit`` without calling ``super()`` would shadow it.
