"""Testes offline da skill logs-search (sem AWS). Rodar: python3 -m unittest discover -s tests"""
import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "logs-search"))
import logs_search as ls  # noqa: E402

NOW = datetime(2026, 9, 29, 23, 0, 0, tzinfo=timezone.utc)


def audit(ts, verb, resource, name, sub=None, user="system:serviceaccount:kube-system:deployment-controller",
          code=200, req=None, ns="production"):
    obj = {"resource": resource, "name": name, "namespace": ns}
    if sub:
        obj["subresource"] = sub
    e = {"requestReceivedTimestamp": ts, "verb": verb, "objectRef": obj, "user": {"username": user},
         "responseStatus": {"code": code}}
    if req is not None:
        e["requestObject"] = req
    return {"message": json.dumps(e)}


class FakeBackend:
    """Backend offline. `events` pode ser lista ou função(start_ms, end_ms) -> lista."""

    def __init__(self, events=None, streams=None, groups=None, cluster=None,
                 cluster_error=None, stream_error=None, slow_after=None):
        self.events = events or []
        self.streams = streams if streams is not None else [
            {"logStreamName": "kube-apiserver-audit-1", "lastIngestionTime": ls.to_ms(NOW)}]
        self.groups = groups or []
        self.cluster = cluster or {}
        self.cluster_error = cluster_error
        self.stream_error = stream_error
        self.slow_after = slow_after  # nº de fatias antes de simular timeout
        self.calls = []

    def filter_events(self, group, prefix, pattern, start_ms, end_ms, max_events, deadline):
        self.calls.append(("filter", group, prefix, pattern, start_ms, end_ms))
        n_filter = sum(1 for c in self.calls if c[0] == "filter")
        if self.slow_after is not None and n_filter > self.slow_after:
            raise TimeoutError
        evs = self.events(start_ms, end_ms) if callable(self.events) else self.events
        yield from evs[:max_events]

    def describe_log_streams(self, group, prefix=None, latest_first=False, max_items=500):
        self.calls.append(("streams", group, prefix, latest_first))
        if self.stream_error:
            raise self.stream_error
        if callable(self.streams):
            return self.streams(group)
        return self.streams[:max_items]

    def describe_log_groups(self, pattern, max_items=200):
        self.calls.append(("groups", pattern))
        return [g for g in self.groups if pattern in g["logGroupName"]][:max_items]

    def describe_cluster(self, name):
        self.calls.append(("cluster", name))
        if self.cluster_error:
            raise self.cluster_error
        return self.cluster


class TimeTests(unittest.TestCase):
    def test_since(self):
        self.assertEqual(ls.parse_since("6h", NOW), datetime(2026, 9, 29, 17, 0, tzinfo=timezone.utc))
        self.assertEqual(ls.parse_since("30m", NOW).minute, 30)
        for bad in ("", "6", "h", "-1h", "0h", "91d", "6x", "1h;rm"):
            with self.assertRaises(ValueError, msg=bad):
                ls.parse_since(bad, NOW)

    def test_iso(self):
        self.assertEqual(ls.parse_iso("2026-09-29T19:40:00Z"), datetime(2026, 9, 29, 19, 40, tzinfo=timezone.utc))
        self.assertEqual(ls.parse_iso("2026-09-29 19:40").hour, 19)
        self.assertEqual(ls.parse_iso("2026-09-29T16:40:00-03:00").hour, 19)
        with self.assertRaises(ValueError):
            ls.parse_iso("ontem")

    def test_window_label(self):
        same = ls._window_label(datetime(2026, 9, 29, 20, 0, tzinfo=timezone.utc), NOW)
        self.assertEqual(same, "2026-09-29 20:00..23:00 UTC")
        multi = ls._window_label(datetime(2026, 9, 19, 23, 0, tzinfo=timezone.utc), NOW)
        self.assertEqual(multi, "2026-09-19 23:00..2026-09-29 23:00 UTC")

    def test_window_order(self):
        args = ls.parse_args(["logs", "--profile", "P", "--log-group", "g",
                              "--start", "2026-09-29T20:00:00Z", "--end", "2026-09-29T19:00:00Z"])
        with self.assertRaises(ValueError):
            ls.resolve_window(args, NOW)


