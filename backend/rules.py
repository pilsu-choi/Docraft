"""twin reader 플러그인에서 이식한 룰 기반 정규화·추출·후처리.

- ``normalize(kind, value)``: 값 하나를 kind에 맞게 정규화한다(날짜 → YYYYMMDD, 금액 → 숫자 문자열 등).
  비교 가능한 정규형이 없으면 None을 돌려준다.
- ``apply(doc_type, result, blocks)``: ``engine.extract`` 결과(정규 표현, doctypes 참고)에
  파싱 블록(``parsers.parse``의 blocks)을 근거로 룰을 적용해 새 정규 표현을 돌려준다.
  값 정규화, 빠진 필드의 라벨 동의어 기반 보충, 파생 필드(성별·생년월일·사고발생일자 등),
  병명코드 분리, 체크박스 코드값 변환을 포함한다.
- ``same(kind, a, b)``: 두 값이 정규화 후 같은지.

룰은 데이터 테이블(``LABELS``·``FIELD_RULES``·``TOTALS``·doctypes.ENUMS)과 공통 엔진으로 나눠 둔다.
"""

import re
from datetime import date as _calendar_date

from . import doctypes
from .doctypes import DOC_TYPES, ENUMS

# ── 데이터 테이블 ────────────────────────────────────────────────────────────

OCR_DIGITS = str.maketrans({"I": "1", "l": "1", "|": "1", "/": "1", "O": "0", "o": "0",
                            "ㅇ": "0", "이": "0", "B": "8", "b": "6"})

