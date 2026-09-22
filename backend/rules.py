"""twin reader 플러그인에서 이식한 룰 기반 정규화·추출·후처리.

- ``normalize(kind, value)``: 값 하나를 kind에 맞게 정규화한다(날짜 → YYYYMMDD, 금액 → 숫자 문자열 등).
  비교 가능한 정규형이 없으면 None을 돌려준다.
- ``apply(doc_type, result, blocks)``: ``engine.extract`` 결과(정규 표현, doctypes 참고)에
  파싱 블록(``parsers.parse``의 blocks)을 근거로 룰을 적용해 새 정규 표현을 돌려준다.
  값 정규화, 값 자리에 들어온 서식 라벨·표 마크업 제거, 빠진 필드의 라벨 동의어 기반 보충,
  소견 문장에서 치료·검사 내역 행 만들기, 병명코드 분리, 합계행 정리, 묶음 제목 금액 열 비우기,
  ``derive``의 관례 채우기를 차례로 한다.
- ``derive(doc_type, fields)``: 읽은 값에서 채울 수 있는 자리를 AO 관례대로 채운다(성별·생년월일,
  진료비영수증 항목명 정규화, 세부내역서 코드 열·급여 칸·종료일자, 사고발생일자).
  정답셋 라벨도 같은 관례를 쓰도록 ``scripts/verify_label.conform``이 이 함수를 그대로 쓴다.
- ``same(kind, a, b)``: 두 값이 정규화 후 같은지(금액의 빈 칸·0, 텍스트의 접두·접미 차이는 같게 본다).
- ``pair_rows(doc_type, table, left, right)``: 두 표의 행을 키 열(``ROW_KEYS``)로 대응시킨다. 행 순서·개수가
  달라도 같은 행끼리 맞물리게 하며, ``is_total(row)``은 그중 합계·소계 행을 가린다. 교차검증
  (``verify._row_diff``)과 채점(``scripts/verify_eval``)이 같은 규칙을 쓰도록 여기 한 곳에 둔다.
- ``check(doc_type, ao, docraft, blocks)``: 진료비영수증 항목내역의 이상 징후 목록(금액 겹침·없는 열·
  합계 베끼기·합계 불일치·행 누락). 다른 유형은 빈 목록이다.
- ``correct(doc_type, checks, ao, docraft)``: 그중 확실한 이상을 Judge 없이 바로 교정한다.

룰은 데이터 테이블(``LABELS``·``FIELD_RULES``·``TOTALS``·doctypes.ENUMS)과 공통 엔진으로 나눠 둔다.
"""

import re
from datetime import date as _calendar_date

from . import doctypes
from .doctypes import ENUMS

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
    "초진일": ["초진일", "초진일자", "초진연월일", "초진년월일", "최초진료일", "최초내원일"],
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

DISTINCT = {"주소": "병원주소", "연락처": "병원연락처"}  # 환자 칸에 병원 값이(그 반대도) 흘러들지 않게 할 짝
DISTINCT.update({hospital: patient for patient, hospital in DISTINCT.items()})

TOTALS = {  # 표 합계행 → 합계 필드. 합계행은 표에서 빼고 비어 있는 필드만 채운다.
    "세부내역서": {"항목내역": {"본인부담": "급여_본인부담총액", "공단부담": "급여_공단부담총액",
                            "전액본인부담": "급여_전액본인부담총액", "급여": "급여_급여총액",
                            "선택진료료": "선택진료료총액", "선택진료료외": "선택진료료외총액",
                            "비급여": "비급여총액"}},
    "진료비영수증": {"항목내역": {"공단부담금": "공단부담총액"}},
}
KEEP_TOTALS = {"진료비영수증"}  # AO 스키마가 합계 행을 표에 두는 유형. 합계 필드를 채운 뒤에도 행을 남긴다.

ROW_KEYS = {  # 표 → 행을 식별하는 열. 두 표의 행을 짝지을 때 쓴다(``pair_rows``). 스키마에 없는 열은 건너뛴다.
    "항목내역": ("항목", "EDI코드", "시작일자"),
    "병명내역": ("병명코드",),
    "수술내역": ("수술일자",),
    "검사내역": ("검사일",),
    "치료내역": ("치료일",),
    "행위내역": ("행위일",),
}

_ACCIDENT_DATES = ("진단일",)  # 사고발생일자 후보(스칼라)
_ACCIDENT_COLUMNS = ("수술일자", "검사일", "치료일", "행위일")  # 사고발생일자 후보(표 열)

NOTES = {  # 표 → (소견 문장을 담은 칸의 라벨, 날짜 열, 이름 열). 전용 표가 없는 서식에서 행을 만든다.
    "치료내역": (["치료소견", "치료내용", "치료내용및향후치료에대한소견", "향후치료의견", "향후치료계획",
                "치료및향후치료의견", "향후치료에대한소견", "내용"], "치료일", "치료명"),
    "검사내역": (["검사소견", "검사결과", "검사내용"], "검사일", "검사명"),
    "수술내역": (["수술소견", "수술내용"], "수술일자", "수술명"),
}
MARKS = {"검사": "검사내역", "수술": "수술내역", "치료": "치료내역"}  # 비고의 ``날짜 (검사)`` 표시 → 표
SENTENCE = 10  # 소견 문장으로 볼 최소 길이

