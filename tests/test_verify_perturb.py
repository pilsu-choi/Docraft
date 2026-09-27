import json
import sys
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from scripts import verify_eval, verify_perturb
from scripts.verify_perturb import counts, make_variant


def test_make_variant_writes_copy_and_preserves_source(tmp_path: Path):
    source = tmp_path / "source.png"
    image = Image.new("RGB", (80, 60), "white")
    image.putpixel((40, 30), (0, 0, 0))
    image.save(source)
    original = source.read_bytes()

    outputs = {name: tmp_path / f"{name}.tif" for name in ("rotate", "blur", "occlude")}
    for name, target in outputs.items():
        make_variant(source, target, name)

    assert source.read_bytes() == original
    assert all(path.is_file() for path in outputs.values())
    with Image.open(outputs["rotate"]) as rotated, Image.open(outputs["blur"]) as blurred:
        assert rotated.size[0] > 80 and rotated.size[1] > 60
        assert blurred.size == (80, 60)


def test_make_variant_rejects_unknown_transform(tmp_path: Path):
    source = tmp_path / "source.png"
    Image.new("RGB", (10, 10), "white").save(source)

    try:
        make_variant(source, tmp_path / "bad.tif", "noise")
    except ValueError as exc:
        assert "지원하지 않는 변형" in str(exc)
    else:
        raise AssertionError("unknown perturbation should fail")


def test_failed_document_keeps_legible_truth_in_denominator(tmp_path: Path):
    label = tmp_path / "label.json"
    label.write_text(json.dumps({"fields": {"name": "A", "empty": None,
                              "table": [{"code": "K1", "blurred": "?"}]},
                                 "provenance": {"unknown_fields": ["table.0.blurred"]}}))
    result = counts([{"label": str(label), "stages": {"raw": {"error": "parse failed"}}}], "raw")
    assert result["documents"] == 1
    assert result["evaluated"] == 0
    assert result["errors"] == 1
    assert result["error_truth_fields"] == 2
    assert result["total_including_errors"] == result["strict_total_including_errors"] == 2


def test_repeat_run_uses_private_unique_output_and_content_cache(monkeypatch, tmp_path: Path):
    images = []
    items = []
    for index in range(4):
        image = tmp_path / f"source-{index}.png"
        Image.new("RGB", (20, 20), "white").save(image)
        label = tmp_path / f"label-{index}.json"
        label.write_text(json.dumps({"doc_type": "진단서", "image": str(image), "grade": "gold",
                                     "fields": {"name": "A"}}))
        images.append(image)
        items.append({"doc_type": "진단서", "grade": "gold", "image": str(image), "label": str(label)})
    source_manifest = tmp_path / "source-manifest.json"
    source_manifest.write_text(json.dumps({"items": items}))
    output = tmp_path / "review"
    commands = []

    def fake_run(command, **_kwargs):
        commands.append(command)
        run_root = Path(command[command.index("--output-root") + 1])
        generated = json.loads((output / "manifest.json").read_text())["items"]
        entries = [{"image": Path(item["image"]).name, "label": item["label"],
                    "stages": {stage: {"correct": 1, "total": 1, "fp": 0,
                                       "strict_correct": 1, "strict_total": 1, "strict_fp": 0}
                               for stage in ("raw", "rules")}} for item in generated]
        (run_root / "eval-fake.json").write_text(json.dumps({"items": entries}))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(verify_perturb.subprocess, "run", fake_run)
    monkeypatch.setattr(verify_perturb, "code_fingerprint", lambda: {"head": "test", "source_sha256": "test"})
    monkeypatch.setattr(verify_perturb, "quality_counts", lambda *_: {"status": {}, "documents": 0})
    for _ in range(2):
        monkeypatch.setattr(sys, "argv", ["verify_perturb", "--manifest", str(source_manifest),
                                       "--output-root", str(output)])
        assert verify_perturb.main() == 0
    assert commands[0][commands[0].index("--cache-root") + 1] == commands[1][commands[1].index("--cache-root") + 1]
    assert commands[0][commands[0].index("--output-root") + 1] != commands[1][commands[1].index("--output-root") + 1]
    assert all(Path(c[c.index("--output-root") + 1]).is_relative_to(output) for c in commands)

    Image.new("RGB", (20, 20), "black").save(images[0])
    assert verify_perturb.main() == 0
    assert commands[2][commands[2].index("--cache-root") + 1] != commands[1][commands[1].index("--cache-root") + 1]


def test_verify_eval_writes_to_requested_private_output(monkeypatch, tmp_path: Path):
    image = tmp_path / "sample.png"
    Image.new("RGB", (10, 10), "white").save(image)
    labels = tmp_path / "labels" / "진단서"
    labels.mkdir(parents=True)
    label = labels / "sample.json"
    label.write_text(json.dumps({"doc_type": "진단서", "image": str(image),
                                 "grade": "silver", "fields": {"병원명": "A"}}))
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"label_root": str(labels.parent),
                                    "items": [{"doc_type": "진단서", "image": str(image)}]}))
    output = tmp_path / "private-results"
    monkeypatch.setattr(sys, "argv", ["verify_eval", "--manifest", str(manifest), "--stage", "raw",
                                   "--output-root", str(output)])
    monkeypatch.setattr(verify_eval, "process_item", lambda item, *_: {
        "doc_type": item.doc_type, "grade": item.grade, "image": item.image_path.name,
        "label": str(item.label_path), "split": None, "stages": {"raw": {
            "correct": 1, "total": 1, "fp": 0, "strict_correct": 1, "strict_total": 1,
            "strict_fp": 0, "rows": []}}, "errors": {}})
    verify_eval.main()
    generated = list(output.glob("eval-*.json"))
    assert len(generated) == 1
    assert json.loads(generated[0].read_text())["args"]["output_root"] == str(output)
