"""KCD 상병·EDI 수가 마스터 사전 조회.

``scripts/build_master.py``가 만든 ``data/master/*.csv``(code,name[,unit_price])를 지연 적재해,
코드가 마스터에 있는 행에 한해 명칭의 1글자 OCR 오인식(편축→편측, 부문→부분)을 되돌린다.
파일이 없으면 조용히 비활성이고, 명칭에서 코드를 역추론하지는 않는다 — 코드가 틀렸을 때
엉뚱한 명칭을 끼워 넣는 쪽이 미검출보다 나쁘다(harness-v2 Arbitration 원칙).
"""

import csv
import functools
import logging
import re

from backend import config

logger = logging.getLogger(__name__)

MAX_EDITS = 1  # 마스터 명칭과 어긋나도 되는 글자 수. 76건 평가에서 1이 최선(2는 순이득 -1)
EDI_MIN = 5  # 뒤에서 절단해 다시 찾을 때 남겨야 할 최소 길이(harness E4)
DRUG_LEN = 9  # 9자리 약가코드는 절단하지 않는다 — 다른 약에 잘못 붙는다
FILES = {"kcd": ("kcd.csv",), "edi": ("edi.csv", "drug.csv", "material.csv")}

_STRIP = re.compile(r"[\s\-_.]+")  # 코드 표기 차이
_LOOSE = re.compile(r"[\s\-_,()\[\]{}]")  # 명칭 표기 차이(고시는 하이픈, 인쇄물은 괄호)


def code(text) -> str | None:
    """조회용 코드 표기: 공백·하이픈·밑줄·점(KCD의 ``M81.99``)을 빼고 대문자로."""
    if not text:
        return None
    return _STRIP.sub("", str(text)).upper() or None


@functools.lru_cache(maxsize=1)
def _tables() -> dict[str, dict[str, list[str]]]:
    tables: dict[str, dict[str, list[str]]] = {}
    root = config.master_dir()
    for system, files in FILES.items():
        table: dict[str, list[str]] = {}
        for file_name in files:
            path = root / file_name
            if not path.is_file():
                continue
            with path.open(encoding="utf-8", newline="") as handle:
                for row in csv.DictReader(handle):
                    key, name = code(row.get("code")), (row.get("name") or "").strip()
                    if key and name and name not in table.setdefault(key, []):
                        table[key].append(name)
        if table:
            tables[system] = table
            logger.info("master: %s 코드 %d건 적재", system, len(table))
    return tables


def names(system: str, value) -> list[str]:
    """코드에 딸린 마스터 명칭들. EDI는 정확 일치가 없으면 뒤에서 한 자씩 줄여 다시 찾는다(harness E3·E4)."""
    table = _tables().get(system)
    key = code(value)
    if not table or not key:
        return []
    if key in table:
        return table[key]
    if system != "edi" or (len(key) == DRUG_LEN and key.isdigit()):
        return []
    for end in range(len(key) - 1, EDI_MIN - 1, -1):
        if key[:end] in table:
            return table[key[:end]]
    return []


def _letters(text: str) -> tuple[str, list[int]]:
    """비교용 글자열과 각 글자의 원문 위치. 띄어쓰기·괄호·하이픈은 표기 차이라 빼고 센다."""
    kept = [(index, char) for index, char in enumerate(text) if not _LOOSE.match(char)]
    return "".join(char.lower() for _, char in kept), [index for index, _ in kept]


def correct_name(system: str, value, name) -> str | None:
    """코드가 마스터에 있고 명칭이 마스터 명칭과 ``MAX_EDITS`` 글자만 다를 때, 그 글자만 고친 명칭.

    마스터 명칭을 통째로 쓰지는 않는다. 라벨도 정답도 문서에 인쇄된 표기인데 마스터는 고시 표기라
    띄어쓰기·괄호·어순이 달라, 통째로 갈아끼우면 맞던 칸까지 어긋난다(76건 평가에서 순손실 -13).
    글자 수가 같을 때만 보므로 낱말이 더 있거나 빠진 경우는 교정하지 않는다.
    """
    text = str(name or "").strip()
    given, positions = _letters(text)
    if not given:
        return None
    for candidate in names(system, value):
        other, other_positions = _letters(candidate)
        if len(other) != len(given):
            continue
        diff = [index for index, (a, b) in enumerate(zip(given, other)) if a != b]
        if not diff or len(diff) > MAX_EDITS:
            continue
        chars = list(text)
        for index in diff:
            chars[positions[index]] = candidate[other_positions[index]]
        return "".join(chars)
    return None


def ready() -> bool:
    return bool(_tables())