LABELS = {  # 필드 → 라벨 동의어. 블록에서 빠진 값을 찾을 때 쓴다(twin reader keywordInfo + 서식 실물 라벨).
    "통원일수": ["통원일수", "방문일수", "실제내원일수", "외래일수", "통원치료일수", "실통원일수"],
    "진단일": ["진단일", "진단일자", "진단연월일", "진단년월일", "소견일", "4.진단일"],
    "진료과": ["진료과", "진료과목", "입원과", "과명", "진료센터(과)"],
    "입원일자": ["입원일", "입원일자", "입원연월일", "입원년월일", "입원기간", "입원치료기간", "입퇴원일"],
    "퇴원일자": ["퇴원일", "퇴원일자", "퇴원연월일", "퇴원년월일", "입퇴원일"],
    "통원일": ["통원일", "통원일자", "실통원일자", "실제내원일자", "외래진료일", "내원일", "통원기간"],
    "초진일": ["초진일", "초진일자", "초진연월일", "초진년월일", "발병일", "발병연월일", "수상일"],
    "발급일": ["발급일", "발행일", "발급일자", "발행일자", "발급연월일", "발행연월일", "작성일", "발급일시"],
    "병원명": ["의료기관명칭", "의료기관명", "요양기관명칭", "요양기관명", "병의원명칭", "병원명칭", "병원명", "기관명", "명칭"],
    "병원주소": ["주소", "소재지", "의료기관주소", "병의원주소", "사업장소재지"],
    "병원연락처": ["전화및FAX", "대표전화", "전화번호", "TEL", "Tel", "전화"],
    "면허번호": ["면허번호", "의사면허번호", "의사번호", "의사면허", "주치의면허번호"],
    "의사명": ["의사성명", "의사명", "담당의사", "주치의", "전문의", "한의사성명", "치과의사성명", "성명", "의사"],
    "환자 등록번호": ["환자등록번호", "등록번호", "환자번호", "병록번호", "병록번호", "고객번호", "환자ID"],
    "차트번호": ["차트번호", "챠트번호", "진료카드번호"],
    "이름": ["환자의성명", "환자성명", "환자명", "수진자성명", "수진자명", "성명", "이름"],
    "환자 주민번호": ["주민등록번호", "환자의주민등록번호", "주민번호", "환자의주민번호", "주민등록번호(수진자)"],
    "성별": ["성별", "나이/성별"],
    "생년월일": ["생년월일", "생일", "출생일", "출생년월일"],
    "주소": ["환자의주소", "환자주소", "수진자주소", "주소", "거주지"],
    "연락처": ["환자전화번호", "연락처", "전화번호", "휴대전화", "H/P", "전화"],
    "외래/입원": ["외래입원", "입원외래", "진료구분", "진료형태", "유형"],
    "공단부담총액": ["공단부담금", "공단부담액", "공단부담", "보험자부담금", "공단부담총액"],
    "상환액초과금": ["상한액초과금", "상한초과금", "상한초과", "본인부담상한액초과금", "상환액초과금"],
    "의료기관정보-명칭": ["요양기관명칭", "의료기관명칭", "의료기관명", "요양기관명", "병원명", "상호", "명칭"],
    "의료기관정보-사업자등록번호": ["사업자등록번호", "사업자번호", "사업장등록번호", "사업장번호"],
    "의료기관정보-요양기관종류": ["요양기관종류", "기관종류", "요양(의료)기관종류", "종별"],
    "의료기관정보-주소": ["사업장소재지", "사업장주소", "주소", "소재지"],
    "환자정보-성명": ["환자성명", "환자명", "수진자명", "성명", "이름"],
    "환자정보-진료과": ["진료과목", "진료과", "진료과/병실", "진료센터(과)"],
    "환자정보-질병군(DRG)번호": ["질병군(DRG)번호", "질병군번호", "DRG번호"],
    "환자정보-진료시작일": ["진료기간", "진료일자", "진료일", "진료일시", "진료기간(처방일)", "시작일", "진료개시일"],
    "환자정보-진료종료일": ["진료기간", "진료일자", "종료일", "진료종료일"],
    "환자정보-환자구분": ["환자구분", "환자유형", "보험구분", "보험유형", "구분"],
    "환자정보-환자등록번호": ["환자등록번호", "등록번호", "환자번호", "환자병록번호"],
    "납부한금액_카드": ["신용카드", "카드수납액", "카드총액", "카드"],
    "납부한금액_현금영수증": ["현금영수증", "현금영수증(소득공제)", "현금(현금영수증)"],
    "납부한금액_현금": ["현금(소득공제)", "현금수납액", "현금총액", "현금"],
    "납부한금액_합계": ["납부한금액", "납부금액", "수납금액", "영수액", "합계"],
    "납부할금액": ["납부할금액", "납부하실금액", "계산하실금액", "수납하실금액"],
    "이미납부한금액": ["이미납부한금액", "기납부금액", "기납부금", "기납입액", "먼저내신금액"],
    "진료비총액": ["진료비총액", "총진료비", "요양급여비용총액", "진료비액"],
    "환자부담총액": ["환자부담총액", "환자부담금총액", "환자부담액총액", "환자실부담액", "본인이부담할총액"],
    "환자정보(환자등록번호)": ["환자등록번호", "등록번호", "환자번호", "병록번호", "환자ID"],
    "환자성명": ["환자성명", "환자명", "수진자명", "성명", "환자이름"],
    "환자정보(진료시작일)": ["진료기간", "시작일", "진료일자", "집계기간", "입원일"],
    "환자정보(진료종료일)": ["진료기간", "종료일", "진료일자", "퇴원일"],
    "환자정보(병실)": ["병실", "병실번호", "병실호수", "병실구분", "병동-병실", "진료과병실"],
    "환자정보(입통원구분)": ["입통원구분", "입원외래구분", "진료구분", "유형"],
    "영수증진료형태(환자구분)": ["환자구분", "환자유형", "보험구분", "보험유형", "유형", "자격"],
    "급여_본인부담총액": ["본인부담금", "본인부담액", "급여본인", "일부본인부담금", "본인부담"],
    "급여_공단부담총액": ["공단부담금", "공단부담액", "급여공단", "보험자부담금", "공단부담"],
    "급여_전액본인부담총액": ["전액본인부담금", "전액본인부담", "전액본인", "전액부담"],
    "급여_급여총액": ["급여총액", "요양급여", "급여계", "급여합계", "급여"],
    "선택진료료총액": ["선택진료료", "선택진료", "지정진료비", "선택진료료총액"],
    "선택진료료외총액": ["선택진료료이외", "선택진료료외", "선택진료외", "선택진료료외총액"],
    "비급여총액": ["비급여", "비급여총액", "비급여계", "비급"],
}