class PatternTests(unittest.TestCase):
    def test_audit_changes_pattern(self):
        p = ls.build_audit_pattern("production", "api-foo", None, None, False)
        self.assertTrue(p.startswith("{ ") and p.endswith(" }"))
        self.assertIn('$.objectRef.namespace = "production"', p)
        self.assertIn('$.objectRef.name = "api-foo*"', p)
        self.assertIn('$.objectRef.subresource NOT EXISTS || $.objectRef.subresource = "scale"', p)
        self.assertIn('$.verb = "patch"', p)
        self.assertNotIn('"get"', p)
        self.assertLess(len(p), 1024)  # limite do CloudWatch

    def test_audit_status_pattern(self):
        p = ls.build_audit_pattern("production", "api-foo*", None, None, True)
        self.assertIn('$.objectRef.subresource = "status"', p)
        self.assertIn('$.objectRef.name = "api-foo*"', p)
        self.assertNotIn("**", p)

    def test_events_pattern(self):
        p = ls.build_events_pattern("production", "api-foo")
        self.assertIn('$.objectRef.resource = "events"', p)

    def test_injection_rejected(self):
        for bad in ('x" || $.verb = "get', "a b", "x}", "x;rm", "$(id)"):
            with self.assertRaises(ValueError, msg=bad):
                ls.build_audit_pattern("production", bad, None, None, False)


class AuditTests(unittest.TestCase):
    def test_changes_collapse_and_detail(self):
        evs = [
            audit("2026-09-29T20:00:00.1Z", "patch", "deployments", "api-foo", user="lucas@x",
                  req={"spec": {"template": {"spec": {"containers": [{"name": "c", "image": "123.dkr/api-foo:v42"}]}}}}),
            audit("2026-09-29T20:05:00Z", "patch", "deployments", "api-foo", sub="scale",
                  user="system:serviceaccount:keda:keda-operator", req={"spec": {"replicas": 0}}),
            audit("2026-09-29T20:06:00Z", "delete", "pods", "api-foo-abc-1", code=200),
            audit("2026-09-29T20:06:01Z", "delete", "pods", "api-foo-abc-1", code=200),
            audit("2026-09-29T20:07:00Z", "patch", "deployments", "api-foo", code=403,
                  req={"metadata": {"labels": {"a": "b"}}}),
        ]
        rows = ls.summarize_changes(ls._parse_audit(evs))
        self.assertEqual(len(rows), 4)
        self.assertIn("image=api-foo:v42", rows[0][6])
        self.assertEqual(rows[1][2], "deployments/scale")
        self.assertIn("replicas=0", rows[1][6])
        self.assertEqual(rows[1][4], "keda:keda-operator")
        self.assertIn("×2", rows[2][0])
        self.assertIn("FALHOU(403", rows[3][6])

    def test_status_transitions(self):
        def pod(ready, restarts, state="running", last=None):
            cs = {"name": "app", "ready": ready == "True", "restartCount": restarts, "state": {state: {}}}
            if last:
                cs["lastState"] = {"terminated": {"reason": last, "exitCode": 137}}
            return {"status": {"conditions": [{"type": "Ready", "status": ready}], "containerStatuses": [cs]}}
        evs = [
            audit("2026-09-29T22:20:51Z", "patch", "pods", "api-foo-x", sub="status", req=pod("False", 0)),
            audit("2026-09-29T22:21:01Z", "patch", "pods", "api-foo-x", sub="status", req=pod("False", 0)),
            audit("2026-09-29T22:44:33Z", "patch", "pods", "api-foo-x", sub="status", req=pod("True", 1, last="OOMKilled")),
            audit("2026-09-29T22:45:00Z", "update", "deployments", "api-foo", sub="status",
                  req={"status": {"replicas": 2, "readyReplicas": 1,
                                  "conditions": [{"type": "Available", "status": "False",
                                                  "reason": "MinimumReplicasUnavailable"}]}}),
            audit("2026-09-29T22:46:00Z", "patch", "pods", "api-foo-y", sub="status", req={}),  # sem status: ignora
        ]
        rows = ls.summarize_status(ls._parse_audit(evs))
        self.assertEqual(len(rows), 3)
        self.assertIn("×2", rows[0][0])
        self.assertIn("Ready=False", rows[0][2])
        self.assertIn("last=OOMKilled/exit=137", rows[1][2])
        self.assertIn("Available=False(MinimumReplicasUnavailable)", rows[2][2])

    def test_non_json_ignored(self):
        self.assertEqual(ls._parse_audit([{"message": "not json"}, {}]), [])


