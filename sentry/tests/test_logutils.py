# Copyright 2016-2017 Versada <https://versada.eu/>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.tests import TransactionCase

from ..logutils import SanitizeOdooCookiesProcessor, SanitizeOdooRpcProcessor


class TestOdooCookieSanitizer(TransactionCase):
    def test_cookie_as_string(self):
        data = {
            "request": {
                "cookies": "website_lang=en_us;"
                "session_id=hello;"
                "Session_ID=hello;"
                "foo=bar"
            }
        }

        proc = SanitizeOdooCookiesProcessor()
        result = proc.process(data)

        self.assertTrue("request" in result)
        http = result["request"]
        self.assertEqual(
            http["cookies"],
            "website_lang=en_us;"
            "session_id={m};"
            "Session_ID={m};"
            "foo=bar".format(m=proc.MASK),
        )

    def test_cookie_as_string_with_partials(self):
        data = {"request": {"cookies": "website_lang=en_us;session_id;foo=bar"}}

        proc = SanitizeOdooCookiesProcessor()
        result = proc.process(data)

        self.assertTrue("request" in result)
        http = result["request"]
        self.assertEqual(
            http["cookies"],
            "website_lang=en_us;session_id;foo=bar",
        )

    def test_cookie_header(self):
        data = {
            "request": {
                "headers": {
                    "Cookie": "foo=bar;"
                    "session_id=hello;"
                    "Session_ID=hello;"
                    "a_session_id_here=hello"
                }
            }
        }

        proc = SanitizeOdooCookiesProcessor()
        result = proc.process(data)

        self.assertTrue("request" in result)
        http = result["request"]
        self.assertEqual(
            http["headers"]["Cookie"],
            "foo=bar;"
            "session_id={m};"
            "Session_ID={m};"
            "a_session_id_here={m}".format(m=proc.MASK),
        )

    def test_password_keys_in_frame_vars(self):
        """Password-like keys must be masked, not only "session_id"."""
        data = {
            "exception": {
                "values": [
                    {
                        "stacktrace": {
                            "frames": [
                                {
                                    "module": "odoo.service.common",
                                    "function": "exp_authenticate",
                                    "vars": {
                                        "db": "prod",
                                        "login": "admin",
                                        "password": "s3cr3t",
                                        "passwd": "s3cr3t",
                                    },
                                },
                            ]
                        }
                    }
                ]
            }
        }

        proc = SanitizeOdooCookiesProcessor()
        result = proc.process(data)

        frame_vars = result["exception"]["values"][0]["stacktrace"]["frames"][0]["vars"]
        self.assertEqual(frame_vars["password"], proc.MASK)
        self.assertEqual(frame_vars["passwd"], proc.MASK)
        self.assertEqual(frame_vars["login"], "admin")

    def test_breadcrumb_data(self):
        """Password-like keys in breadcrumb data must be masked."""
        data = {
            "breadcrumbs": {
                "values": [
                    {
                        "category": "odoo.http.rpc.request",
                        "message": "object.execute_kw",
                        "data": {"password": "s3cr3t", "model": "res.users"},
                    },
                ]
            }
        }

        proc = SanitizeOdooCookiesProcessor()
        result = proc.process(data)

        crumb = result["breadcrumbs"]["values"][0]
        self.assertEqual(crumb["data"]["password"], proc.MASK)
        self.assertEqual(crumb["data"]["model"], "res.users")


class TestOdooRpcSanitizer(TransactionCase):
    def _make_event(self, module, section="exception"):
        return {
            section: {
                "values": [
                    {
                        "stacktrace": {
                            "frames": [
                                {
                                    "module": module,
                                    "function": "dispatch",
                                    "vars": {
                                        "method": "execute_kw",
                                        "params": "('prod', 2, 's3cr3t')",
                                        "args": "('prod', 2, 's3cr3t')",
                                        "data": "<methodCall>...</methodCall>",
                                    },
                                },
                            ]
                        }
                    }
                ]
            }
        }

    def _frame_vars(self, event, section="exception"):
        return event[section]["values"][0]["stacktrace"]["frames"][0]["vars"]

    def test_rpc_frame_vars_masked(self):
        """Positional RPC payloads must be fully masked in RPC frames."""
        proc = SanitizeOdooRpcProcessor()
        for module in (
            "odoo.addons.base.controllers.rpc",
            "odoo.http",
            "odoo.service.common",
            "odoo.service.db",
            "odoo.service.model",
            "odoo.service.security",
        ):
            result = proc.process(self._make_event(module))
            frame_vars = self._frame_vars(result)
            self.assertEqual(frame_vars["params"], proc.MASK, module)
            self.assertEqual(frame_vars["args"], proc.MASK, module)
            self.assertEqual(frame_vars["data"], proc.MASK, module)
            self.assertEqual(frame_vars["method"], "execute_kw", module)

    def test_non_rpc_frame_vars_untouched(self):
        """Variables of frames outside the RPC entry points must be kept."""
        proc = SanitizeOdooRpcProcessor()
        result = proc.process(self._make_event("odoo.addons.sale.models.sale_order"))

        frame_vars = self._frame_vars(result)
        self.assertEqual(frame_vars["params"], "('prod', 2, 's3cr3t')")

    def test_thread_stacktrace_masked(self):
        """Frames in thread stacktraces (attach_stacktrace) are also masked."""
        proc = SanitizeOdooRpcProcessor()
        result = proc.process(self._make_event("odoo.http", section="threads"))

        frame_vars = self._frame_vars(result, section="threads")
        self.assertEqual(frame_vars["params"], proc.MASK)