TOTALS = {  # 표 합계행 → 합계 필드. 합계행은 표에서 빼고 비어 있는 필드만 채운다.
    "세부내역서": {"항목내역": {"본인부담": "급여_본인부담총액", "공단부담": "급여_공단부담총액",
                            "전액본인부담": "급여_전액본인부담총액", "급여": "급여_급여총액",
                            "선택진료료": "선택진료료총액", "선택진료료외": "선택진료료외총액",
                            "비급여": "비급여총액"}},
    "진료비영수증": {"항목내역": {"공단부담금": "공단부담총액"}},
}

_ACCIDENT_DATES = ("진단일",)  # 사고발생일자 후보(스칼라)
_ACCIDENT_COLUMNS = ("수술일자", "검사일", "치료일", "행위일")  # 사고발생일자 후보(표 열)

# ── 정규식 ──────────────────────────────────────────────────────────────────

_DATE = re.compile(
    r"(?<!\d)(\d{4})\s*[.\-/년]\s*(\d{1,2})\s*[.\-/월]\s*(\d{1,2})\s*일?"
    r"|(?<!\d)(\d{2})\s*[.\-/년]\s*(\d{1,2})\s*[.\-/월]\s*(\d{1,2})\s*일?"
    r"|(?<!\d)(\d{4})(\d{2})(\d{2})(?!\d)"
    r"|(?<!\d)(\d{2})(\d{2})(\d{2})(?!\d)")
_CODE = re.compile(r"[A-Za-z01][0-9]{2,5}(?:\.[0-9]{1,2})?")
_CODE_IN_TEXT = re.compile(r"[(\[{]?\s*[A-Za-z]\d{2,5}(?:\.\d{1,2})?\s*[)\]}]?")
_LICENSE = re.compile(r"\(?\s*(제)?\s*\d{4,6}\s*(호)?\s*\)?")
_NAME_WORDS = re.compile(r"의사|성명|이름|환자|면허|직인|서명|담당|주치의|전문의")
_PHONE_IN_TEXT = re.compile(r"\(?\d{2,4}\)?\s*-\s*\d{3,4}\s*-\s*\d{4}\)?")
_TOTAL_ROW = re.compile(r"^(합계|총계|소계|계|total|합계금액)$", re.I)
_TRUE = re.compile(r"^[\[(]?\s*(y|yes|o|v|1|true|예|체크|해당|√|✓|✔|☑|■|●)\s*[\])]?$|[✓✔√☑■●]|체크", re.I)
_WARD = re.compile(r"^(?=.*\d)[A-Za-z0-9/:\-]+호?$")
_EMPTY = ("", "[]", "{}", "none", "null", "nan", "-", "n/a")

# ── kind별 정규화 ───────────────────────────────────────────────────────────


def _calendar(parts):
    year, month, day = (int(part) for part in parts)
    if year < 100:
        year += 1900 if year >= 50 else 2000
    try:
        return f"{_calendar_date(year, month, day):%Y%m%d}"
    except ValueError:
        return None


def _dates_in(text):
    found = []
    for match in _DATE.finditer(text):
        value = _calendar([group for group in match.groups() if group is not None])
        if value and value not in found:
            found.append(value)
    return found


def _text(text):
    return re.sub(r"\s+", " ", text).strip() or None


def _date(text):
    return next(iter(_dates_in(text)), None)


def _dates(text):
    return ", ".join(_dates_in(text)) or None


def _amount(text):
    digits = re.sub(r"\D", "", text.translate(OCR_DIGITS))
    return (digits.lstrip("0") or "0") if digits else None


def _number(text):
    text = text.replace(",", ".")
    pair = re.search(r"(\d+(?:\.\d+)?)\s*[xX*×]\s*(\d+(?:\.\d+)?)", text)
    if pair:
        return _trim(float(pair[1]) * float(pair[2]))
    single = re.search(r"\d+(?:\.\d+)?", text)
    return _trim(float(single[0])) if single else None


def _trim(number):
    return f"{number:.4f}".rstrip("0").rstrip(".") or "0"


def _idnum(text):
    match = re.match(r"(\d{6})([\d*]{0,7})", re.sub(r"[^\d*]", "", text))
    return match[1] + ("-" + match[2] if match[2] else "") if match else None