# 값이 아니라 서식의 라벨 글자가 흘러든 것을 가려낼 낱말. LABELS·doctypes 키에 서식 상용어를 더한다.
_FORM_WORDS = ("의", "제", "호", "및", "성", "명", "세", "연령", "만", "년", "월", "일", "구분", "번호",
               "내용", "기타", "원본대조필인", "원본대조필", "상기", "위와같이", "비고",
               "영수증번호", "일련번호", "연월", "야간", "공휴일", "종류")

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
_TOTAL_ROW = re.compile(r"^(합계|총계|소계|계|total|합계금액|끝수처리조정금액?)$", re.I)
_TRUE = re.compile(r"^[\[(]?\s*(y|yes|o|v|1|true|예|체크|해당|√|✓|✔|☑|■|●)\s*[\])]?$|[✓✔√☑■●]|체크", re.I)
_WARD = re.compile(r"^(?=.*\d)[A-Za-z0-9/:\-]+호?$")
_EMPTY = ("", "[]", "{}", "none", "null", "nan", "-", "n/a")
_WORD = re.compile(r"[0-9A-Za-z가-힣]")
_HTML = re.compile(r"</?(?:t[dhr]|table|br|p)\b", re.I)
_MARKED_DATE = re.compile(r"(\d{4}\s*[./-]\s*\d{1,2}\s*[./-]\s*\d{1,2})\s*[(\[]\s*(" + "|".join(MARKS) + r")\s*[)\]]")
_EDI_CODE = re.compile(r"^([A-Za-z]{0,3})([0-9A-Za-z]{2,})$")
_EDI_DIGITS = str.maketrans({"O": "0", "I": "1", "L": "1", "S": "5", "B": "8"})

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
    text = re.sub(r"\s+", " ", text).strip()
    return text if _WORD.search(text) else None  # 구두점·기호만 남은 칸은 값이 아니다


def _date(text):
    return next(iter(_dates_in(text)), None)


def _dates(text):
    return ", ".join(_dates_in(text)) or None


def _amount(text):
    digits = re.sub(r"\D", "", text.translate(OCR_DIGITS))
    return (digits.lstrip("0") or "0") if digits else None


def _number(text):
    text = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", text).replace(",", ".")  # 천 단위 콤마는 빼고, 남은 콤마는 소수점
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
        code = head + token[1:].replace(".", "")
        if head.isalpha() and code not in codes:
            codes.append(code)
    return ", ".join(codes) or None


def _edi(text):
    """EDI·원내 코드: 공백·구분기호를 빼고 대문자로, 숫자부의 흔한 오인식(O·I·L·S·B)을 숫자로 돌린다."""
    text = re.sub(r"[\s.\-_{}()\[\]]+", "", text).upper()
    match = _EDI_CODE.match(text)
    if not match:
        return _text(text)
    head, tail = match[1], match[2]
    return head + (tail.translate(_EDI_DIGITS) if set(tail) <= set("0123456789OILSB") else tail)


def _bool(text):
    return "Y" if _TRUE.search(text.strip()) else "N"


def _enum_text(text):
    return re.sub(r"\s+", "", text) or None


_NORMALIZERS = {"text": _text, "date": _date, "dates": _dates, "amount": _amount, "number": _number,
                "idnum": _idnum, "phone": _phone, "code": _code, "edi": _edi, "bool": _bool, "enum": _enum_text}


def normalize(kind: str, value) -> str | None:
    if value is None:
        return None
    text = str(value).replace("[UNK]", " ").strip()
    if kind == "bool":
        return _bool(text)
    return None if text.lower() in _EMPTY else _NORMALIZERS.get(kind, _text)(text)


def same(kind: str, a, b) -> bool:
    """두 값이 정규화 후 같은지.

    표기 차이를 같게 보도록 느슨하게 판정한다: 금액·수량은 빈 칸과 0을 같게 보고(빈 금액 칸은 0이다),
    텍스트는 한쪽이 다른 쪽을 통째로 품고 있으면 같게 본다('(주상병)이상체중감소'와 '이상체중감소').
    다만 짧은 쪽이 네 글자는 되어야 한다 — '외과'는 '정형외과'와 다른 값이다.
    """
    left, right = normalize(kind, a), normalize(kind, b)
    if kind in ("amount", "number"):
        left, right = left or "0", right or "0"
    if left is None or right is None:
        return left is None and right is None
    if kind == "dates":
        return set(left.split(", ")) == set(right.split(", "))
    if kind == "text":
        short, long = sorted((re.sub(r"[\s\W_]+", "", value) for value in (left, right)), key=len)
        return short == long or (len(short) >= 4 and short in long)
    return left == right