class EventsTests(unittest.TestCase):
    def test_aggregate_create_and_patch(self):
        probe = "Readiness probe failed: HTTP probe failed with statuscode: 503"
        evs = [
            audit("2026-09-29T22:00:00Z", "create", "events", "api-foo-x.17a", user="kubelet",
                  req={"involvedObject": {"kind": "Pod", "name": "api-foo-x"}, "reason": "Unhealthy",
                       "type": "Warning", "message": probe, "count": 1,
                       "firstTimestamp": "2026-09-21T10:00:00Z", "lastTimestamp": "2026-09-29T22:00:00Z"}),
            audit("2026-09-29T22:10:00Z", "patch", "events", "api-foo-x.17a", user="kubelet",
                  req={"count": 24000, "lastTimestamp": "2026-09-29T22:10:00Z"}),
            audit("2026-09-29T22:05:00Z", "create", "events", "api-foo-y.18b", user="kubelet",
                  req={"involvedObject": {"kind": "Pod", "name": "api-foo-y"}, "reason": "Unhealthy",
                       "type": "Warning", "message": probe, "count": 3}),
            # evento events.k8s.io/v1
            audit("2026-09-29T22:06:00Z", "create", "events", "api-foo.19c", user="deployment-controller",
                  req={"regarding": {"kind": "Deployment", "name": "api-foo"}, "reason": "ScalingReplicaSet",
                       "type": "Normal", "note": "Scaled up replica set api-foo-abc to 2",
                       "series": {"count": 2, "lastObservedTime": "2026-09-29T22:07:00Z"}}),
            # patch sem create na janela
            audit("2026-09-29T22:08:00Z", "patch", "events", "api-foo-z.20d", req={"count": 5}),
        ]
        audits = ls._parse_audit(evs)
        rows = ls.summarize_k8s_events(audits)
        unhealthy = [r for r in rows if r[1] == "Unhealthy"][0]
        self.assertEqual(unhealthy[2], "24003")
        self.assertEqual(unhealthy[3], "2026-09-21 10:00:00")
        self.assertIn("(+1)", unhealthy[5])
        scaling = [r for r in rows if r[1] == "ScalingReplicaSet"][0]
        self.assertEqual(scaling[2], "2")
        self.assertIn("Scaled up", scaling[6])
        unknown = [r for r in rows if r[1] == "?"][0]
        self.assertEqual(unknown[5], "api-foo-z")

        warn = ls.summarize_k8s_events(audits, type_filter="warning")
        self.assertEqual({r[0] for r in warn}, {"Warning"})
        self.assertEqual(ls.summarize_k8s_events(audits, reason_filter="BackOff"), [])


