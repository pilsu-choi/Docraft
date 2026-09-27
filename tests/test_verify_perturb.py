from pathlib import Path

from PIL import Image

from scripts.verify_perturb import make_variant


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
