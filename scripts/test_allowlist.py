#!/usr/bin/env python3
"""Roda a suíte de allowlist/denylist de generate_allowlist.py como teste (não grava o agente).

Equivalente a `python3 scripts/generate_allowlist.py --check`.
Rodar: python3 scripts/test_allowlist.py
"""
import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import generate_allowlist as ga  # noqa: E402


class AllowlistTests(unittest.TestCase):
    def test_all_classification_cases_pass(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            ok = ga.run_tests()
        out = buf.getvalue()
        print(out.strip().splitlines()[-1])
        self.assertTrue(ok, out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