class CliTests(unittest.TestCase):
    def run_mode(self, argv, backend):
        args = ls.parse_args(argv)
        start, end = ls.resolve_window(args, NOW)
        out = io.StringIO()
        with redirect_stdout(out):
            ls.cmd_k8s(args, backend, start, end)
        return out.getvalue()

    def test_k8s_audit_end_to_end(self):
        evs = [audit(f"2026-09-29T22:{m:02d}:00Z", "delete", "pods", f"api-foo-{m}") for m in range(10)]
        be = FakeBackend(evs)
        out = self.run_mode(["k8s-audit", "--profile", "P", "--cluster", "eks-x", "-n", "production",
                             "--name", "api-foo", "--limit", "3"], be)
        first_filter = [c for c in be.calls if c[0] == "filter"][0]
        self.assertEqual(first_filter[1:3], ("/aws/eks/eks-x/cluster", "kube-apiserver-audit"))
        self.assertIn("exibindo 3 de 10", out)
        self.assertIn("api-foo-9", out)          # mantém os mais recentes
        self.assertNotIn("api-foo-0 ", out)

    def test_truncation_note(self):
        evs = [audit("2026-09-29T22:00:00Z", "delete", "pods", f"p{i}") for i in range(5)]
        out = self.run_mode(["k8s-audit", "--profile", "P", "--cluster", "c", "--max-events", "5"], FakeBackend(evs))
        self.assertIn("TRUNCADO", out)

    def test_width_truncates_and_no_newlines(self):
        long_msg = "x\n" * 500
        evs = [audit("2026-09-29T22:00:00Z", "create", "events", "a.1",
                     req={"involvedObject": {"name": "a"}, "reason": "R", "type": "Warning", "message": long_msg})]
        out = self.run_mode(["k8s-events", "--profile", "P", "--cluster", "c", "--width", "40"], FakeBackend(evs))
        data_line = [l for l in out.splitlines() if l.startswith("Warning")][0]
        self.assertLess(len(data_line), 200)
        self.assertTrue(data_line.endswith("…"))

    def test_requires_cluster(self):
        with self.assertRaises(SystemExit), redirect_stdout(io.StringIO()):
            import contextlib
            with contextlib.redirect_stderr(io.StringIO()):
                ls.parse_args(["k8s-events", "--profile", "P"])

    def test_main_rejects_bad_name_without_aws(self):
        import contextlib
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            rc = ls.main(["k8s-audit", "--profile", "P", "--cluster", "c", "--name", 'x" || $.verb = "get'])
        self.assertEqual(rc, 1)
        self.assertIn("valor inválido", err.getvalue())


def _run_k8s(argv, backend):
    args = ls.parse_args(argv)
    start, end = ls.resolve_window(args, NOW)
    out = io.StringIO()
    with redirect_stdout(out):
        rc = ls.cmd_k8s(args, backend, start, end)
    return rc, out.getvalue()


BASE = ["k8s-audit", "--profile", "P", "--cluster", "eks-x", "-n", "production", "--name", "api-foo"]
H = 3_600_000


class AuditHealthTests(unittest.TestCase):
    def test_missing_group(self):
        be = FakeBackend(stream_error=ls.AwsError("x", "ResourceNotFoundException"),
                         cluster={"logging": {"clusterLogging": [{"types": ["api", "audit"], "enabled": False}]}})
        rc, out = _run_k8s(BASE, be)
        self.assertEqual(rc, 2)
        self.assertIn("AUDIT INDISPONÍVEL", out)
        self.assertIn("não existe", out)
        self.assertIn("audit DESABILITADO", out)
        self.assertIn("NÃO significa", out)
        self.assertFalse([c for c in be.calls if c[0] == "filter"])  # não varre à toa

    def test_no_streams_and_cluster_not_found(self):
        be = FakeBackend(streams=[], cluster_error=ls.AwsError("x", "ResourceNotFoundException"))
        rc, out = _run_k8s(BASE, be)
        self.assertEqual(rc, 2)
        self.assertIn("sem streams", out)
        self.assertIn("cluster não encontrado", out)

    def test_stale_audit(self):
        be = FakeBackend(streams=[{"lastIngestionTime": ls.to_ms(NOW) - 48 * H}])
        rc, out = _run_k8s(BASE + ["--since", "6h", "--log-group", "/custom/audit"], be)
        self.assertEqual(rc, 2)
        self.assertIn("antes da janela", out)
        self.assertNotIn("DESABILITADO", out)  # sem dado de logging => não afirma nada
        self.assertIn("sem informação de logging", out)
    def test_lagging_stream_metadata_confirmed_by_probe(self):
        # lastEventTimestamp atrasado (3h) mas há eventos recentes: NÃO pode dizer indisponível
        be = FakeBackend(events=[{"message": "{}"}],
                         streams=[{"logStreamName": "kube-apiserver-audit-z", "lastEventTimestamp": ls.to_ms(NOW) - 3 * H}])
        rc, out = _run_k8s(BASE + ["--since", "1h"], be)
        self.assertEqual(rc, 0)
        self.assertNotIn("INDISPONÍVEL", out)
        self.assertNotIn("AVISO", out)

    def test_probe_timeout_does_not_claim_unavailable(self):
        be = FakeBackend(slow_after=0, streams=[{"lastEventTimestamp": ls.to_ms(NOW) - 48 * H}])
        state = ls.audit_health(be, "g", NOW - ls.parse_duration("6h"), NOW)["state"]
        self.assertEqual(state, "ok")

    def test_ignores_non_audit_streams_when_sorting(self):
        streams = [{"logStreamName": "authenticator-1", "lastIngestionTime": ls.to_ms(NOW)},
                   {"logStreamName": "kube-apiserver-audit-1", "lastIngestionTime": ls.to_ms(NOW) - 30 * 60_000}]
        be = FakeBackend(streams=streams)
        h = ls.audit_health(be, "g", NOW - ls.parse_duration("1h"), NOW)
        self.assertEqual((h["state"], h["last"]), ("ok", ls.to_ms(NOW) - 30 * 60_000))

    def test_gap_warns_but_scans(self):
        be = FakeBackend(streams=[{"lastIngestionTime": ls.to_ms(NOW) - 5 * H}])
        rc, out = _run_k8s(BASE + ["--since", "24h"], be)
        self.assertEqual(rc, 0)
        self.assertIn("AVISO: último evento de audit", out)

    def test_access_denied_propagates(self):
        be = FakeBackend(stream_error=ls.AwsError("negado", "AccessDeniedException"))
        with self.assertRaises(ls.AwsError):
            _run_k8s(BASE, be)


