#!/usr/bin/env python3
"""Testes offline de scripts/validate_skills.py. Rodar: python3 scripts/test_validate_skills.py"""
import io
import sys
import tempfile
import textwrap
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import validate_skills as vs  # noqa: E402

GOOD_MD = """---
name: {name}
description: Skill de teste somente leitura usada pelos testes do validador.
---

# {name}

Documentação.
"""


class SkillFixture:
    """Cria skills/<name>/ temporário com SKILL.md e scripts."""

    def __init__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def add(self, name, files=None, md=GOOD_MD):
        d = self.root / name
        d.mkdir()
        if md is not None:
            (d / "SKILL.md").write_text(md.format(name=name), encoding="utf-8")
        for fname, content in (files or {}).items():
            (d / fname).write_text(textwrap.dedent(content), encoding="utf-8")
        return d

    def report(self, name):
        return vs.validate_skill(self.root / name)

    def cleanup(self):
        self._tmp.cleanup()


class Base(unittest.TestCase):
    def setUp(self):
        self.fx = SkillFixture()

    def tearDown(self):
        self.fx.cleanup()

    def assertClean(self, report):
        self.assertEqual([str(f) for f in report.errors], [])

    def assertError(self, report, category, fragment):
        hits = [f for f in report.errors if f.category == category and fragment in f.message]
        self.assertTrue(hits, f"esperado ERROR [{category}] contendo {fragment!r}; "
                              f"obtido: {[str(f) for f in report.findings]}")


class SkillMdTests(Base):
    def test_valid_skill_passes(self):
        self.fx.add("ok-skill", {"run.py": "print('hi')\n"})
        self.assertClean(self.fx.report("ok-skill"))

    def test_missing_skill_md(self):
        self.fx.add("no-md", md=None)
        self.assertError(self.fx.report("no-md"), "skill-md", "ausente")

    def test_missing_description(self):
        self.fx.add("no-desc", md="---\nname: no-desc\n---\n\nCorpo.\n")
        self.assertError(self.fx.report("no-desc"), "skill-md", "description")

    def test_missing_frontmatter(self):
        self.fx.add("no-fm", md="# sem frontmatter\n")
        self.assertError(self.fx.report("no-fm"), "skill-md", "---")

    def test_name_must_match_dir(self):
        self.fx.add("dir-a", md=GOOD_MD.replace("{name}", "outro-nome", 1))
        self.assertError(self.fx.report("dir-a"), "skill-md", "difere")

    def test_folded_description(self):
        md = "---\nname: folded\ndescription: >\n  Descrição longa em bloco\n  dobrado do YAML.\n---\n\nCorpo.\n"
        self.fx.add("folded", md=md)
        self.assertClean(self.fx.report("folded"))


class SecurityTests(Base):
    def test_sdk_mutation_call(self):
        self.fx.add("bad", {"x.py": "import boto3\nboto3.client('logs').delete_log_group(logGroupName='g')\n"})
        self.assertError(self.fx.report("bad"), "security", "delete_log_group")

    def test_cli_mutation_argv(self):
        self.fx.add("bad", {"x.py": "cmd = ['aws', 'ec2', 'terminate-instances', '--instance-ids', 'i-1']\n"})
        self.assertError(self.fx.report("bad"), "security", "terminate-instances")

    def test_kubectl_write(self):
        self.fx.add("bad", {"x.py": "cmd = ['kubectl', '-n', 'prod', 'rollout', 'restart', 'deploy/x']\n"})
        self.assertError(self.fx.report("bad"), "security", "kubectl rollout")

    def test_local_delete_and_shell(self):
        self.fx.add("bad", {"x.py": "import os, subprocess\nos.remove('/tmp/x')\n"
                                    "subprocess.run('ls', shell=True)\n"})
        r = self.fx.report("bad")
        self.assertError(r, "security", "os.remove")
        self.assertError(r, "security", "shell=True")

    def test_shell_string_rm(self):
        self.fx.add("bad", {"x.sh": "#!/bin/sh\nrm -rf /tmp/cache\n"})
        self.assertError(self.fx.report("bad"), "security", "rm -rf")

    def test_read_only_calls_pass(self):
        src = """
        import subprocess, boto3
        boto3.client('ec2').describe_instances()
        subprocess.run(['aws', 'logs', 'describe-log-groups'], capture_output=True)
        d = {}
        d.update(a=1)
        'abc'.startswith('a')
        """
        self.fx.add("ro", {"x.py": src})
        self.assertClean(self.fx.report("ro"))

    def test_docstring_is_ignored(self):
        self.fx.add("doc", {"x.py": '"""Nunca rodar aws s3 sync nem kubectl delete aqui."""\n'})
        self.assertClean(self.fx.report("doc"))

    def test_pragma_with_reason_allows(self):
        src = "# noc-guard: allow-mutation: cache local da própria skill\nopen('/tmp/c', 'a')\n"
        self.fx.add("prag", {"x.py": src})
        r = self.fx.report("prag")
        self.assertClean(r)
        self.assertTrue(any(f.level == "NOTE" for f in r.findings))

    def test_pragma_without_reason_fails(self):
        self.fx.add("prag", {"x.py": "open('/tmp/c', 'w')  # noc-guard: allow-mutation\n"})
        self.assertError(self.fx.report("prag"), "security", "sem motivo")

    def test_billed_api_not_overridable(self):
        src = ("# noc-guard: allow-mutation: tentativa de liberar Logs Insights\n"
               "boto3.client('logs').start_query(queryString='x')\n")
        self.fx.add("cost", {"x.py": src})
        self.assertError(self.fx.report("cost"), "cost", "start_query")


class TokenTests(Base):
    def test_unbounded_log_query_fails(self):
        src = """
        import boto3
        p = boto3.client('logs').get_paginator('filter_log_events')
        for page in p.paginate(logGroupName='g'):
            for e in page['events']:
                print(e)
        """
        self.fx.add("dump", {"x.py": src})
        self.assertError(self.fx.report("dump"), "tokens", "filter_log_events")

    def test_explicit_cap_passes(self):
        src = """
        import boto3
        n = 0
        for page in boto3.client('cloudtrail').get_paginator('lookup_events').paginate():
            for e in page['Events']:
                n += 1
                if n >= 100:
                    return_value = None
                    break
        """
        self.fx.add("cap", {"x.py": src})
        r = self.fx.report("cap")
        self.assertClean(r)
        self.assertTrue(r.token_evidence)

    def test_limit_parameter_passes(self):
        self.fx.add("lim", {"x.py": "import boto3\nboto3.client('logs').filter_log_events(logGroupName='g', limit=50)\n"})
        self.assertClean(self.fx.report("lim"))


class RepoTests(unittest.TestCase):
    def test_repository_skills_are_compliant(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = vs.main([])
        self.assertEqual(code, 0, buf.getvalue())

    def test_missing_dir_returns_error(self):
        with redirect_stdout(io.StringIO()):
            self.assertEqual(vs.main(["--skills-dir", "/nonexistent/skills"]), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
