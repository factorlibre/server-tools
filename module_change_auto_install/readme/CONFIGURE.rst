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


**Glue entries with two or more dependencies (``glue:pkg_a/pkg_b``)**

Entries with **two or more** specific dependencies are the AND-glue between
functional packages whose names are **not** part of the glue manifest
``depends``. The native ``auto_install`` mechanism cannot resolve them, so
they are handled explicitly at the moments below, all resolving dependencies
**by name**:

* **Installing modules from the Apps UI.** Every call to
  ``ir.module.module.button_install`` runs a post-cascade pass that installs
  such glue **whose dependencies the current operation has just made
  installable** — i.e. all of its dependencies are installed (or being
  installed in the same transaction) *and* at least one of them was touched
  by this install. The pass iterates to a fixpoint, so a glue depending on
  another glue installed in the same pass is caught as well. Installed glue
  modules are logged::

      INFO db_name odoo.addons.module_change_auto_install.patch: Config auto-install glue to install: ['point_of_sale']

  The pass runs **fail-loud** (no savepoint): if a glue tied to what is being
  installed fails, the error is raised, as with any install. Because the pass
  only ever touches glue related to the current operation, an unrelated,
  already-installable glue is never (re)tried here and can never abort an
  unrelated install.

* **Deployment.** Reconciliation of glue whose packages were already
  installed *before*, independently of any Apps action, is performed by the
  deployment script (``set_addons_auto_install.py``), which sweeps the whole
  configuration by name on every deploy.

* **Brand-new database.** During database initialization these glue entries
  are intentionally **not** auto-installed: since their packages are not part
  of ``depends``, the core would otherwise install them unconditionally on
  every from-scratch database even when the packages are not present. They
  get installed later, by the two mechanisms above, once their packages are
  actually installed.

Notes and limitations:

* The runtime hook and the fresh-database skip only apply to entries with
  **two or more** specific dependencies. Unconditional entries (``module:``)
  are always installed; classic (``module``) and single-dependency
  (``module:dep``, whose dependency is normally part of the manifest
  ``depends``) entries keep the native load-time ``auto_install`` behaviour.
* The module MUST be listed in ``server_wide_modules``: the hook and the
  fresh-database wrapper are applied in ``post_load()``, before the registry
  evaluates any installation.
* The hook wraps ``Module.button_install`` on the Python class of the
  ``base`` addon. A third-party addon overriding ``button_install`` through
  ``_inherit`` without calling ``super()`` would shadow it.