def _phone(text):
    text = re.sub(r"[-/()]{0,2}\s*(fax|팩스).*", "", text, flags=re.I | re.S)
    digits = re.sub(r"-{2,}", "-", re.sub(r"[^\d-]+", "-", text)).strip("-")
    return digits if len(re.sub(r"\D", "", digits)) >= 7 else None


def _code(text):
    codes = []
    for token in _CODE.findall(text.replace(" ", "")):
        head = {"0": "D", "1": "I"}.get(token[0], token[0]).upper()
        code = head + token[1:]
        if head.isalpha() and code not in codes:
            codes.append(code)
    return ", ".join(codes) or None


def _bool(text):
    return "Y" if _TRUE.search(text.strip()) else "N"


def _enum_text(text):
    return re.sub(r"\s+", "", text) or None


_NORMALIZERS = {"text": _text, "date": _date, "dates": _dates, "amount": _amount, "number": _number,
                "idnum": _idnum, "phone": _phone, "code": _code, "bool": _bool, "enum": _enum_text}


def normalize(kind: str, value) -> str | None:
    if value is None:
        return None
    text = str(value).replace("[UNK]", " ").strip()
    if kind == "bool":
        return _bool(text)
    return None if text.lower() in _EMPTY else _NORMALIZERS.get(kind, _text)(text)


def same(kind: str, a, b) -> bool:
    left, right = normalize(kind, a), normalize(kind, b)
    if left is None or right is None:
        return left is None and right is None
    if kind == "dates":
        return set(left.split(", ")) == set(right.split(", "))
    if kind == "text":
        return re.sub(r"[\s\W_]+", "", left) == re.sub(r"[\s\W_]+", "", right)
    return left == right


# ── 필드별 정제 ─────────────────────────────────────────────────────────────


def _name(text):
    text = re.sub(r"[^가-힣]", "", _NAME_WORDS.sub(" ", _LICENSE.sub(" ", text)))
    half = len(text) // 2
    return (text[:half] if half and text[:half] == text[half:] else text) or None


def _hospital(text):
    text = re.sub(r"^\s*(명칭|의료기관명칭|의료기관명|요양기관명|병원명)\s*[:：]?\s*", "", text)
    text = re.sub(r"\(?\s*직인.*", "", text).replace("의과의원", "외과의원").strip()
    return re.sub(r"병$", "병원", text) or None


def _address(text):
    text = re.split(r"주\s*소\s*[:：]?", text)[-1]
    text = re.sub(r"(전화|연락처|tel|fax)\s*[:：]?.*", "", _PHONE_IN_TEXT.sub(" ", text), flags=re.I | re.S)
    return _text(_DATE.sub(" ", text))


FIELD_RULES = {  # 필드 → 추가 정제(정규화 뒤에 적용)
    **dict.fromkeys(["이름", "의사명", "환자정보-성명", "환자성명"], _name),
    **dict.fromkeys(["병원명", "의료기관정보-명칭"], _hospital),
    **dict.fromkeys(["주소", "병원주소", "의료기관정보-주소"], _address),
}


def _enum(key, text):
    """정규값 목록이 있는 필드는 동의어를 정규값으로 바꾸고, 어디에도 맞지 않으면 버린다."""
    table = ENUMS.get(key)
    if not table or text is None:
        return text
    lowered = text.lower()
    for canonical, words in table.items():
        if lowered == canonical.lower() or any(word == lowered or (len(word) > 1 and word in lowered) for word in words):
            return canonical
    return None


def _value(doc_type, key, value, table=None):
    kind = doctypes.kind(doc_type, key, table)
    text = normalize(kind, value)
    rule = FIELD_RULES.get(key)
    if text is not None and rule:
        text = rule(text)
    return _enum(key, text) if kind == "enum" else text


# ── 블록에서 라벨로 값 찾기 ─────────────────────────────────────────────────


def _key(text):
    return re.sub(r"[\s:：()\[\]._-]+", "", str(text))


def _matches(cell, labels):
    cell = _key(cell)
    return bool(cell) and any(cell == label or (cell.startswith(label) and len(cell) <= len(label) + 2) for label in labels)