def _prefix_same(kind, a, b):
    """짝짓기 전용 느슨한 비교: 한쪽이 다른 쪽의 접두면 같은 행으로 본다('주사료' ⊂ '주사료_행위료')."""
    if kind not in ("text", "edi") or a in (None, "") or b in (None, ""):
        return same(kind, a, b)
    short, long = sorted((re.sub(r"[\s\W_]+", "", str(value)) for value in (a, b)), key=len)
    return len(short) >= 2 and long.startswith(short)


def pair_rows(doc_type: str, table: str, left: list, right: list, columns=None,
              fallback: bool = True) -> list[tuple[dict | None, dict | None]]:
    """두 표의 행을 ``ROW_KEYS``의 키 열로 짝짓는다.

    값이 같은 행부터 짝짓고, 남은 행은 키 열의 접두가 같은 행에 붙이고(``주사료`` ⊂ ``주사료_행위료``),
    ``fallback``이면 그래도 남은 행끼리 순서대로 잇는다. 끝내 짝이 없는 행은 상대가 ``None``인
    쌍(누락·과잉)으로 남는다. 왼쪽 행 순서는 그대로 지킨다.
    """
    keys = [column for column in ROW_KEYS.get(table, ())
            if column in (columns if columns is not None else doctypes.spec(doc_type)["tables"].get(table, ()))]
    kinds = {column: doctypes.kind(doc_type, column, table) for column in keys}
    taken, matched = set(), [None] * len(left)
    for match in (same, _prefix_same):  # 값이 같은 행부터, 남은 행은 접두가 같은 행에
        for index, row in enumerate(left):
            if matched[index] is not None or not any(row.get(column) not in (None, "") for column in keys):
                continue
            hit = next((other for other, mate in enumerate(right) if other not in taken
                        and all(match(kinds[column], row.get(column), mate.get(column)) for column in keys)), None)
            if hit is not None:
                taken.add(hit)
                matched[index] = hit
    spare = iter([index for index in range(len(right)) if index not in taken])
    pairs = []
    for index, hit in enumerate(matched):
        if hit is None and fallback:
            hit = next(spare, None)
        pairs.append((left[index], right[hit] if hit is not None else None))
    return pairs + [(None, right[index]) for index in spare]


# ── 필드별 정제 ─────────────────────────────────────────────────────────────


def _name(text):
    text = re.sub(r"[^가-힣]", "", _NAME_WORDS.sub(" ", _LICENSE.sub(" ", text)))
    half = len(text) // 2
    text = text[:half] if half and text[:half] == text[half:] else text
    return text if 2 <= len(text) <= 5 else None  # 사람 이름 길이를 벗어나면 라벨 글자가 섞인 것이다


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


def _key(text):
    return re.sub(r"[\s:：()\[\]._-]+", "", str(text))


_LABEL_WORDS = frozenset(  # 값 자리에 들어온 서식 라벨을 가려낼 낱말 모음
    _key(word) for word in (*_FORM_WORDS, *(word for words in LABELS.values() for word in words),
                            *(key for spec in doctypes.DOC_TYPES.values() for key in
                              (*spec["fields"], *spec["tables"],
                               *(column for columns in spec["tables"].values() for column in columns))))
)


def _junk(value) -> bool:
    """값이 아니라 서식의 라벨 글자나 표 마크업이 흘러든 것인지('성별', '질병군(DRG)번호', '</td><td>')."""
    rest = _key(value)
    if _HTML.search(str(value)):
        return True
    while rest:
        word = max((word for word in _LABEL_WORDS if word and rest.startswith(word)), key=len, default=None)
        if not word:
            return False
        rest = rest[len(word):]
    return True


def _enum(key, text):
    """정규값 목록이 있는 필드는 동의어를 정규값으로 바꾸고, 어디에도 맞지 않으면 버린다.

    서식에 인쇄된 보기('남 여')처럼 정규값 둘이 똑같은 근거로 걸리면 고르지 않는다. 한쪽 동의어가
    다른 쪽을 품는 관계('비급여'⊃'급여')는 더 긴 쪽이 이긴다.
    """
    table = ENUMS.get(key)
    if not table or text is None:
        return text
    lowered = text.lower()
    hits = {}
    for canonical, words in table.items():
        found = [word for word in (canonical.lower(), *words)
                 if word == lowered or (len(word) > 1 and word in lowered)]
        if found:
            hits[canonical] = max(map(len, found))
    best = max(hits.values(), default=0)
    winners = [canonical for canonical, length in hits.items() if length == best]
    return winners[0] if len(winners) == 1 else None


def _value(doc_type, key, value, table=None):
    kind = doctypes.kind(doc_type, key, table)
    text = normalize(kind, value)
    if text is not None and kind != "bool" and table is None and _junk(value):
        return None
    rule = FIELD_RULES.get(key)
    if text is not None and rule:
        text = rule(text)
    return _enum(key, text) if kind == "enum" else text


