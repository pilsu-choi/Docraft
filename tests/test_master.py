"""마스터 사전 조회·명칭 교정. 작은 fixture CSV만 쓰고 data/master에는 손대지 않는다."""

from pathlib import Path

import pytest

from backend import master, rules

FIXTURE = Path(__file__).parent / "master_fixture"


@pytest.fixture
def loaded(monkeypatch):
    monkeypatch.setenv("MASTER_DIR", str(FIXTURE))
    master._tables.cache_clear()
    yield master
    master._tables.cache_clear()


@pytest.fixture
def missing(monkeypatch, tmp_path):
    monkeypatch.setenv("MASTER_DIR", str(tmp_path / "nowhere"))
    master._tables.cache_clear()
    yield master
    master._tables.cache_clear()


# ── 조회 ────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw, expected", [
    ("M81.99", "M8199"), (" m81-99 ", "M8199"), ("kk054", "KK054"), ("", None), (None, None),
])
def test_code_normalizes(raw, expected):
    assert master.code(raw) == expected


def test_names_exact_and_dotted(loaded):
    assert loaded.names("kcd", "M8199") == ["상세불명의 골다공증, 상세불명 부분"]
    assert loaded.names("kcd", "M81.99") == loaded.names("kcd", "M8199")
    assert loaded.names("edi", "E6660") == ["정밀안저검사[편측]"]


def test_names_truncates_edi_but_not_drug_code(loaded):
    assert loaded.names("edi", "KK054000") == ["수액제주입로를통한주사"]  # 뒤에서 절단해 재조회
    assert loaded.names("edi", "KK05") == []  # 최소 5자 미만은 절단하지 않는다
    assert loaded.names("edi", "642902710") == ["세타마돌정_(1정)"]  # 9자리 약가코드는 정확 일치만
    assert loaded.names("edi", "642902719") == []


def test_disabled_without_files(missing):
    assert missing.ready() is False
    assert missing.names("kcd", "M8199") == []
    assert missing.correct_name("kcd", "M8199", "상세불명의 골다공증, 상세불명 부문") is None


# ── 명칭 교정 ───────────────────────────────────────────────────────────────

def test_corrects_one_character_and_keeps_printed_spacing(loaded):
    assert loaded.correct_name("kcd", "M81.99", "상세불명의 골다공증, 상세불명 부문") == "상세불명의 골다공증, 상세불명 부분"
    # 마스터는 붙여 쓰지만 인쇄 표기의 띄어쓰기는 그대로 둔다
    assert loaded.correct_name("edi", "KK054", "수액제 주입로를 통한 추사") == "수액제 주입로를 통한 주사"


@pytest.mark.parametrize("system, code, name", [
    ("kcd", "Z999", "있지도 않은 병명"),                      # 코드가 마스터에 없다
    ("kcd", "M81.99", "상세불명의 골다공증, 상세불명 부분"),      # 이미 같다
    ("kcd", "J209", "상세불명의 기관지염"),                     # 글자 수가 다르다(낱말 누락)
    ("kcd", "S92240", "발의 쐬기뼈의 괄절, 폐쇄성"),            # 두 글자 차이는 임계값 밖
    ("kcd", "M81.99", None),
    ("kcd", None, "상세불명의 골다공증, 상세불명 부문"),          # 코드가 없으면 역추론하지 않는다
])
def test_leaves_uncertain_names_alone(loaded, system, code, name):
    assert loaded.correct_name(system, code, name) is None


def test_threshold_boundary_is_max_edits(loaded, monkeypatch):
    two_off = "발의 쐬기뼈의 괄절, 폐쇄성"
    monkeypatch.setattr(master, "MAX_EDITS", 2)
    assert loaded.correct_name("kcd", "S92240", two_off) == "발의 쐐기뼈의 골절, 폐쇄성"


# ── rules 통합 ──────────────────────────────────────────────────────────────

def test_apply_corrects_code_matched_names(loaded):
    result = {"병명내역": [{"병명코드": "M81.99", "병명": "상세불명의 골다공증, 상세불명 부문"},
                        {"병명코드": "Z999", "병명": "마스터에 없는 코드라 그대로 둔다"}]}
    out = rules.apply("진단서", result, [])
    assert [row["병명"] for row in out["병명내역"]] == ["상세불명의 골다공증, 상세불명 부분",
                                                   "마스터에 없는 코드라 그대로 둔다"]
    assert [flag["code"] for flag in rules.check("진단서", out, {}, [])] == ["code_unknown"]