class SliceScanTests(unittest.TestCase):
    def test_newest_first_slices(self):
        be = FakeBackend()
        start = datetime(2026, 9, 29, 5, 0, tzinfo=timezone.utc)
        ev, meta = ls.scan_filter_slices(be, "g", "p", start, NOW, ls.parse_duration("6h"), 100, 60)
        spans = [(c[4], c[5]) for c in be.calls if c[0] == "filter"]
        self.assertEqual(len(spans), 3)                      # 18h / 6h
        self.assertEqual(spans[0][1], ls.to_ms(NOW))         # primeira fatia = mais recente
        self.assertEqual(spans[-1][0], ls.to_ms(start))
        self.assertTrue(all(a[0] == b[1] for a, b in zip(spans, spans[1:])))  # contíguas
        self.assertFalse(meta["partial"])
        self.assertEqual(meta["covered_from"], start)

    def test_timeout_keeps_recent_part(self):
        be = FakeBackend(slow_after=2)
        start = NOW - ls.parse_duration("10d")
        _, meta = ls.scan_filter_slices(be, "g", "p", start, NOW, ls.parse_duration("6h"), 100, 60)
        self.assertTrue(meta["partial"])
        self.assertEqual(meta["covered_from"], NOW - ls.parse_duration("12h"))

    def test_truncation_stops(self):
        evs = [{"message": "{}"}] * 5
        be = FakeBackend(events=evs)
        _, meta = ls.scan_filter_slices(be, "g", "p", NOW - ls.parse_duration("2d"), NOW,
                                        ls.parse_duration("6h"), 5, 60)
        self.assertTrue(meta["truncated"])
        self.assertEqual(len([c for c in be.calls if c[0] == "filter"]), 1)


class CoverageTests(unittest.TestCase):
    def test_partial_scan_reports_coverage_and_never_queries(self):
        recent = audit("2026-09-29T22:00:00Z", "patch", "deployments", "api-foo", req={"spec": {"replicas": 3}})
        be = FakeBackend(events=[recent], slow_after=1)
        rc, out = _run_k8s(BASE + ["--since", "10d"], be)
        self.assertEqual(rc, 0)
        self.assertIn("PARCIAL: cobertura completa só de 2026-09-29 17:00:00", out)
        self.assertIn("NÃO foi lido", out)
        self.assertIn("replicas=3", out)
        self.assertEqual({c[0] for c in be.calls}, {"filter", "streams"})

    def test_engine_option_removed(self):
        import contextlib
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            ls.parse_args(BASE + ["--engine", "insights"])

    def test_dedupe_by_audit_id(self):
        a = {"auditID": "1", "stage": "ResponseComplete", "requestReceivedTimestamp": "2"}
        b = {"auditID": "0", "stage": "ResponseComplete", "requestReceivedTimestamp": "1"}
        self.assertEqual(ls._dedupe_sort([a, b, dict(a)]), [b, a])

    def test_bad_slice_rejected(self):
        err = io.StringIO()
        import contextlib
        with contextlib.redirect_stderr(err):
            rc = ls.main(BASE + ["--slice", "0h"])
        self.assertEqual(rc, 1)