# ── 블록에서 라벨로 값 찾기 ─────────────────────────────────────────────────


def _matches(cell, labels):
    cell = _key(cell)
    return bool(cell) and any(cell == label or (cell.startswith(label) and len(cell) <= len(label) + 2) for label in labels)


def _lines(blocks):
    """블록의 텍스트 줄 전부(줄 목록과 text 모두)."""
    for block in blocks:
        yield from (line["text"] for line in block.get("lines") or [])
        yield from (block.get("text") or "").split("\n")


def _candidates(labels, blocks):
    """라벨 오른쪽 셀(표)과 ``라벨: 값`` 패턴(텍스트)에서 값 후보를 순서대로 낸다."""
    keys = [_key(label) for label in labels]
    # 라벨이 다른 낱말 꼬리에 걸리지 않게 앞 글자를 막는다('환자성명'의 '성명'은 의사명 라벨이 아니다).
    patterns = [re.compile(r"(?<![가-힣A-Za-z0-9])" + r"\s*".join(map(re.escape, label))
                           + r"(?![가-힣])\s*[:：]?\s*([^\n|]{1,60})") for label in labels]
    for block in blocks:
        for row in block.get("rows") or []:
            for index, cell in enumerate(row):
                if _matches(cell, keys):
                    yield from (other for other in row[index + 1:] if str(other or "").strip())
    for line in _lines(blocks):
        for pattern in patterns:
            match = pattern.search(line)
            if match:
                yield match[1]
def _fill(doc_type, out, blocks):
    """빠진 스칼라를 라벨 동의어로 찾아 채운다. 짝이 되는 필드가 이미 쓰고 있는 값은 그 필드의 것이다."""
    for key, value in out.items():
        if value is not None or key not in LABELS:
            continue
        for candidate in _candidates(LABELS[key], blocks):
            filled = _value(doc_type, key, candidate)
            if filled and filled != out.get(DISTINCT.get(key)):
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


def is_total(row) -> bool:
    """합계·소계 등 표의 집계 행인지. 금액을 더할 때 빼야 하는 행이다."""
    return bool(_TOTAL_ROW.match(_key((row or {}).get("항목") or "")))


def _totals(doc_type, out):
    """합계 행의 금액으로 빈 합계 필드를 채운다.

    집계 행을 표에 두는 유형(``KEEP_TOTALS``)은 소계 행도 지우지 않는다 — 서식에 인쇄된 행이라
    지우면 아래 행이 통째로 밀린다. 대신 소계는 합계 필드를 채우지 않고, 금액을 더하는 검사
    (``_sum_checks``)가 ``is_total``로 빼 준다.
    """
    for table, mapping in TOTALS.get(doc_type, {}).items():
        kept = []
        for row in out.get(table) or []:
            if not is_total(row):
                kept.append(row)
                continue
            if item(row.get("항목")) == "합계":  # 소계·중간소계는 합계 필드를 채우지 않는다
                for column, field in mapping.items():
                    if field in out and not out[field] and row.get(column):
                        out[field] = row[column]
                row = {**row, "항목": "합계"}
            if doc_type in KEEP_TOTALS:
                kept.append(row)
        out[table] = kept


def _notes(doc_type, out, blocks):
    """전용 표가 없는 서식에서 소견 문장·비고의 날짜 표시로 치료·검사·수술 내역 행을 만든다(AO 관례)."""
    tables = doctypes.spec(doc_type)["tables"]
    for table, (labels, date_column, name_column) in NOTES.items():
        if table not in tables:
            continue
        if out.get(table):
            continue
        for candidate in _candidates(labels, blocks):
            text = normalize("text", candidate)
            if text and len(_key(text)) >= SENTENCE and not _junk(text):
                # 소견 속 날짜는 진료일이 아니라 과거력·예정일인 경우가 많아 표의 날짜 칸에는 넣지 않는다.
                out[table] = [{date_column: None, name_column: text}]
                break
    for line in _lines(blocks):
        for date, mark in _MARKED_DATE.findall(line):
            table = MARKS[mark]
            _, date_column, name_column = NOTES[table]
            row = {date_column: normalize("date", date), name_column: mark}
            if table in tables and row not in out.setdefault(table, []):
                out[table].append(row)


def _columns(doc_type, out):
    """표 열의 AO 관례: 진료비영수증은 항목명을 정규화하고, 세부내역서는 코드를 EDI코드 한 열에 모으고
    급여/비급여 칸과 종료일자를 급여구분·총액·시작일자에서 채운다."""
    for row in out.get(ITEM_TABLE) or []:
        if doc_type == "진료비영수증":
            row["항목"] = item(row.get("항목"))
            continue
        if doc_type != "세부내역서":
            return
        code, edi = row.get("원내코드"), row.get("EDI코드")
        if code and (not edi or code == edi):
            row["원내코드"], row["EDI코드"] = None, edi or code
        if not row.get("종료일자") and row.get("시작일자"):
            row["종료일자"] = row["시작일자"]
        paid = row.get("급여구분")
        if paid in ("급여", "비급여") and not row.get(paid) and row.get("총액"):
            row[paid] = row["총액"]


