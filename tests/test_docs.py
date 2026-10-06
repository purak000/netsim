import contextlib
import inspect
import io
import os
import pathlib
import re
import tempfile
import unittest
from unittest import mock

from netsim import cli, dsl, log

SRC = pathlib.Path(__file__).resolve().parent.parent / "netsim"


def run_cli(*argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        cli.main(list(argv))
    return out.getvalue()


class Docs(unittest.TestCase):
    def test_every_dsl_function_has_docstring(self):
        for name, obj in dsl.namespace().items():
            doc = inspect.getdoc(obj) or ""
            self.assertTrue(doc.startswith(f"{name}(") and " -- " in doc.splitlines()[0],
                            f"{name}: docstring line 1 must be 'name(args) -- summary'")

    def test_every_code_in_source_is_in_codes(self):
        used = set()
        for f in SRC.glob("*.py"):
            used |= set(re.findall(r'"([NT]_[A-Z_]+)"', f.read_text()))
        self.assertTrue(used)
        self.assertEqual(used - set(log.CODES), set())

    def test_man_starts_with_th(self):
        page = run_cli("man")
        self.assertTrue(page.startswith(".TH"))
        for sec in ("NAME", "SYNOPSIS", "DESCRIPTION", "COMMANDS", "DSL FUNCTIONS",
                    "DOT LEGEND", "ERROR CODES", "FILES", "EXAMPLES"):
            self.assertIn(f".SH {sec}", page)

    def test_info_unknown_suggests_and_logs(self):
        log.tool.clear()
        with mock.patch.object(log.tool, "sink", None):
            out = run_cli("help", "jion")
        self.assertIn("did you mean join", out)
        self.assertEqual([e.code for e in log.tool.entries], ["T_UNKNOWN"])


class Logs(unittest.TestCase):
    def test_level_e_filters(self):
        with tempfile.TemporaryDirectory() as d:
            net, tool = os.path.join(d, "net.log"), os.path.join(d, "tool.log")
            with mock.patch.object(log.net, "sink", net), mock.patch.object(log.tool, "sink", tool):
                log.net.clear()
                log.net.add("N_SEND", "pc1", "send pc1>r1")
                log.net.add("N_ISOLATED", "x", "x has no links")
                log.net.add("N_NODE_OFF", "r1", "send pc1>d1 dropped at r1 (off)")
                log.tool.add("T_NAME", "line 3", "Error: device 'A' already exists")
                lines = run_cli("logs", "--level", "E").splitlines()
                net_w = run_cli("logs", "--net", "--level", "W").splitlines()
                last = run_cli("logs", "--last", "1").splitlines()
        self.assertEqual([ln.split()[2] for ln in lines], ["N_NODE_OFF", "T_NAME"])
        self.assertEqual([ln.split()[2] for ln in net_w], ["N_ISOLATED", "N_NODE_OFF"])
        self.assertEqual(len(last), 1)


if __name__ == "__main__":
    unittest.main()
