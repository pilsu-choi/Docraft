"""backend 복제본 2개 이상: 차트(복제본·롤링·동시성 합계 유지)와 파드끼리 겹쳐도 안전한 기동 작업."""

import shutil
import subprocess
import threading
from pathlib import Path

import pytest
import yaml

from backend import failures
from backend.db import connect
from backend.main import claim
from tests.test_api import project, upload, wait_for
from tests.test_jobs import set_status

CHART = Path(__file__).resolve().parent.parent / "deploy/k8s/helm/docraft"


def render(*sets):
    if not shutil.which("helm"):
        pytest.skip("helm 없음")
    args = ["helm", "template", "t", str(CHART), "--set", "vllmVlm.enabled=true", "--set", "vllmVlm.parallel=replicas"]
    for item in sets:
        args += ["--set", item]
    return [doc for doc in yaml.safe_load_all(subprocess.run(args, check=True, capture_output=True, text=True).stdout) if doc]


def deployment(docs, suffix):
    return next(d for d in docs if d["kind"] == "Deployment" and d["metadata"]["name"].endswith(suffix))


def env(docs):
    return next(d for d in docs if d["kind"] == "ConfigMap" and d["metadata"]["name"].endswith("-env"))["data"]


@pytest.mark.parametrize("replicas", [1, 2, 3])
def test_backend_and_router_replicas_roll_without_downtime(replicas):
    docs = render(f"backend.replicas={replicas}", f"vllmVlm.router.replicas={replicas}")
    for suffix in ("-backend", "-vllm-router"):
        spec = deployment(docs, suffix)["spec"]
        assert spec["replicas"] == replicas
        assert spec["strategy"] == {"type": "RollingUpdate", "rollingUpdate": {"maxUnavailable": 0, "maxSurge": 1}}


@pytest.mark.parametrize("replicas", [1, 2, 3, 5])
@pytest.mark.parametrize("total", [1, 6, 24, 25])
def test_concurrency_totals_are_kept_across_replicas(replicas, total):
    data = env(render(f"backend.replicas={replicas}", f"backend.vlmConcurrency={total}", f"backend.ocrConcurrency={total}",
                      f"backend.tablePageConcurrency={total}", f"queue.concurrency={total}"))
    for name in ("VLM_CONCURRENCY", "OCR_CONCURRENCY", "TABLE_PAGE_CONCURRENCY", "QUEUE_CONCURRENCY"):
        per_pod = int(data[name])
        assert per_pod >= 1 and per_pod * replicas >= total and (per_pod - 1) * replicas < total  # 올림 나눗셈


def test_zero_concurrency_stays_unlimited():
    assert env(render("backend.replicas=2", "queue.concurrency=0"))["QUEUE_CONCURRENCY"] == "0"


def test_concurrent_claims_have_one_winner():
    """같은 문서를 두 파드(스레드)가 동시에 집어도 조건부 UPDATE 한 번만 성공한다."""
    document_id = upload(project("ha-claim"))
    wait_for(document_id, "parsed")
    with connect() as db:
        generation = db.execute("SELECT job_generation FROM documents WHERE id=?", (document_id,)).fetchone()["job_generation"]
    set_status(document_id, "queued", "2000-01-01T00:00:00+00:00")
    owners, barrier = [], threading.Barrier(4)

    def attempt():
        barrier.wait()
        with connect() as db:
            owners.append(claim(db, document_id, "parsing", generation))

    threads = [threading.Thread(target=attempt) for _ in range(4)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len([o for o in owners if o]) == 1


def test_prune_survives_entries_removed_by_another_pod(monkeypatch, tmp_path):
    day = tmp_path / "29990101"
    (day / "gone").mkdir(parents=True)
    (day / "kept").mkdir()
    (day / "kept" / "input.png").write_bytes(b"x" * 10)
    real = Path.stat
    monkeypatch.setattr(Path, "stat", lambda self, **kw: (_ for _ in ()).throw(FileNotFoundError(self)) if self.name == "gone" else real(self, **kw))
    failures.prune(tmp_path)
    assert (day / "kept").exists()