def _group_titles(doc_type, out, blocks):
    """머리글이 '묶음 제목'이라고 말하는 금액 열은 하위 열의 합일 뿐이므로 비운다(진료비영수증 급여·비급여)."""
    if doc_type != "진료비영수증":
        return
    cells = _headers(blocks)
    for column, (titles, subs, _) in GROUPED.items():
        if _grouped(cells, titles, subs) is True:
            for row in out.get(ITEM_TABLE) or []:
                row[column] = None


def _receipt_column(cells):
    """반복·병합된 영수증 머리글 셀을 AO 항목내역 열 이름으로 바꾼다."""
    text = _key(" ".join(str(cell or "") for cell in cells))
    if "선택진료료이외" in text or "선택진료료외" in text:
        return "선택진료료외"
    if "선택진료료" in text:
        return "선택진료료"
    if "전액본인부담" in text:
        return "전액본인부담"
    if "공단부담" in text or "보험자부담" in text:
        return "공단부담금"
    if "본인부담" in text:
        return "본인부담금"
    return None


def _receipt_item(values):
    """항목이 여러 병합 칸으로 나뉜 행에서 실제 항목명만 조합한다."""
    values = [str(value).strip() for value in values if str(value or "").strip()]
    if not values:
        return None
    # 첫 칸은 보통 '기본항목' 같은 분류이고, 끝 두 칸이 항목·세부항목이다.
    tail = values[-2:]
    text = tail[-1] if len(tail) == 1 or _key(tail[0]) == _key(tail[-1]) else " ".join(tail)
    name = item(text)
    # 안내문·날짜·OCR 깨짐은 표 칸 수가 맞아도 항목 행의 근거가 될 수 없다. 실제 항목은 짧은
    # 한글(필요하면 CT·MRI 같은 대문자 약어)로 이뤄진다.
    if (not name or name not in RECEIPT_ITEM_NAMES or _junk(text) or not re.search(r"[가-힣]", name) or not _RECEIPT_ITEM_TEXT.fullmatch(name)
            or normalize("date", name)):
        return None
    return name


def _receipt_rows(blocks):
    """파서 표에서 근거가 확실한 진료비영수증 항목 행만 복원한다.

    표 머리글의 항목 병합 칸과 둘 이상의 금액 열을 함께 확인한다. 따라서 본문 문장이나 다른 표를
    항목으로 해석하지 않으며, 원 추출에 없는 항목만 보충하는 데 쓴다.
    """
    rebuilt = []
    for block in blocks or []:
        rows = block.get("rows") or []
        for start, header in enumerate(rows):
            item_columns = [index for index, cell in enumerate(header) if _key(cell).endswith("항목")]
            if not item_columns:
                continue
            body = next((index for index in range(start + 1, len(rows))
                         if _receipt_item([rows[index][column] if column < len(rows[index]) else ""
                                           for column in item_columns])), None)
            if body is None:
                continue
            columns = {index: _receipt_column([row[index] if index < len(row) else "" for row in rows[start:body]])
                       for index in range(len(header))}
            leaves = {}
            for index, column in columns.items():
                if column:
                    leaves.setdefault(column, []).append(index)
            if len(leaves) < 2:
                continue
            for source in rows[body:]:
                name = _receipt_item([source[index] if index < len(source) else "" for index in item_columns])
                if not name:
                    continue
                row = {"항목": name}
                for column, indexes in leaves.items():
                    values = {normalize("amount", source[index]) for index in indexes if index < len(source)} - {None}
                    row[column] = values.pop() if len(values) == 1 else None
                rebuilt.append(row)
            break
    return rebuilt


def _receipt_table(doc_type, out, blocks):
    """모델이 뭉치거나 빠뜨린 영수증 항목 행을 파서 표 행으로 바로잡는다.

    파서 표는 서식에 인쇄된 순서와 세분 항목명(``주사료_행위료``·``입원료_1인실``)을 그대로 갖고 있다.
    항목명이 겹치지 않게 넉넉히 복원됐을 때만 그 목록을 뼈대로 삼아 모델 행을 제자리에 맞추고
    (값은 모델 쪽을 쓰고 빈 칸만 파서 표로 메운다), 뼈대에 없는 모델 행은 뒤에 남긴다.
    복원이 부실하면 예전처럼 빠진 항목만 인쇄 순서 자리에 보충한다.
    """
    if doc_type != "진료비영수증":
        return
    rows, rebuilt = out.get(ITEM_TABLE) or [], _receipt_rows(blocks)
    names = [row["항목"] for row in rebuilt]
    if len(rebuilt) >= max(2, len(rows)) and len(set(names)) == len(names):
        merged = []
        for base, mine in pair_rows(doc_type, ITEM_TABLE, rebuilt, rows, fallback=False):
            merged.append(mine if base is None else {
                **base, **{column: value for column, value in (mine or {}).items()
                           if value is not None and column != "항목"}})
        out[ITEM_TABLE] = merged
        return
    present = {item(row.get("항목")) for row in rows}
    for row in rebuilt:
        if row["항목"] not in present:
            rows.insert(_insert_at(rows, rebuilt, row["항목"]), row)
            present.add(row["항목"])
    out[ITEM_TABLE] = rows