def _candidates(labels, blocks):
    """라벨 오른쪽 셀(표)과 ``라벨: 값`` 패턴(텍스트)에서 값 후보를 순서대로 낸다."""
    keys = [_key(label) for label in labels]
    patterns = [re.compile(r"\s*".join(map(re.escape, label)) + r"\s*[:：]?\s*([^\n|]{1,60})") for label in labels]
    for block in blocks:
        for row in block.get("rows") or []:
            for index, cell in enumerate(row):
                if _matches(cell, keys):
                    yield from (other for other in row[index + 1:] if str(other or "").strip())
        text = block.get("text") or ""
        for line in [*(line["text"] for line in block.get("lines") or []), *text.split("\n")]:
            for pattern in patterns:
                match = pattern.search(line)
                if match:
                    yield match[1]


def _fill(doc_type, out, blocks):
    for key, value in out.items():
        if value is not None or key not in LABELS:
            continue
        for candidate in _candidates(LABELS[key], blocks):
            filled = _value(doc_type, key, candidate)
            if filled:
                out[key] = filled
                break


# ── 표·파생 필드 후처리 ─────────────────────────────────────────────────────


def _split_codes(out):
    """병명 칸에 섞인 병명코드를 분리하고 병명에서 코드 잔재를 지운다."""
    for row in out.get("병명내역") or []:
        name = row.get("병명")
        if not name:
            continue
        row["병명코드"] = row.get("병명코드") or normalize("code", name)
        row["병명"] = normalize("text", _CODE_IN_TEXT.sub(" ", name))


def _totals(doc_type, out):
    for table, mapping in TOTALS.get(doc_type, {}).items():
        kept = []
        for row in out.get(table) or []:
            if not _TOTAL_ROW.match(_key(row.get("항목") or "")):
                kept.append(row)
                continue
            for column, field in mapping.items():
                if field in out and not out[field] and row.get(column):
                    out[field] = row[column]
        out[table] = kept


def _derive(doc_type, out):
    fields = DOC_TYPES.get(doc_type, {}).get("fields", {})
    idnum = next((out[key] for key, meta in fields.items() if meta["kind"] == "idnum" and out.get(key)), None)
    back = idnum.partition("-")[2][:1] if idnum else ""
    if back in "123456" and "성별" in fields and not out.get("성별"):
        out["성별"] = "남" if back in "135" else "여"
    if back and "생년월일" in fields and not out.get("생년월일"):
        century = "20" if back in "3478" else "19" if back in "1256" else ""
        out["생년월일"] = normalize("date", century + idnum[:6])
    if "외래/입원" in fields and not out.get("외래/입원"):
        out["외래/입원"] = _enum("외래/입원", out.get("환자정보-환자구분") or "") or None
    room = out.get("환자정보(병실)") or ""
    if "환자정보(입통원구분)" in fields and not out.get("환자정보(입통원구분)") and room:
        out["환자정보(입통원구분)"] = "통원" if "외래" in room else "입원" if _WARD.match(room.replace(" ", "")) or "입원" in room else None
    if "사고발생일자" in fields and not out.get("사고발생일자"):
        start = next((out[key] for key in out if "진료시작일" in key and out.get(key)), None)
        out["사고발생일자"] = start or _earliest(out)


def _earliest(out):
    dates = [out[key] for key in _ACCIDENT_DATES if out.get(key)]
    dates += [row[column] for rows in out.values() if isinstance(rows, list)
              for row in rows for column in _ACCIDENT_COLUMNS if row.get(column)]
    return min(dates, default=None)


def apply(doc_type: str, result: dict, blocks: list[dict]) -> dict:
    spec = DOC_TYPES.get(doc_type, {"fields": {}, "tables": {}})
    result = result or {}
    out = {key: _value(doc_type, key, result.get(key)) for key in spec["fields"]}
    for table, columns in spec["tables"].items():
        rows = [row for row in (result.get(table) or []) if isinstance(row, dict)]
        out[table] = [{column: _value(doc_type, column, row.get(column), table) for column in columns} for row in rows]
    _fill(doc_type, out, blocks or [])
    _split_codes(out)
    _totals(doc_type, out)
    _derive(doc_type, out)
    return out
