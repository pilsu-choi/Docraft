"""근거 대기·재처리 CPU 경로의 기억·재사용이 결과를 바꾸지 않는다(2026-10-12 지연 최적화).

정규화는 글자만으로 정해지므로 기억해도 같아야 하고, 재처리는 같은 입력의 근거·룰·정규화를 다시 계산하지 않는다.
기준(reference)은 기억을 넣기 전 구현을 그대로 옮긴 것이다."""
import re
import time
import unicodedata

import pytest
from PIL import Image

from backend import doctypes, engine, reprocess, rules, typed_evidence, verify


def _plain(text):
    return re.sub(r"[^0-9A-Za-z가-힣]", "", text)


def _jamo(text):
    return unicodedata.normalize("NFD", text)


def reference_item(name):
    text = _plain(str(name or ""))
    if text in rules.PRINTED_ITEM_NAMES:
        return text
    bare = rules._alias(rules._ITEM_GROUP.sub("", text, count=1))
    name = rules._alias(text) if bare is None or _plain(bare) not in rules._PRINTED else bare
    name = rules._PRINTED.get(_plain(name or ""), name)
    if name in rules.RECEIPT_ITEM_NAMES or name is None or len(name) < 2:
        return name
    hits = [other for other in rules.RECEIPT_ITEM_NAMES
            if len(_plain(other)) == len(name) and rules._one_off(_jamo(_plain(other)), _jamo(name))
            or len(_plain(other)) >= 4 and rules._one_off(_plain(other), name)]
    return hits[0] if len(hits) == 1 else name


def reference_total(row):
    row = row or {}
    names = (row.get("항목"), None if row.get("EDI코드") or row.get("원내코드") else row.get("EDI명칭"))
    return next((standard for name in names if name for standard, pattern in rules._TOTAL_NAMES.items()
                 if pattern.fullmatch(re.sub(r"[\s:：()\[\]._|-]+", "", str(name)))), None)


def misreads(name):
    """OCR 오독 변형: 자모 하나 바꾸기·빼기, 글자 하나 빼기·더하기, 분류 칸 글자·공백·기호 붙이기."""
    spelled = _jamo(name)
    out = {name, f" {name} ", f"필{name}", f"선택항목_{name}", name.replace("료", "료 "), f"({name})", name + "1"}
    for index, char in enumerate(spelled):
        if "ᄀ" <= char <= "ᇿ":
            out.add(unicodedata.normalize("NFC", spelled[:index] + chr(ord(char) + 1) + spelled[index + 1:]))
            out.add(unicodedata.normalize("NFC", spelled[:index] + spelled[index + 1:]))
    for index in range(len(name)):
        out.update((name[:index] + name[index + 1:], name[:index] + "가" + name[index:]))
    return out


NAMES = sorted({variant for name in rules.RECEIPT_ITEM_NAMES for variant in misreads(name)})
ODD = [None, "", "-", 0, 12000, "12,000", "합 계", "총 합계", "소계", "Total", "끝수 처리 조정금액", "조정금액", "계",
       "진찰료 합계", "입원료 1인실", "CT 진단료", "MRI", "초음파진단료", "기타", ["진찰료"], 3.5]


@pytest.mark.parametrize("name", [*NAMES, *ODD], ids=repr)
def test_remembered_item_equals_reference(name):
    assert rules.item(name) == reference_item(name)
    assert rules.item(name) == reference_item(name)  # 두 번째(기억된) 결과도 같다


@pytest.mark.parametrize("row", [{"항목": name} for name in [*NAMES[::7], *ODD]]
                         + [{"EDI명칭": "합계"}, {"EDI명칭": "소 계", "EDI코드": "A1"}, {"항목": None, "EDI명칭": "총계"}, None],
                         ids=repr)
def test_remembered_total_label_equals_reference(row):
    assert rules.total_label(row) == reference_total(row)
    assert rules.total_label(row) == reference_total(row)


def reference_table_row(row, source_rows):
    name = row.get("항목") if isinstance(row, dict) else None
    if not name:
        return None
    total = reference_total({"항목": name}) is not None
    matches = [index for index, source in enumerate(source_rows)
               if (total and any(reference_total({"항목": cell}) is not None for cell in source)
                   or not total and any(reference_item(cell) == reference_item(name) for cell in source if cell))]
    return matches[0] if len(matches) == 1 else None


SOURCE = [["진찰료", "1,334", "12,006"], ["입원료", "", ""], ["진찰료 ", "0"], ["식데", "5,000"], ["합 계", "10"],
          ["", None], ["주사료", "주사료"], ["검사료"], ["소계", "합계"], ["필수항목", "투약및조제료"]]


@pytest.mark.parametrize("name", ["진찰료", "입원료", "식대", "식데", "합계", "소계", "주사료", "검사료", "투약및조제료",
                                  "영상진단료", None, "", "주시료"])
def test_table_row_from_names_read_once_equals_reference(name):
    row = {"항목": name}
    assert typed_evidence._table_row(row, typed_evidence._row_names(SOURCE)) == reference_table_row(row, SOURCE)


# --- 재처리: 같은 (값, 원 OCR)의 근거·룰·정규화는 한 번만 ---

SCHEMA = {"type": "object", "properties": {key: {"type": "string"} for key in ("a", "b", "c")}}
BLOCKS = [{"page": 1, "bbox": [0, 0, 10, 10], "page_size": [100, 100], "text": "a b c"}]