def _period(out):
    """진료기간 칸이 비면 표의 시작·종료일자에서 채운다."""
    for key in out:
        if out.get(key) or not isinstance(key, str):
            continue
        column = "시작일자" if "진료시작일" in key else "종료일자" if "진료종료일" in key else None
        dates = sorted(row[column] for row in out.get(ITEM_TABLE) or [] if column and row.get(column))
        if dates:
            out[key] = dates[0] if column == "시작일자" else dates[-1]


def derive(doc_type: str, out: dict) -> dict:
    """값을 읽어 채울 수 있는 자리를 AO 관례대로 채운다(성별·생년월일·사고발생일자·표 열 관례).

    ``apply``가 마지막에 부르고, 정답셋 라벨도 같은 관례를 쓰도록 ``scripts/verify_label.conform``이
    그대로 재사용한다 — 관례 정의를 두 벌 두지 않는다.
    """
    _columns(doc_type, out)
    fields = doctypes.spec(doc_type)["fields"]
    idnum = next((out[key] for key, meta in fields.items() if meta["kind"] == "idnum" and out.get(key)), None)
    back = idnum.partition("-")[2][:1] if idnum else ""
    if back and back in "123456" and "성별" in fields and not out.get("성별"):
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
    return out


def _earliest(out):
    dates = [out[key] for key in _ACCIDENT_DATES if out.get(key)]
    dates += [row[column] for rows in out.values() if isinstance(rows, list)
              for row in rows for column in _ACCIDENT_COLUMNS if row.get(column)]
    return min(dates, default=None)


# ── 진료비영수증 항목내역 검사 ──────────────────────────────────────────────

ITEM_TABLE = "항목내역"
ITEM_COLUMNS = ("본인부담금", "공단부담금", "전액본인부담", "비급여", "선택진료료", "선택진료료외", "급여")
TOLERANCE = 100  # 십의 자리 절사 허용 오차(요건 1절)
# 합계 필드 → 합계 행에서 더할 열(요건 1절 합계식). 비급여와 선택진료료·선택진료료외는 한쪽만 값을 갖는
# 묶음 제목·하위 열 관계라 함께 더해도 겹치지 않는다.
TOTAL_FIELDS = {
    "진료비총액": ITEM_COLUMNS,
    "환자부담총액": tuple(column for column in ITEM_COLUMNS if column not in ("공단부담금", "급여")),
    "공단부담총액": ("공단부담금",),
}
GROUPED = {  # 열 → (묶음 제목 후보, 하위 열이 있으면 그 열은 독립 열이 아니다, 값을 옮길 열)
    "급여": (("급여", "요양급여"), ("본인부담", "공단부담", "전액본인"), "비급여"),
    "비급여": (("비급여",), ("선택진료",), "급여"),
}
ITEM_ALIASES = (  # AO 프롬프트의 항목명 정규화 규칙
    (re.compile(r"^입원료.*1인"), "입원료_1인실"),
    (re.compile(r"^입원료.*[23]"), "입원료_2-3인실"),
    (re.compile(r"^입원료.*4인"), "입원료_4인실이상"),
    (re.compile(r"^(투약|투약및조제료).*행위"), "투약및조제료_행위료"),
    (re.compile(r"^(투약|투약및조제료).*약품"), "투약및조제료_약품비"),
    (re.compile(r"^주사.*행위"), "주사료_행위료"),
    (re.compile(r"^주사.*약품"), "주사료_약품비"),
    (re.compile(r"^식대?$"), "식대"),
    (re.compile(r"^(계|합계|총계|합계금액)$"), "합계"),
)
# 건강보험 진료비 계산서·영수증의 표준 항목. 파서 표에서 새 행을 만들 때만 이 목록을 적용한다.
# 모델이 낸 비정형 항목은 버리지 않고 그대로 보존한다.
RECEIPT_ITEM_NAMES = frozenset((
    "진찰료", "입원료", "입원료_1인실", "입원료_2-3인실", "입원료_4인실이상", "식대",
    "투약및조제료_행위료", "투약및조제료_약품비", "주사료_행위료", "주사료_약품비",
    "처치및수술", "처치및수술료", "검사료", "영상진단료", "방사선치료료", "마취료", "정신요법료",
    "재활및물리치료료", "치료재료대", "전혈및혈액성분제제료", "CT진단료", "MRI진단료", "PET진단료",
    "초음파진단료", "보철교정료", "제증명료", "정액수가", "정액수가요양병원", "포괄수가진료비",
    "65세이상등정액", "시행령별표2제4호의요양급여", "합계",
))
LUMP_ITEMS = ("정액수가", "65세이상등정액", "질병군포괄수가")  # 항목 행을 묶어 담는 포괄수가 행
_MULTI_AMOUNT = re.compile(r"\d[\d,]*\s+\d")
_RECEIPT_ITEM_TEXT = re.compile(r"^[0-9A-Z가-힣_-]{1,24}$")


