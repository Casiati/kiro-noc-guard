#!/usr/bin/env python3
"""Testes da busca da KB (kb_manager.search_kb / search_entry). Sem rede, sem AWS."""
import contextlib
import importlib.util
import io
import tempfile
import unittest
from pathlib import Path

KB_PATH = Path(__file__).resolve().parent.parent / "skills" / "knowledge-builder" / "kb_manager.py"
_spec = importlib.util.spec_from_file_location("kb_manager", KB_PATH)
kb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(kb)


def entry(date, title, body):
    return f"\n### [{date}] {title}\n{body}\n"


class KbSearchTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def write(self, name, *entries):
        (self.dir / name).write_text("".join(entries), encoding="utf-8")

    def run_cli(self, query):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            kb.search_entry(None, self.dir, query)
        return out.getvalue(), err.getvalue()

    # --- AND em qualquer ordem -------------------------------------------------
    def test_all_terms_any_order_not_contiguous(self):
        self.write("guardduty_i-0fa7.md", entry(
            "2026-11-10 10:00:00", "GuardDuty Tunel reidoscanais",
            "Finding DriveBySourceTraffic na instancia i-0fa7e4a1108d72dd0 (streaming pirata via VPN)."))
        self.write("outro.md", entry("2026-11-01 09:00:00", "GuardDuty generico", "Outro finding."))
        r = kb.search_kb(self.dir, "GuardDuty DriveBySourceTraffic i-0fa7e4a1108d72dd0")
        self.assertEqual(r["mode"], "all")
        self.assertEqual([f["name"] for f in r["files"]], ["guardduty_i-0fa7.md"])
        r2 = kb.search_kb(self.dir, "i-0fa7e4a1108d72dd0 pirata DriveBySourceTraffic")  # outra ordem
        self.assertEqual(r2["mode"], "all")

    def test_single_term_still_works(self):
        self.write("a.md", entry("2026-11-10 10:00:00", "X", "reidoscanais bloqueado"))
        self.assertEqual(kb.search_kb(self.dir, "reidoscanais")["mode"], "all")

    # --- acentos e caixa --------------------------------------------------------
    def test_accents_and_case_ignored_both_sides(self):
        self.write("a.md", entry("2026-11-10 10:00:00", "Investigacao", "identificacao do recurso"))
        self.assertEqual(kb.search_kb(self.dir, "INVESTIGAÇÃO identificação")["mode"], "all")
        self.write("b.md", entry("2026-11-10 10:00:00", "Investigação", "Identificação"))
        self.assertEqual(len(kb.search_kb(self.dir, "investigacao")["files"]), 2)

    # --- parcial / nenhum --------------------------------------------------------
    def test_partial_when_no_file_has_all_terms(self):
        self.write("a.md", entry("2026-11-10 10:00:00", "A", "VPN em uso"))
        self.write("b.md", entry("2026-11-11 10:00:00", "B", "streaming bloqueado"))
        r = kb.search_kb(self.dir, "VPN streaming pirata")
        self.assertEqual(r["mode"], "partial")
        self.assertEqual({f["name"] for f in r["files"]}, {"a.md", "b.md"})
        out, _ = self.run_cli("VPN streaming pirata")
        self.assertIn("PARCIAL", out)
        self.assertIn("faltou:", out)

    def test_none_message_and_hint(self):
        self.write("a.md", entry("2026-11-10 10:00:00", "A", "nada relevante"))
        out, _ = self.run_cli("inexistente outro")
        self.assertIn("Nenhum registro contém todos os termos", out)
        self.assertIn("termos isolados", out)
        self.assertNotIn("PARCIAL", out)

    def test_single_unmatched_term_is_none_not_partial(self):
        self.write("a.md", entry("2026-11-10 10:00:00", "A", "nada"))
        self.assertEqual(kb.search_kb(self.dir, "zzz")["mode"], "none")

    def test_empty_query_returns_none(self):
        self.write("a.md", entry("2026-11-10 10:00:00", "A", "x"))
        self.assertEqual(kb.search_kb(self.dir, "   ")["mode"], "none")

    # --- ranking, datas e blocos --------------------------------------------------
    def test_ranking_more_terms_then_most_recent(self):
        self.write("antigo.md", entry("2026-01-01 00:00:00", "T", "alfa beta"))
        self.write("recente.md", entry("2026-11-01 00:00:00", "T", "alfa beta"))
        self.write("parcial.md", entry("2026-12-01 00:00:00", "T", "alfa"))
        r = kb.search_kb(self.dir, "alfa beta")
        self.assertEqual(r["mode"], "all")
        self.assertEqual([f["name"] for f in r["files"]], ["recente.md", "antigo.md"])

    def test_header_shows_filename_date_and_matched_terms(self):
        self.write("a.md", entry("2026-10-17 21:18:47", "T", "alfa beta"))
        out, _ = self.run_cli("alfa beta")
        self.assertIn("📄 Arquivo: a.md", out)
        self.assertIn("2/2 termos", out)
        self.assertIn("último registro: 2026-10-17 21:18:47", out)

    def test_only_matching_blocks_are_printed_best_first(self):
        self.write("a.md",
                   entry("2026-01-01 00:00:00", "um", "alfa"),
                   entry("2026-02-01 00:00:00", "dois", "alfa beta"),
                   entry("2026-03-01 00:00:00", "tres", "sem relacao"))
        out, _ = self.run_cli("alfa beta")
        self.assertIn("dois", out)
        self.assertNotIn("sem relacao", out)
        self.assertLess(out.index("dois"), out.index("um"))  # bloco com mais termos primeiro

    def test_filename_only_match_shows_latest_block(self):
        self.write("CL999_reidoscanais.md",
                   entry("2026-01-01 00:00:00", "velho", "texto"),
                   entry("2026-05-01 00:00:00", "novo", "texto"))
        r = kb.search_kb(self.dir, "reidoscanais")
        self.assertEqual(r["mode"], "all")
        self.assertIn("novo", r["files"][0]["blocks"][0]["text"])

    # --- contenção de tokens -------------------------------------------------------
    def test_truncates_files_and_blocks_with_marker(self):
        for i in range(kb.MAX_FILES + 3):
            self.write(f"f{i:02d}.md", entry(f"2026-11-{i + 1:02d} 00:00:00", "T", "alfa"))
        out, _ = self.run_cli("alfa")
        self.assertEqual(out.count("📄 Arquivo:"), kb.MAX_FILES)
        self.assertIn(f"TRUNCADO: exibindo {kb.MAX_FILES} de {kb.MAX_FILES + 3}", out)

        many = "".join(entry(f"2026-01-{i + 1:02d} 00:00:00", f"b{i}", "beta") for i in range(kb.MAX_BLOCKS_PER_FILE + 2))
        self.write("blocos.md", many)
        out, _ = self.run_cli("beta")
        self.assertIn("TRUNCADO: +2 registro(s)", out)

    # --- robustez ---------------------------------------------------------------------
    def test_unreadable_file_is_reported_not_silenced(self):
        self.write("ok.md", entry("2026-11-10 10:00:00", "A", "alfa"))
        (self.dir / "ruim.md").write_bytes(b"\xff\xfe\x00 alfa invalido")
        out, err = self.run_cli("alfa")
        self.assertIn("ok.md", out)
        self.assertIn("1 arquivo(s) da KB não puderam ser lidos", err)

    def test_duplicate_terms_counted_once(self):
        self.write("a.md", entry("2026-11-10 10:00:00", "A", "alfa"))
        r = kb.search_kb(self.dir, "alfa ALFA álfa")
        self.assertEqual(len(r["terms"]), 1)
        self.assertEqual(r["mode"], "all")


if __name__ == "__main__":
    unittest.main()