def stub_loop(monkeypatch, counts):
    monkeypatch.setenv("REPROCESS_ENABLED", "true")
    monkeypatch.setenv("REPROCESS_MAX_ATTEMPTS", "8")
    monkeypatch.setenv("REPROCESS_MAX_MODEL_CALLS", "0")
    monkeypatch.setenv("REPROCESS_MAX_MS", "10000")

    def ground(fields, _schema, _blocks):
        counts["ground"] = counts.get("ground", 0) + 1
        return {key: {"match": "none", "page": 1, "bbox": [0, 0, 10, 10], "page_size": [100, 100]} for key in fields}
    monkeypatch.setattr(reprocess.engine, "ground", ground)
    monkeypatch.setattr(reprocess.engine, "assess", lambda fields, _schema, _blocks, grounds: {
        key: {"status": "SUSPICIOUS", "issue_codes": [], "provenance": grounds[key]} for key in fields})
    monkeypatch.setattr(reprocess, "_crop", lambda *args: counts.__setitem__("crop", counts.get("crop", 0) + 1))

    def normalize(values, _evidence):
        counts["normalize"] = counts.get("normalize", 0) + 1
        values["a"] = "changed"  # 넘겨받은 값을 고쳐도 재처리의 fields가 오염되지 않아야 한다
        return {**values, "a": "x"}

    def check_rules(values, _evidence):
        counts["rules"] = counts.get("rules", 0) + 1
        return []
    return normalize, check_rules


def test_unchanged_targets_reuse_ground_rules_and_normalize(monkeypatch):
    counts = {}
    normalize, check_rules = stub_loop(monkeypatch, counts)
    fields, _, quality, summary = reprocess.run("scan.png", SCHEMA, BLOCKS, {"a": "x", "b": "y", "c": "z"},
                                                normalize=normalize, check_rules=check_rules,
                                                deadline=time.monotonic() + 3)  # 원격 단계는 열리지 않는다

    assert fields == {"a": "x", "b": "y", "c": "z"}
    assert [step["reason"] for step in summary["trace"] if step["stage"] == "rules"] == ["no_change"] * 3
    assert counts == {"ground": 1, "normalize": 1, "rules": 1}  # 기억 전에는 근거 4번·정규화 3번·룰 7번
    assert set(quality) == {"a", "b", "c"}


def test_roi_crop_is_cut_only_when_the_roi_stage_is_reached(monkeypatch):
    counts = {}
    normalize, check_rules = stub_loop(monkeypatch, counts)
    reprocess.run("scan.png", SCHEMA, BLOCKS, {"a": "x"}, normalize=normalize, check_rules=check_rules,
                  deadline=time.monotonic() + 3)
    assert "crop" not in counts  # 시한이 남은 단계보다 짧으면 페이지를 열어 잘라 내지 않는다

    monkeypatch.setattr(reprocess, "parse", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("down")))
    reprocess.run("scan.png", SCHEMA, BLOCKS, {"a": "x"}, normalize=normalize, check_rules=check_rules,
                  deadline=time.monotonic() + 60)
    assert counts["crop"] == 1


@pytest.mark.parametrize("guard", [False, True])
def test_cost_guard_skips_a_stage_longer_than_the_time_left(monkeypatch, guard):
    counts = {}
    _, check_rules = stub_loop(monkeypatch, counts)
    if guard:
        monkeypatch.setenv("REPROCESS_COST_GUARD", "true")

    def slow(values, _evidence):
        time.sleep(0.3)
        return values
    _, _, _, summary = reprocess.run("scan.png", SCHEMA, BLOCKS, {"a": "x", "b": "y"}, normalize=slow,
                                     check_rules=check_rules, deadline=time.monotonic() + 0.45)
    rules_steps = [step for step in summary["trace"] if step["stage"] == "rules"]
    assert len(rules_steps) == (1 if guard else 2)  # 기본(꺼짐)은 예전처럼 시작한다
    if guard:
        assert summary["stop_reason"] == "deadline"


# --- /api/read: 재처리를 건너뛴 읽기는 근거를 한 번만 댄다 ---

def test_read_without_reprocess_grounds_final_fields_once(monkeypatch, tmp_path):
    image = tmp_path / "scan.png"
    Image.new("RGB", (8, 8), "white").save(image)
    blocks = [{"type": "text", "page": 1, "bbox": [0, 0, 100, 20], "page_size": [200, 100], "text": "발행일 2026.10.12",
               "lines": [{"text": "발행일 2026.10.12", "bbox": [0, 0, 100, 20]}]}]
    monkeypatch.setattr(verify, "parse", lambda *args, **kwargs: ("md", blocks))
    monkeypatch.setattr(engine, "extract", lambda schema, blocks, source=None, **kwargs: ({"발행일": "2026.10.12"}, {}))
    calls = []
    real = engine.ground
    monkeypatch.setattr(engine, "ground", lambda *args: calls.append(args) or real(*args))

    _, fields, _, got, quality, _ = verify.read(str(image), "진료비영수증", {"발행일"}, with_groundings=True,
                                                with_reprocess=True, auto_reprocess=False)

    assert len(calls) == 1
    monkeypatch.setattr(engine, "ground", real)
    schema = verify._restrict(doctypes.schema("진료비영수증"), {"발행일"})
    assert quality == engine.assess(fields, schema, blocks)  # main.run_read가 따로 대던 품질 판정과 같다
    assert got["발행일"]["source_text"]