def item(name) -> str | None:
    """진료비영수증 항목명을 AO 프롬프트 규칙대로 정규화한다(입원료 1인실 → 입원료_1인실 등)."""
    text = re.sub(r"[^0-9A-Za-z가-힣]", "", str(name or ""))
    return next((canonical for pattern, canonical in ITEM_ALIASES if pattern.match(text)), text or None)


def _money(value) -> int | None:
    """금액을 부호 있는 정수로. ``normalize``가 지우는 음수 부호를 살린다."""
    text = normalize("amount", value)
    return None if text is None else -int(text) if str(value).strip().startswith("-") else int(text)


def _flag(code, message, key=ITEM_TABLE, **extra):
    return {"code": code, "key": key, "message": message, **extra}


def _row_of(rows, name):
    return next((row for row in rows if item(row.get("항목")) == item(name)), None)


def _headers(blocks):
    """파싱 블록에서 항목 표 머리글 셀 모음. '항목'으로 끝나는 셀이 있는 행부터 세 행을 머리글로 본다.

    병합된 셀 탓에 '항목'이 앞 칸 글자와 붙어 나오기도 해서 끝만 맞춰 찾는다. 항목 행이 없는 블록은
    다른 표이므로 건너뛴다(엉뚱한 표의 제목이 섞이면 없는 열을 있다고 볼 수 있다)."""
    cells = set()
    for block in blocks or []:
        rows = block.get("rows") or []
        start = next((index for index, row in enumerate(rows) if any(_key(cell).endswith("항목") for cell in row)), None)
        for row in rows[start:start + 3] if start is not None else []:
            cells.update(_key(cell) for cell in row if str(cell or "").strip())
    return cells


def _grouped(cells, titles, subs):
    """머리글로 보아 그 금액 열이 하위 열을 묶는 제목인지. 판단 근거가 없으면 None."""
    title = any(cell.startswith(name) for cell in cells for name in titles)
    sub = any(cell.startswith(name) for cell in cells for name in subs)
    return None if not (title or sub) else sub or not title


def check(doc_type: str, ao_fields: dict, docraft_fields: dict, blocks: list[dict]) -> list[dict]:
    """문서의 이상 징후 ``{"code", "key", "row"?, "message"}`` 목록. 진료비영수증 항목내역 전용."""
    rows = ao_fields.get(ITEM_TABLE) or []
    if doc_type != "진료비영수증" or not rows:
        return []
    mine = docraft_fields.get(ITEM_TABLE) or []
    found = []
    for side, side_rows in (("AO", rows), ("Docraft", mine)):
        for index, row in enumerate(side_rows):
            for column in ITEM_COLUMNS:
                if _MULTI_AMOUNT.search(str(row.get(column) or "")):
                    found.append(_flag("multi_amount", f"{side} 표 {index}행 '{column}' 셀에 금액이 둘 이상 들어 있다: "
                                                       f"{row[column]}", row=index, column=column))
    cells = _headers(blocks)
    for column, (titles, subs, _) in GROUPED.items():
        if _grouped(cells, titles, subs) is not True:  # 묶음 제목이라고 확신할 때만 집어낸다
            continue
        for index, row in enumerate(rows):
            if _money(row.get(column)):
                found.append(_flag("no_column", f"이 표에는 독립된 '{column}' 열이 없으므로 {index}행 "
                                                f"'{row.get('항목')}'의 {column}는 0이어야 한다.", row=index, column=column))
    found += _row_checks(rows, mine)
    found += _sum_checks(ao_fields, rows)
    return found


def _amounts(row):
    return tuple(_money(row.get(column)) or 0 for column in ITEM_COLUMNS)