class SourcesTests(unittest.TestCase):
    def run_sources(self, argv, be):
        args = ls.parse_args(["sources", "--profile", "P"] + argv)
        start, end = ls.resolve_window(args, NOW)
        out = io.StringIO()
        with redirect_stdout(out):
            rc = ls.cmd_sources(args, be, start, end)
        return rc, out.getvalue()

    def test_full_discovery(self):
        now = ls.to_ms(NOW)
        groups = [{"logGroupName": "/aws/eks/eks-x/cluster", "storedBytes": 10 * 1024 ** 3, "retentionInDays": 30},
                  {"logGroupName": "/aws/containerinsights/eks-x/application", "storedBytes": 2048},
                  {"logGroupName": "/aws/containerinsights/eks-x/performance", "storedBytes": 0},
                  {"logGroupName": "log_group_api-foo", "storedBytes": 5, "retentionInDays": 7}]
        last = {"/aws/eks/eks-x/cluster": now - 60_000, "/aws/containerinsights/eks-x/application": now - 120_000,
                "/aws/containerinsights/eks-x/performance": None, "log_group_api-foo": now - 400 * 86_400_000}

        def streams(group):
            if group not in last:
                return [{"lastIngestionTime": now}]
            return [{"lastIngestionTime": last[group]}] if last[group] else []
        be = FakeBackend(groups=groups, streams=streams,
                         cluster={"logging": {"clusterLogging": [
                             {"types": ["api", "audit"], "enabled": True},
                             {"types": ["scheduler"], "enabled": False}]}})
        rc, out = self.run_sources(["--cluster", "eks-x", "--name", "api-foo"], be)
        self.assertEqual(rc, 0)
        self.assertIn("habilitados=api,audit desabilitados=scheduler", out)
        self.assertIn("audit EKS (/aws/eks/eks-x/cluster): OK", out)
        self.assertIn("container insights: presente (application,performance)", out)
        self.assertIn("log groups relacionados: 4", out)
        self.assertRegex(out, r"log_group_api-foo .*\| PARADO")
        self.assertRegex(out, r"performance .*\| vazio")
        self.assertIn("logs --log-group /aws/containerinsights/eks-x/application", out)

    def test_no_audit_no_groups(self):
        be = FakeBackend(stream_error=ls.AwsError("x", "ResourceNotFoundException"),
                         cluster={"logging": {"clusterLogging": [{"types": ["api", "audit"], "enabled": False}]}})
        rc, out = self.run_sources(["--cluster", "eks-dev"], be)
        self.assertIn("habilitados=nenhum desabilitados=api,audit", out)
        self.assertIn("AUSENTE", out)
        self.assertIn("container insights: ausente", out)
        self.assertIn("sem audit ->", out)
        self.assertIn("nenhum log group encontrado", out)

    def test_cluster_access_denied_is_not_fatal(self):
        be = FakeBackend(cluster_error=ls.AwsError("x", "AccessDeniedException"),
                         groups=[{"logGroupName": "/aws/eks/c/cluster"}])
        rc, out = self.run_sources(["--cluster", "c"], be)
        self.assertEqual(rc, 0)
        self.assertIn("sem permissão eks:DescribeCluster", out)

    def test_term_validation(self):
        err = io.StringIO()
        import contextlib
        with contextlib.redirect_stderr(err):
            rc = ls.main(["sources", "--profile", "P", "--pattern", "a b;rm"])
        self.assertEqual(rc, 1)
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            ls.parse_args(["sources", "--profile", "P"])


class FormatTests(unittest.TestCase):
    def test_age_and_bytes(self):
        self.assertEqual(ls.fmt_age(ls.to_ms(NOW) - 3 * H, NOW), "3h")
        self.assertEqual(ls.fmt_age(ls.to_ms(NOW) - 90_000, NOW), "1min")
        self.assertEqual(ls.fmt_bytes(0), "0 B")
        self.assertEqual(ls.fmt_bytes(1536), "1.5 KB")
        self.assertEqual(ls.fmt_bytes(5 * 1024 ** 3), "5.0 GB")


