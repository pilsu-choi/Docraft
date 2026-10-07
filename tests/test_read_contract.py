"""`/api/read` 재판독의 key·groundings 계약: 요청 key로 좁힌 스키마와 재처리 대상 field가 어긋나지 않는다.
DB 없이 돈다(`--noconftest`). 입력 key는 하네스가 실제로 보낸 평탄화 key(영수증 재판독 요청)다."""
import pytest
from PIL import Image

from backend import doctypes, engine, reprocess, rules, verify

TABLE = {"type": "object", "properties": {"행": {"type": "array", "items": {"type": "object", "properties": {"a": {"type": "string"}}}}}}
ROWS = [{"a": "x"}, {"a": "y"}, {"a": "y"}]  # 쪽이 바뀐 뒤 같은 행이 반복되는 경계
LEAF = {"confidence": 1, "bbox": [0, 0, 1, 1]}
PAGES = [1, 1, 2]
FORMS = {
    "queue": {"행": {str(i): {"a": {**LEAF, "page": page}} for i, page in enumerate(PAGES)}},  # 문서 큐: {"행 번호": {열: leaf}}
    "read": {"행": [{"a": {**LEAF, "page": page}} for page in PAGES]},  # /api/read 노출 형태: [{열: leaf}]
}


def flag_codes(groundings, rows=ROWS):
    return {(f["code"], tuple(f["rows"])) for f in engine.unit_flags({"행": rows}, TABLE, groundings, [{"type": "text", "page": 1, "text": "가"}])}


@pytest.mark.parametrize("form", FORMS)
def test_unit_flags_read_row_pages_from_either_grounding_form(form):
    assert flag_codes(FORMS[form]) == flag_codes(FORMS["queue"]) == {("boundary_repeat", (2,))}


@pytest.mark.parametrize("grounding", [[], [{}], None, {}, "", {"0": None}, [None, None]])
def test_unit_flags_tolerate_missing_or_short_row_groundings(grounding):
    assert flag_codes({"행": grounding}) == set()  # 근거가 없는 행은 쪽을 알 수 없으므로 경계 판정에서 빠진다


@pytest.fixture
def read_stub(monkeypatch, tmp_path):
    seen = {}
    image = tmp_path / "scan.png"
    Image.new("RGB", (8, 8), "white").save(image)
    monkeypatch.setattr(verify, "parse", lambda *args, **kwargs: ("md", [{"text": "x"}]))
    monkeypatch.setattr(engine, "extract", lambda schema, blocks, source=None, **kwargs: ({}, {}))
    monkeypatch.setattr(reprocess, "run", lambda image, schema, blocks, fields, **kwargs: (
        seen.update(schema=schema, fields=fields) or fields, {}, {}, None))
    return str(image), seen


HARNESS_KEYS = ["발행일", "의료기관정보-명칭", "의료기관정보-주소", "납부한금액_카드", "공단부담총액", "항목내역"]  # 영수증 재판독 요청의 실제 key(상한액초과금은 별칭이라 제외)


@pytest.mark.parametrize("doc_type", ["진료비영수증", "약제비영수증", "진단서"])
def test_read_hands_reprocess_only_requested_keys_in_the_narrowed_schema(read_stub, doc_type):
    image, seen = read_stub
    spec = doctypes.spec(doc_type)
    keys = HARNESS_KEYS if doc_type == "진료비영수증" else [*list(spec["fields"])[::3], *spec["tables"]]  # 그룹·최상위 필드와 표 key를 섞어 요청한다
    only = verify.resolve_keys(doc_type, keys)

    _, fields, *_ = verify.read(image, doc_type, only, with_groundings=True, with_reprocess=True)

    assert set(seen["schema"]["properties"]) == only
    assert set(seen["fields"]) == only  # 요청 밖 key가 재처리에 들어가 schema["properties"][root]가 KeyError 나지 않는다
    assert set(fields) == set(doctypes.spec(doc_type)["fields"]) | set(doctypes.spec(doc_type)["tables"])  # 읽기 결과(AO 비교용)는 전체 key를 유지한다


def test_reprocess_targets_of_a_narrowed_schema_resolve_in_it():
    schema = verify._restrict(doctypes.schema("진료비영수증"), {"공단부담총액", "의료기관정보-명칭"})
    fields = {key: value for key, value in rules.apply("진료비영수증", {}, []).items() if key in schema["properties"]}
    quality, _ = reprocess._quality(fields, schema, [])
    assert {path.split("/")[0] for path in quality} <= set(schema["properties"])