def _row_checks(rows, mine):
    """합계 행 베끼기와 AO·Docraft 간 항목 행 누락·과다를 본다."""
    found = []
    names, my_names = [item(row.get("항목")) for row in rows], [item(row.get("항목")) for row in mine]
    body = [row for row in rows if not is_total(row)]
    total = next((index for index, name in enumerate(names) if name == "합계"), len(rows) - 1)
    if len(rows) > 1 and sum(any(_amounts(row)) for row in body) > 1:
        copied = next((index for index in range(total) if _amounts(rows[index]) == _amounts(rows[total])
                       and any(_amounts(rows[total]))), None)
        if copied is not None:
            found.append(_flag("row_copy", f"합계 행({total}행)의 금액이 {copied}행 "
                                           f"'{rows[copied].get('항목')}'과 전부 같다. 합계를 베낀 것으로 보인다.", row=total))
    for name in dict.fromkeys(my_names):
        if name and not is_total({"항목": name}) and name not in names:
            found.append(_flag("row_missing", f"Docraft가 읽은 항목 '{name}' 행이 AO 표에 없다.", item=name))
    valued = {name for row, name in zip(rows, names) if any(_amounts(row)) and not is_total(row)}
    for name in dict.fromkeys(names):
        if name in valued and my_names and name not in my_names:
            found.append(_flag("row_extra", f"AO 표의 항목 '{name}' 행이 Docraft 표에는 없다."))
    return found


def _sum_checks(fields, rows):
    """요건 1절의 합계식·열별 합을 본다. 십의 자리 절사는 허용한다."""
    found = []
    total = next((row for row in rows if item(row.get("항목")) == "합계"), None)
    added = {column: sum(_money(row.get(column)) or 0 for row in rows if not is_total(row))
             for column in ITEM_COLUMNS}
    stated = {column: _money(total.get(column)) or 0 for column in ITEM_COLUMNS} if total else added
    # 포괄수가 행은 위쪽 항목 행을 다시 담으므로 열별 합이 어긋나는 것이 정상이다.
    lump = any(any(_amounts(row)) and (item(row.get("항목")) or "").startswith(LUMP_ITEMS) for row in rows)
    if total and not lump:
        for column, value in stated.items():
            if abs(value - added[column]) >= TOLERANCE:
                found.append(_flag("sum_mismatch", f"합계 행의 '{column}' {value:,}이 항목 행 합 {added[column]:,}과 다르다."))
    for field, columns in TOTAL_FIELDS.items():
        value, computed = _money(fields.get(field)), sum(stated[column] for column in columns)
        if value is not None and abs(value - computed) >= TOLERANCE:
            found.append(_flag("sum_mismatch", f"{field} {value:,}이 합계 행의 {'+'.join(columns)} {computed:,}과 다르다.",
                               key=field))
    return found


def correct(doc_type: str, checks: list[dict], ao_fields: dict, docraft_fields: dict) -> dict:
    """확실한 이상만 Judge 없이 룰로 교정한다. ``{key: (교정값, 사유)}``."""
    rows, mine = [dict(row) for row in ao_fields.get(ITEM_TABLE) or []], docraft_fields.get(ITEM_TABLE) or []
    reasons = []
    for flag in sorted(checks, key=lambda flag: flag["code"] != "no_column"):  # 행을 끼우기 전에 열부터 고친다
        row = rows[flag["row"]] if flag.get("row") is not None and flag["row"] < len(rows) else None
        if flag["code"] == "no_column" and row is not None:
            target = GROUPED[flag["column"]][2]
            source = _row_of(mine, row.get("항목"))
            if source and _money(source.get(target)) == _money(row[flag["column"]]) and not _money(row.get(target)):
                row[target], row[flag["column"]] = row[flag["column"]], "0"
                reasons.append(f"no_column: {row.get('항목')} 행의 {flag['column']}를 {target}로 옮겼다")
        elif flag["code"] == "row_missing":
            name = flag["item"]
            source = _row_of(mine, name)
            if source and not any(_amounts(source)):
                rows.insert(_insert_at(rows, mine, name), {**source, "항목": name})
                reasons.append(f"row_missing: 금액이 모두 0인 '{name}' 행을 Docraft에서 채웠다")
    return {ITEM_TABLE: (rows, " / ".join(reasons))} if reasons else {}


def _insert_at(rows, mine, name):
    """Docraft에서 바로 앞 항목이 AO 표에 있는 자리 뒤에 끼운다. 없으면 합계 앞."""
    names = [item(row.get("항목")) for row in rows]
    my_names = [item(row.get("항목")) for row in mine]
    for previous in reversed(my_names[:my_names.index(name)]):
        if previous in names:
            return names.index(previous) + 1
    return names.index("합계") if "합계" in names else len(rows)


# ── 적용 ────────────────────────────────────────────────────────────────────


def apply(doc_type: str, result: dict, blocks: list[dict]) -> dict:
    spec = doctypes.spec(doc_type)
    result = result or {}
    out = {key: _value(doc_type, key, result.get(key)) for key in spec["fields"]}
    for table, columns in spec["tables"].items():
        rows = [row for row in (result.get(table) or []) if isinstance(row, dict)]
        out[table] = [{column: _value(doc_type, column, row.get(column), table) for column in columns} for row in rows]
    _fill(doc_type, out, blocks or [])
    _notes(doc_type, out, blocks or [])
    _split_codes(out)
    _receipt_table(doc_type, out, blocks or [])
    _totals(doc_type, out)
    _group_titles(doc_type, out, blocks or [])
    _period(out)
    return derive(doc_type, out)