class LogsModeTests(unittest.TestCase):
    def run_logs(self, argv, be):
        args = ls.parse_args(["logs", "--profile", "P", "--log-group", "/aws/ecs/app"] + argv)
        start, end = ls.resolve_window(args, NOW)
        out = io.StringIO()
        with redirect_stdout(out):
            rc = ls.cmd_logs(args, be, start, end)
        return rc, out.getvalue()

    def evs(self):
        base = ls.to_ms(NOW) - 30 * 60_000
        msgs = ["ERROR timeout calling 10.0.1.5:8080 after 5000ms req=1a2b3c4d-1111-2222-3333-444455556666",
                "ERROR timeout calling 10.0.1.9:8080 after 5012ms req=aaaaaaaa-1111-2222-3333-444455556666",
                "WARN redis connection refused", "ERROR timeout calling 10.0.1.7:8080 after 4999ms req=bbbbbbbb-1111-2222-3333-444455556666"]
        return [{"timestamp": base + i * 60_000, "message": m, "logStreamName": f"pod-{i % 2}"}
                for i, m in enumerate(msgs)]

    def test_group_by_message_normalizes(self):
        be = FakeBackend(events=self.evs())
        rc, out = self.run_logs(["--since", "1h"], be)
        self.assertEqual(rc, 0)
        self.assertRegex(out, r"\n3 +\| .*timeout calling")
        self.assertIn(ls.DEFAULT_ERROR_PATTERN, out)
        f = [c for c in be.calls if c[0] == "filter"][0]
        self.assertEqual((f[1], f[2], f[3]), ("/aws/ecs/app", None, ls.DEFAULT_ERROR_PATTERN))

    def test_group_by_bin_stream_none_and_all(self):
        rc, out = self.run_logs(["--group-by", "bin", "--bin", "1h", "--all"], FakeBackend(events=self.evs()))
        self.assertIn("filter-pattern: (nenhum)", out)
        self.assertRegex(out, r"2026-09-29 22:00:00 +\| 4")
        rc, out = self.run_logs(["--group-by", "stream"], FakeBackend(events=self.evs()))
        self.assertRegex(out, r"2 +\| .*pod-0")
        rc, out = self.run_logs(["--group-by", "none", "--limit", "1", "--stream-prefix", "pod-1"],
                                FakeBackend(events=self.evs()))
        self.assertIn("exibindo 1 de 4", out)
        self.assertIn("after 4999ms", out)  # mais recente primeiro

    def test_all_and_pattern_conflict(self):
        import contextlib
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            ls.parse_args(["logs", "--profile", "P", "--log-group", "g", "--all", "--filter-pattern", "x"])

    def test_normalize(self):
        self.assertEqual(ls.normalize_message("GET /a 503 12ms at 2026-09-29T22:00:01.123Z from 10.1.2.3"),
                         "GET /a <n> <n>ms at <ts> from <ip>")


class ReadOnlyTests(unittest.TestCase):
    def test_only_free_read_apis_in_source(self):
        import re
        src = (Path(ls.__file__)).read_text(encoding="utf-8")
        allowed = {"filter_log_events", "describe_log_streams", "describe_log_groups", "describe_cluster"}
        self.assertEqual(set(re.findall(r"self\.(?:logs|eks)\.(\w+)", src)), allowed)
        cli = set(re.findall(r'\["(\w[\w-]+)", "--', src))
        self.assertTrue(cli and cli <= {"filter-log-events", "describe-log-streams", "describe-log-groups",
                                        "describe-cluster"}, cli)
        # custo zero: nenhuma API cobrada por consulta pode aparecer no código
        for billed in ("start_query", "start-query", "get_query_results", "start_live_tail", "StartLiveTail",
                       "get_metric_data", "get-metric-data", "get_cost_and_usage", "athena"):
            self.assertNotIn(billed, src, billed)
        self.assertEqual(set(re.findall(r'self\._run\("(\w+)"', src)), {"logs", "eks"})
        self.assertEqual(set(re.findall(r'\.client\("(\w+)"\)', src)), {"logs", "eks"})
        self.assertNotIn("open(", src)
        self.assertNotIn("shell=True", src)


if __name__ == "__main__":
    unittest.main()
