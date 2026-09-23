"""twin reader 플러그인에서 이식한 룰 기반 정규화·추출·후처리.

- ``normalize(kind, value)``: 값 하나를 kind에 맞게 정규화한다(날짜 → YYYYMMDD, 금액 → 숫자 문자열 등).
  비교 가능한 정규형이 없으면 None을 돌려준다.
- ``apply(doc_type, result, blocks)``: ``engine.extract`` 결과(정규 표현, doctypes 참고)에
  파싱 블록(``parsers.parse``의 blocks)을 근거로 룰을 적용해 새 정규 표현을 돌려준다.
  값 정규화, 값 자리에 들어온 서식 라벨·표 마크업과 빈 행·머리글 행 제거, 연번호를 차트번호로 옮기기, 빠진 필드의 라벨 동의어 기반 보충,
  소견 문장에서 치료·검사 내역 행 만들기, 병명코드·수술일자 분리, 인쇄되지 않은 급여 합계 비우기, 합계행 정리,
  머리글에 없는·묶음 제목인 금액 열 비우기, 통째로 맞바뀐 금액 열 되돌리기, ``derive``의 관례 채우기를 차례로 한다.
- ``derive(doc_type, fields)``: 읽은 값에서 채울 수 있는 자리를 AO 관례대로 채운다(성별·생년월일,
  진료비영수증 항목명 정규화·외래 진료종료일, 세부내역서 코드 열·비급여 칸·종료일자, 사고발생일자).
  정답셋 라벨도 같은 관례를 쓰도록 ``scripts/verify_label.conform``이 이 함수를 그대로 쓴다.
- ``same(kind, a, b)``: 두 값이 정규화 후 같은지(금액의 빈 칸·0, 텍스트의 접두·접미 차이는 같게 본다).
- ``pair_rows(doc_type, table, left, right)``: 두 표의 행을 키 열(``ROW_KEYS``)로 대응시킨다. 행 순서·개수가
  달라도 같은 행끼리 맞물리게 하며, ``is_total(row)``은 그중 합계·소계 행을 가린다. 교차검증
  (``verify._row_diff``)과 채점(``scripts/verify_eval``)이 같은 규칙을 쓰도록 여기 한 곳에 둔다.
- ``check(doc_type, ao, docraft, blocks)``: 이상 징후 목록. 모든 유형에 날짜 앞뒤·주민번호 일치·합계식·
  근거 없는 합계·마스터에 없는 병명코드를, 세부내역서에 행 산술·문서 품질·급여구분 값을, 진료비영수증 항목내역에
  금액 겹침·없는 열·합계 베끼기·합계 불일치·열 바뀜·행 밀림·행 누락을 본다.
- ``correct(doc_type, checks, ao, docraft)``: 그중 확실한 이상을 Judge 없이 바로 교정한다.
- ``sum_errors(doc_type, fields)``: 합계식 불일치 수. Judge 판정이 합계식을 더 어기면 되돌리는 데 쓴다.

룰은 데이터 테이블(``LABELS``·``FIELD_RULES``·``TOTALS``·doctypes.ENUMS)과 공통 엔진으로 나눠 둔다.
"""

import logging
import re
from collections import Counter
from datetime import date as _calendar_date

from . import doctypes, master
from .doctypes import ENUMS

logger = logging.getLogger(__name__)

# ── 데이터 테이블 ────────────────────────────────────────────────────────────

OCR_DIGITS = str.maketrans({"I": "1", "l": "1", "|": "1", "/": "1", "O": "0", "o": "0",
                            "ㅇ": "0", "이": "0", "B": "8", "b": "6"})

LABELS = {  # 필드 → 라벨 동의어. 블록에서 빠진 값을 찾을 때 쓴다(twin reader keywordInfo + 서식 실물 라벨).
    "통원일수": ["통원일수", "방문일수", "실제내원일수", "외래일수", "통원치료일수", "실통원일수"],
    "진단일": ["진단일", "진단일자", "진단연월일", "진단년월일", "소견일", "4.진단일"],
    "진료과": ["진료과", "진료과목", "입원과", "과명", "진료센터(과)"],
    "입원일자": ["입원일", "입원일자", "입원연월일", "입원년월일", "입원기간", "입원치료기간", "입퇴원일"],
    "퇴원일자": ["퇴원일", "퇴원일자", "퇴원연월일", "퇴원년월일", "입퇴원일", "입원기간", "입원치료기간"],
    "통원일": ["통원일", "통원일자", "실통원일자", "실제내원일자", "외래진료일", "내원일", "통원기간"],
    "초진일": ["초진일", "초진일자", "초진연월일", "초진년월일", "최초진료일", "최초내원일"],
    "발급일": ["발급일", "발행일", "발급일자", "발행일자", "발급연월일", "발행연월일", "작성일", "발급일시"],
    "병원명": ["의료기관명칭", "의료기관명", "요양기관명칭", "요양기관명", "병의원명칭", "병원명칭", "병원명", "기관명", "명칭"],
    "병원주소": ["주소", "소재지", "의료기관주소", "병의원주소", "사업장소재지"],
    "병원연락처": ["전화및FAX", "대표전화", "전화번호", "TEL", "Tel", "전화"],
    "면허번호": ["면허번호", "의사면허번호", "의사번호", "의사면허", "주치의면허번호"],
    "의사명": ["의사성명", "의사명", "담당의사", "주치의", "전문의", "한의사성명", "치과의사성명", "성명", "의사"],
    "환자 등록번호": ["환자등록번호", "병원등록번호", "등록번호", "환자번호", "병록번호", "병록번호", "고객번호", "환자ID"],
    "차트번호": ["차트번호", "챠트번호", "진료카드번호", "연번호", "발행번호", "일련번호", "문서번호"],
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
    "환자정보(병실)": ["병실", "호실", "병실번호", "병실호수", "병실구분", "병동-병실", "진료과병실"],
    "환자정보(입통원구분)": ["입통원구분", "입원외래구분", "진료구분", "유형"],
    "영수증진료형태(환자구분)": ["환자구분", "환자유형", "보험구분", "보험유형", "유형", "자격"],
    "급여_본인부담총액": ["본인부담금", "본인부담액", "급여본인", "일부본인부담금", "본인부담"],
    "급여_공단부담총액": ["공단부담금", "공단부담액", "급여공단", "보험자부담금", "공단부담"],
    "급여_전액본인부담총액": ["전액본인부담금", "전액본인부담", "전액본인", "전액부담"],
    "급여_급여총액": ["급여총액", "요양급여", "급여계", "급여합계", "급여"],
    "선택진료료총액": ["선택진료료", "선택진료", "지정진료비", "선택진료료총액"],
    "선택진료료외총액": ["선택진료료이외", "선택진료료외", "선택진료외", "선택진료료외총액"],
    "비급여총액": ["비급여", "비급여총액", "비급여계", "비급"],
    "조제일자": ["조제일자", "조제일", "조제연월일", "조제년월일"],
    "진료비내역-총액": ["약제비총액", "총약제비", "약제비합계"],
    "진료비내역-급여본인부담": ["본인부담금", "본인부담액", "급여본인부담"],
    "진료비내역-공단부담액": ["보험자부담금", "보험자부담액", "공단부담금", "공단부담액"],
    "진료비내역-전액본인부담": ["전액본인부담금", "전액본인부담"],
    "진료비내역-비급여및전액본인부담금": ["비급여및전액본인부담금", "비급여및전액본인부담"],
    "진료비내역-환자부담총액": ["환자부담총액", "본인부담총액"],
    "소득공제대상액-수납금액": ["총수납금액", "수납금액"],
    "약국정보(상호)": ["상호", "약국명", "약국명칭"],
    "약국정보(사업자등록번호)": ["사업자등록번호", "사업자번호"],
    "약국정보(주소)": ["사업장소재지", "소재지", "약국주소", "주소"],
}

MASTER_NAMES = {  # 표 → (코드 열, 명칭 열, 마스터 계통). 코드가 마스터에 있을 때만 명칭을 고친다
    "항목내역": ("EDI코드", "EDI명칭", "edi"),
    "병명내역": ("병명코드", "병명", "kcd"),
}

# 같은 라벨('주소'·'성명'·'진료기간')을 여러 칸이 나눠 쓰는 필드 무리. 한 무리에서 한 값은 한 필드만 쓴다.
EXCLUSIVE = (
    ("주소", "병원주소", "의료기관정보-주소", "약국정보(주소)"),
    ("연락처", "병원연락처"),
    ("이름", "환자성명", "환자정보-성명", "의사명", "병원명", "의료기관정보-명칭", "약국정보(상호)"),
    ("진단일", "발급일", "초진일", "입원일자", "퇴원일자", "통원일"),
    ("환자정보-진료시작일", "환자정보-진료종료일"),
    ("환자정보(진료시작일)", "환자정보(진료종료일)"),
)
SECTIONS = {  # 영역 → 그 영역이 시작됐다는 표시. 의료기관 표시가 환자 표시를 이긴다.
    "기관": ("의료기관", "요양기관", "병의원", "면허번호", "사업자등록번호", "위와같이", "원본대조필",
            "상호", "의사", "발행인", "사업장"),
    "환자": ("환자", "수진자", "주민등록번호", "생년월일", "병록번호"),
}
FIELD_SECTION = {  # 환자 칸·의료기관 칸이 같은 라벨을 나눠 쓰는 필드만 영역을 따진다.
    **dict.fromkeys(("주소", "연락처", "이름", "환자성명", "환자정보-성명"), "환자"),
    **dict.fromkeys(("병원주소", "병원연락처", "병원명", "의사명",
                     "의료기관정보-주소", "의료기관정보-명칭", "약국정보(주소)", "약국정보(상호)"), "기관"),
}
EXPLICIT = {("소견서", "진단일"), ("소견서", "초진일")}  # 그 유형에 원래 드문 필드. 제 이름 라벨일 때만 채운다.
LAST_DATE = ("진료종료일", "퇴원일자")  # '진료기간(입원기간) A ~ B' 한 칸에서 마지막 날짜를 취할 필드

TOTALS = {  # 표 합계행 → 합계 필드. 합계행은 표에서 빼고 비어 있는 필드만 채운다.
    "세부내역서": {"항목내역": {"본인부담": "급여_본인부담총액", "공단부담": "급여_공단부담총액",
                            "전액본인부담": "급여_전액본인부담총액", "급여": "급여_급여총액",
                            "선택진료료": "선택진료료총액", "선택진료료외": "선택진료료외총액",
                            "비급여": "비급여총액"}},
    "진료비영수증": {"항목내역": {"공단부담금": "공단부담총액"}},
}
UNPRINTED_NULL = ("급여_본인부담총액", "급여_공단부담총액", "급여_전액본인부담총액", "급여_급여총액")  # 글자에 없으면 지우는 합계
KEEP_TOTALS = {"진료비영수증"}  # AO 스키마가 합계 행을 표에 두는 유형. 합계 필드를 채운 뒤에도 행을 남긴다.

ROW_KEYS = {  # 표 → 행을 식별하는 열. 두 표의 행을 짝지을 때 쓴다(``pair_rows``). 스키마에 없는 열은 건너뛴다.
    "항목내역": ("항목", "EDI코드", "시작일자"),
    "병명내역": ("병명코드",),
    "수술내역": ("수술일자",),
    "검사내역": ("검사일",),
    "치료내역": ("치료일",),
    "행위내역": ("행위일",),
}

_ACCIDENT_DATES = ("진단일", "조제일자")  # 사고발생일자 후보(스칼라). 약제비영수증은 조제일자다
_ACCIDENT_COLUMNS = ("수술일자", "검사일", "치료일", "행위일")  # 사고발생일자 후보(표 열)

NOTES = {  # 표 → (소견 문장을 담은 칸의 라벨, 날짜 열, 이름 열). 전용 표가 없는 서식에서 행을 만든다.
    # 뒤의 표는 앞의 표에 이미 담긴 내용을 다시 담지 않는다(수술·검사를 적은 소견 문장은 치료내역이 되지 않는다).
    "수술내역": (["수술소견", "수술내용"], "수술일자", "수술명"),
    "검사내역": (["검사소견", "검사결과", "검사내용"], "검사일", "검사명"),
    "치료내역": (["치료소견", "치료내용", "치료내용및향후치료에대한소견", "향후치료의견", "향후치료계획",
                "치료및향후치료의견", "향후치료에대한소견", "내용"], "치료일", "치료명"),
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
_NAME_WORDS = re.compile(r"의사|성명|이름|환자|면허|직인|서명|담당|주치의|전문의|연령|나이|또는|만\s*\d+\s*세")
_SEAL = re.compile(r"[(\[]\s*(?:인|印)\s*[)\]]|\s+(?:인|印)\s*$")  # 이름 뒤 날인 표시: (인)·[인]·(印)·공백+인
_PHONE_IN_TEXT = re.compile(r"\(?\d{2,4}\)?\s*-\s*\d{3,4}\s*-\s*\d{4}\)?")
_TOTAL_ROW = re.compile(r"^(합계|총합계|총계|소계|계|total|합계금액|끝수처리조정금액?)$", re.I)
_TRUE = re.compile(r"^[\[(]?\s*(y|yes|o|v|1|true|예|체크|해당|√|✓|✔|☑|■|●)\s*[\])]?$|[✓✔√☑■●]|체크", re.I)
_WARD = re.compile(r"^(?=.*\d)[A-Za-z0-9/:\-]+호?$")
_EMPTY = ("", "[]", "{}", "none", "null", "nan", "-", "n/a")
_WORD = re.compile(r"[0-9A-Za-z가-힣]")
_HTML = re.compile(r"</?(?:t[dhr]|table|br|p)\b", re.I)
_OPTIONS = re.compile(r"[\[(][^\]\)]{0,3}[\])]|[□☐■▣☑✔√●○]")  # 서식의 선택지 표시([ ] 의사 [ ] 치과의사)
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
    """금액의 숫자. 천 단위 구분 기호는 빼고, 소수 한두 자리(세부내역서 단가 954.5 등)는 살린다('.0'은 정수).
    소수 세 자리('1.234')는 천 단위 구분으로 본다."""
    digits = re.sub(r"[^\d.]", "", text.translate(OCR_DIGITS))
    whole, dot, fraction = digits.rpartition(".") if re.fullmatch(r"\d+\.\d{1,2}", digits) else (digits, "", "")
    whole = whole.replace(".", "")
    if not whole:
        return None
    fraction = fraction.rstrip("0")
    return (whole.lstrip("0") or "0") + (f".{fraction}" if fraction else "")


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
    return match[1] + ("-" + match[2].ljust(7, "*") if match[2] else "") if match else None  # 가린 뒷자리는 *로 채운다


def _phone(text):
    text = re.sub(r"[-/()]{0,2}\s*(fax|팩스).*", "", text, flags=re.I | re.S)
    digits = re.sub(r"-{2,}", "-", re.sub(r"[^\d-]+", "-", text)).strip("-")
    digits = re.sub(r"^(02|0[1-9]\d)(\d{3,4})(\d{4})$|^(1[5-9]\d\d)()(\d{4})$",
                    lambda m: "-".join(filter(None, m.groups())), digits)  # 붙여 쓴 번호에 국번 구분을 넣는다
    digits = re.sub(r"^(0\d{1,2}-\d{3,4}-\d{4})-0\d{1,2}-\d{3,4}-\d{4}$", r"\1", digits)  # 이어 붙은 팩스는 뺀다
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


def _likeness(row, other):
    """두 행에서 값이 있고 표기까지 같은 칸 수."""
    return sum(1 for column, value in row.items() if value not in (None, "", "0") and str(value) == str(other.get(column)))


def pair_rows(doc_type: str, table: str, left: list, right: list, columns=None,
              fallback: bool = True) -> list[tuple[dict | None, dict | None]]:
    """두 표의 행을 ``ROW_KEYS``의 키 열로 짝짓는다.

    값이 같은 행부터 짝짓고(키가 같은 후보가 여럿이면 나머지 칸이 더 많이 같은 행), 남은 행은 키 열의 접두가 같은 행에 붙이고(``주사료`` ⊂ ``주사료_행위료``),
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
            hits = [other for other, mate in enumerate(right) if other not in taken
                    and all(match(kinds[column], row.get(column), mate.get(column)) for column in keys)]
            # 키가 같은 행이 여럿이면(같은 날 이학요법료 셋 등) 나머지 칸이 더 많이 같은 행과 잇는다. 동점이면 순서대로.
            hit = max(hits, key=lambda other: _likeness(row, right[other]), default=None)
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
    text = re.sub(r"[^가-힣]", "", _NAME_WORDS.sub(" ", _LICENSE.sub(" ", _SEAL.sub(" ", text))))
    half = len(text) // 2
    text = text[:half] if half and text[:half] == text[half:] else text
    if set(text) <= set("남여녀") or text.endswith("과"):  # 성별 보기 칸, 진료과('치과의사' 보기)
        return None
    return text if 2 <= len(text) <= 5 else None  # 사람 이름 길이를 벗어나면 라벨 글자가 섞인 것이다


def _hospital(text):
    text = re.sub(r"^\s*(명칭|의료기관명칭|의료기관명|요양기관명|병원명)\s*[:：]?\s*", "", text)
    text = re.sub(r"\(?\s*직인.*", "", text).replace("의과의원", "외과의원").strip()
    return re.sub(r"병$", "병원", text) or None


def _address(text):
    text = re.split(r"주\s*소\s*[:：]?", text)[-1]
    text = re.sub(r"(전화|연락처|tel|fax)\s*[:：]?.*", "", _PHONE_IN_TEXT.sub(" ", text), flags=re.I | re.S)
    text = _text(_DATE.sub(" ", text))
    return text if text and re.search(r"[가-힣]{2}", text) else None


def _serial(text, strict=True):
    """등록·차트번호. 숫자가 없으면 옆 라벨('야간(공휴일)진료')이 흘러든 것이다. 등록번호(``strict``)는 한글이 섞이거나
    ('602-82-00286 상호 …') 날짜로 시작하면('20191024-M188', 접수·영수증번호) 버린다 — 차트번호는 둘 다 흔하다.
    연도만 인쇄된 빈 칸('2018 -')도 버리고, 뒤 칸 라벨('… 주민등록번호 :')이 흘러들면 잘라 낸다."""
    text = re.split(r"\s+[가-힣]{2,}번호", text)[0]
    if not re.search(r"\d", text) or re.fullmatch(r"(19|20)\d\d\s*-?", text) or strict and (
            re.search(r"[가-힣]", text) or re.match(r"\d{8}\D", text) and _dates_in(text[:8])):
        return None
    return text


FIELD_RULES = {  # 필드 → 추가 정제(정규화 뒤에 적용)
    **dict.fromkeys(["환자 등록번호", "환자정보-환자등록번호", "환자정보(환자등록번호)"], _serial),
    "차트번호": lambda text: _serial(text, strict=False),
    "환자정보-질병군(DRG)번호": lambda text: text if re.search(r"[A-Za-z]", text) else None,  # KDRG는 영문으로 시작한다
    **dict.fromkeys(["이름", "의사명", "환자정보-성명", "환자성명"], _name),
    **dict.fromkeys(["병원명", "의료기관정보-명칭", "약국정보(상호)"], _hospital),
    **dict.fromkeys(["주소", "병원주소", "의료기관정보-주소", "약국정보(주소)"], _address),
}


def _key(text):
    return re.sub(r"[\s:：()\[\]._|-]+", "", str(text))


_LABEL_WORDS = frozenset(  # 값 자리에 들어온 서식 라벨을 가려낼 낱말 모음
    _key(word) for word in (*_FORM_WORDS, *(word for words in LABELS.values() for word in words),
                            *(key for spec in doctypes.DOC_TYPES.values() for key in
                              (*spec["fields"], *spec["tables"],
                               *(column for columns in spec["tables"].values() for column in columns))))
)


def _junk(value) -> bool:
    """값이 아니라 서식의 라벨 글자나 표 마크업이 흘러든 것인지('성별', '4 환자구분', '</td><td>')."""
    rest = re.sub(r"^\d{1,2}(?=\D)", "", _key(value))  # 서식의 항목 번호('4 환자구분')는 라벨의 일부다
    if _HTML.search(str(value)) or len(_OPTIONS.findall(re.sub(r"●{2,}", "", str(value)))) > 1:  # ●● 연속은 가림 표시
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
    """라벨 셀이면 근거 등급(정확히 같으면 0, 라벨로 시작하면 1), 라벨 셀이 아니면 None."""
    cell = _key(cell)
    if not cell:
        return None
    if cell in labels:
        return 0
    return 1 if any(cell.startswith(label) and len(cell) <= len(label) + 2 for label in labels) else None


def _section(text, current):
    """블록 순서를 따라가며 지금 읽는 칸이 환자 칸인지 의료기관 칸인지 기억한다."""
    text = _key(text)
    return next((name for name, marks in SECTIONS.items() if any(mark in text for mark in marks)), current)


def _lines(blocks):
    """블록의 텍스트 줄 전부(줄 목록과 text 모두)."""
    for block in blocks:
        yield from (line["text"] for line in block.get("lines") or [])
        yield from (block.get("text") or "").split("\n")


def _candidates(labels, blocks):
    """라벨 오른쪽 셀(표)과 ``라벨: 값`` 패턴(텍스트)에서 ``(등급, 영역, 값)``을 순서대로 낸다.

    등급이 낮을수록 근거가 확실하다(라벨과 똑같은 표 셀 0, 라벨로 시작하는 표 셀 1, 텍스트 줄 2).
    영역은 그 후보를 만나기까지 지나온 라벨이 가리키는 환자 칸·의료기관 칸이다.
    """
    keys = [_key(label) for label in labels]
    # 라벨이 다른 낱말 꼬리에 걸리지 않게 앞 글자를 막는다('환자성명'의 '성명'은 의사명 라벨이 아니다).
    patterns = [re.compile(r"(?<![가-힣A-Za-z0-9])" + r"\s*".join(map(re.escape, label))
                           + r"(?![가-힣])\s*[:：]?\s*([^\n|]{1,60})") for label in labels]
    section = None
    for block in blocks:
        for row in block.get("rows") or []:
            section = _section(" ".join(str(cell or "") for cell in row), section)
            for index, cell in enumerate(row):
                rank = _matches(cell, keys)
                if rank is None:
                    continue
                here = _section(str(cell), section)
                values = [other for other in row[index + 1:] if str(other or "").strip()]
                for other in values or [None]:  # 값이 없는 라벨 칸도 근거 등급은 알린다
                    yield rank, here, other
    section = None
    for line in _lines(blocks):
        section = _section(line, section)
        for pattern in patterns:
            match = pattern.search(line)
            if match:
                yield 2, _section(line[:match.start()], section), match[1]


def _exclusive(key):
    """key와 같은 라벨을 나눠 쓰는 다른 필드들."""
    return tuple(other for group in EXCLUSIVE if key in group for other in group if other != key)


def _picked(doc_type, key, candidate):
    """후보 텍스트에서 필드가 취할 값. 진료기간처럼 범위 한 칸을 쓰는 종료일은 마지막 날짜를 취한다."""
    if any(mark in key for mark in LAST_DATE):
        return next(reversed(_dates_in(str(candidate))), None)
    return _value(doc_type, key, candidate)


def _serials(doc_type, out, blocks):
    """환자 등록번호에 든 값이 연번호·발행번호 칸의 값이면(등록번호 칸의 값이 아니면) 차트번호로 옮긴다."""
    value = out.get("환자 등록번호")
    if not value or out.get("차트번호"):
        return
    near = lambda key: {_picked(doc_type, key, c) for _, _, c in _candidates(LABELS[key], blocks) if c is not None}
    if value in near("차트번호") - near("환자 등록번호"):
        out["차트번호"], out["환자 등록번호"] = value, None


def _fill(doc_type, out, blocks):
    """빠진 스칼라를 라벨 동의어로 찾아 채운다.

    값이 있어야 할 영역(환자 칸·의료기관 칸) 밖의 후보, 같은 무리의 다른 필드가 이미 쓰는 값,
    근거 등급이 같은데 값이 갈리는 후보는 쓰지 않는다 — 잘못 채우는 쪽이 비워 두는 쪽보다 나쁘다.
    """
    for key in list(out):
        if out.get(key) is not None or key not in LABELS:
            continue
        labels = [label for label in LABELS[key] if key in label] if (doc_type, key) in EXPLICIT else LABELS[key]
        want = FIELD_SECTION.get(key)
        taken = {out.get(other) for other in _exclusive(key)} - {None}
        seen, found = set(), {}
        for rank, section, candidate in _candidates(labels, blocks):
            if want and section != want:
                continue
            seen.add(rank)
            value = _picked(doc_type, key, candidate) if candidate is not None else None
            if value and value not in taken:
                found.setdefault(rank, []).append(value)
        # 서식에 그 필드의 라벨 칸이 있는데 비어 있으면, 더 약한 근거로 채우지 않고 빈 칸으로 둔다.
        best = min(found, default=None)
        if best is not None and best <= min(seen) and len(set(found[best])) == 1:
            out[key] = found[best][0]


# ── 표·파생 필드 후처리 ─────────────────────────────────────────────────────


def _split_cells(out):
    """병명 칸에 섞인 병명코드, 수술명 칸에 섞인 수술일자를 제 열로 옮기고 이름에서 그 잔재를 지운다."""
    for row in out.get("병명내역") or []:
        name = row.get("병명")
        if not name:
            continue
        row["병명코드"] = row.get("병명코드") or normalize("code", name)
        row["병명"] = normalize("text", _CODE_IN_TEXT.sub(" ", name))
    for row in out.get("수술내역") or []:
        name = row.get("수술명") or ""
        if _dates_in(name):
            row["수술일자"] = row.get("수술일자") or _date(name)
            row["수술명"] = normalize("text", _DATE.sub(" ", name))


def is_total(row) -> bool:
    """합계·소계 등 표의 집계 행인지. 금액을 더할 때 빼야 하는 행이다."""
    return bool(_TOTAL_ROW.match(_key((row or {}).get("항목") or "")))


def _hollow(doc_type, table, row):
    """값이 하나도 없거나 서식 라벨 글자뿐인 행(흘러든 머리글). 진료비영수증은 금액이 모두 0인 인쇄 행과
    '기타' 같은 라벨꼴 항목명이 흔해 보지 않는다."""
    return doc_type != "진료비영수증" and all(_junk(value) for value in row.values() if value not in (None, "0"))


def _master_names(out):
    """코드가 마스터에 있는 행에 한해 명칭의 1글자 OCR 오인식을 되돌린다(``master.correct_name``).

    코드가 없거나 마스터에 없으면 아무것도 하지 않는다 — 명칭에서 코드를 역추론하지 않는다.
    """
    for table, (code_column, name_column, system) in MASTER_NAMES.items():
        for row in out.get(table) or []:
            fixed = master.correct_name(system, row.get(code_column), row.get(name_column))
            if fixed:
                logger.info("master 교정: %s %s %r → %r", table, row.get(code_column), row[name_column], fixed)
                row[name_column] = fixed


def _totals(doc_type, out):
    """합계 행의 금액으로 빈 합계 필드를 채운다.

    집계 행을 표에 두는 유형(``KEEP_TOTALS``)은 소계 행도 지우지 않는다 — 서식에 인쇄된 행이라
    지우면 아래 행이 통째로 밀린다. 대신 소계는 합계 필드를 채우지 않고, 금액을 더하는 검사
    (``_sum_checks``)가 ``is_total``로 빼 준다.
    """
    for table, mapping in TOTALS.get(doc_type, {}).items():
        kept = []
        body = [row for row in out.get(table) or [] if not is_total(row)]
        for row in out.get(table) or []:
            if not is_total(row):
                kept.append(row)
                continue
            if item(row.get("항목")) == "합계":  # 소계·중간소계는 합계 필드를 채우지 않는다
                for column, field in mapping.items():
                    value, added = _money(row.get(column)), sum(_money(line.get(column)) or 0 for line in body)
                    # 채워 둔 합계 필드도 항목 행 합이 합계 행을 뒷받침하고 합계식(진료비총액=환자+공단)이 어긋나지
                    # 않을 때 합계 행과 다르면 합계 행 값으로 바꾼다.
                    if field in out and value and (not out[field] or _near(value, added) and _fits(out, field, value) is not False
                                                   and not _near(_money(out[field]) or 0, value)):
                        out[field] = row[column]
                row = {**row, "항목": "합계"}
            if doc_type in KEEP_TOTALS:
                kept.append(row)
        out[table] = kept


def _printed(value, blocks):
    """금액이 파싱 블록 글자 어딘가에 그대로(천 단위 구분 기호는 빼고)찍혀 있는지."""
    text = re.sub(r"(?<=\d)[,.](?=\d)", "", "\n".join((*_lines(blocks), *(str(cell or "") for block in blocks
                                                                         for row in block.get("rows") or [] for cell in row))))
    return bool(re.search(rf"(?<!\d){re.escape(str(value).replace('.', ''))}(?!\d)", text))


def _copied(doc_type, fields, key):
    """합계 필드가 항목 행 열 합보다 작거나(소계를 옮김), 둘 이상인 항목 행 중 한 행의 같은 열(급여총액은 총액 열도)
    값을 베꼈는지. 열 합과 같으면 아니다."""
    rows, value = _rows(fields, ITEM_TABLE), _money(fields.get(key))
    column = next((column for column, field in TOTALS.get(doc_type, {}).get(ITEM_TABLE, {}).items() if field == key), None)
    columns, added = (column, "총액") if column == "급여" else (column,), sum(_money(row.get(column)) or 0 for row in rows)
    return bool(column and len(rows) >= 2 and not _near(value, added)
                and (value < added or any(_money(row.get(name)) == value for row in rows for name in columns)))


def _ungrounded(doc_type, fields, blocks):
    """합계 행 없이 채워진 합계 금액 필드 중 문서 글자 어디에도 없거나 항목 한 행의 값을 베낀 것(인쇄되지 않은 합계)."""
    if not blocks or any(is_total(row) for row in _rows(fields, ITEM_TABLE)):  # 글자 근거가 없으면 따지지 않는다
        return []
    return [key for key, meta in doctypes.spec(doc_type)["fields"].items()
            if meta["kind"] == "amount" and "총액" in key and _money(fields.get(key))
            and (not _printed(normalize("amount", fields[key]), blocks) or _copied(doc_type, fields, key))]


def _notes(doc_type, out, blocks):
    """전용 표가 없는 서식에서 소견 문장·비고의 날짜 표시로 치료·검사·수술 내역 행을 만든다(AO 관례)."""
    tables = doctypes.spec(doc_type)["tables"]
    for position, (table, (labels, date_column, name_column)) in enumerate(NOTES.items()):
        if table not in tables:
            continue
        taken = {_key(row[name]) for other, (_, _, name) in list(NOTES.items())[:position]
                 for row in out.get(other) or [] if row.get(name)}
        out[table] = [row for row in out.get(table) or [] if _key(row.get(name_column) or "") not in taken]
        if out.get(table):
            continue
        for _, _, candidate in _candidates(labels, blocks):
            text = normalize("text", candidate)
            if (text and len(_key(text)) >= SENTENCE and not _junk(text)
                    and not any(name in _key(text) for name in taken)):
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
    비급여 칸과 종료일자를 비급여 행의 총액·시작일자에서 채운다.

    세부내역서의 행별 ``급여``는 인쇄된 급여 값만 쓴다(라벨 관례 ⑨) — 총액에서 만들지 않고, 모델이 총액을
    옮겨 적은 값은 지운다. 독립 급여 열이 보이는 서식도 라벨은 급여 값을 두지 않았다(행 약 300개 중 0개).
    급여 열이 없는 서식에서 모델이 계산해 채운 값은 ``_header_columns``가 지운다.
    """
    for row in out.get(ITEM_TABLE) or []:
        if doc_type == "진료비영수증":
            row["항목"] = item(row.get("항목"))
            continue
        if doc_type != "세부내역서":
            return
        if row.get("EDI코드") and row["EDI코드"] == normalize("edi", row.get("EDI명칭")):
            row["EDI코드"] = None  # 명칭이 코드 열까지 밀려 들어오면 원내코드 자리의 코드가 EDI코드다
        code, edi = row.get("원내코드"), row.get("EDI코드")
        if code and (not edi or code == edi):
            row["원내코드"], row["EDI코드"] = None, edi or code
        if not row.get("종료일자") and row.get("시작일자"):
            row["종료일자"] = row["시작일자"]
        if row.get("급여구분") == "급여" and row.get("급여") == row.get("총액"):
            row["급여"] = None
        if row.get("급여구분") == "비급여" and not row.get("비급여") and row.get("총액"):
            row["비급여"] = row["총액"]


def _header_columns(doc_type, out, blocks):
    """머리글로 보아 서식에 없는 금액 열을 비운다.

    - 머리글이 '묶음 제목'이라고 말하는 열은 하위 열의 합일 뿐이다(진료비영수증 급여·비급여).
    - 세부내역서 급여 열은 머리글에 독립 열로 보일 때만 남긴다 — 모델이 총액−비급여를 계산해 채우곤 한다.
    - 진료비영수증 머리글에 소계 열이 있고 전액본인부담 값의 과반이 본인부담금+공단부담금이면 소계를 옮긴 것이다.
    - 세부내역서 머리글이 일수 칸까지 읽혔는데 단가·투여량 낱말(``HEADER_COLUMNS``)이 없으면 이웃 열 값을 옮긴 것이다.
    """
    cells, columns = _headers(blocks), []
    for column, (titles, subs) in GROUPED.items():
        grouped = _grouped(cells, titles, subs)
        if (grouped is True if doc_type == "진료비영수증"
                else doc_type == "세부내역서" and column == "급여" and grouped is not False):
            columns.append(column)
    if doc_type == "진료비영수증" and any("소계" in cell for cell in cells):  # 일부 본인부담의 소계 열(한방 서식)
        rows = [row for row in out.get(ITEM_TABLE) or [] if _money(row.get("전액본인부담"))]
        added = sum(_near(_money(row["전액본인부담"]), sum(_money(row.get(column)) or 0 for column in ("본인부담금", "공단부담금")))
                    for row in rows)
        if added * 2 > len(rows):  # 과반이 본인+공단이면 소계를 옮겨 적은 것이다(오독 행이 섞여도)
            columns.append("전액본인부담")
    if doc_type == "세부내역서" and any("일수" in cell for cell in cells):
        columns += [column for column, words in HEADER_COLUMNS.items()
                    if not any(word in cell for cell in cells for word in words)]
    for row in out.get(ITEM_TABLE) or []:
        row.update(dict.fromkeys(columns))


def _receipt_column(cells):
    """반복·병합된 영수증 머리글 셀을 AO 항목내역 열 이름으로 바꾼다."""
    text = _key(" ".join(str(cell or "") for cell in cells))
    if _OTHER_THAN.search(text):
        return "선택진료료외"
    if "선택진료료" in text:
        return "선택진료료"
    if "전액본인부담" in text:
        return "전액본인부담"
    if "공단부담" in text or "보험자부담" in text:
        return "공단부담금"
    if "본인부담" in text:
        return "본인부담금"
    # 하위 열이 없는 독립된 비급여·급여 칸만 leaf로 본다(GROUPED의 묶음 제목·하위 열 판단을 그대로 쓴다).
    # '비급여'가 '급여'를 부분 문자열로 포함하므로 비급여를 먼저 본다.
    for column in ("비급여", "급여"):
        titles, subs = GROUPED[column]
        if not any(title in text for title in titles):
            continue
        return None if any(sub in text for sub in subs) else column
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


def _shift_target(reference, candidate, column):
    """candidate의 column 값이 사실은 reference의 다른 열 값과 자리가 바뀐 것인지, 맞다면 그 열 이름.

    reference를 열 정체성의 기준으로 삼는다(``_receipt_table``에서는 파서 표, ``check``/``correct``에서는
    Docraft 표). candidate의 column 값이 reference의 같은 열 값과는 다르면서 reference의 다른 열 값
    (0보다 큰 실금액)과 같고, candidate가 그 다른 열에는 아직 같은 값을 갖지 않을 때만 옮길 곳으로
    본다. 그런 열이 둘 이상이면(모호하면) 옮기지 않는다.
    """
    value = _money(candidate.get(column))
    if value is None or value == (_money(reference.get(column)) or 0):
        return None
    hits = [other for other in ITEM_COLUMNS if other != column and _money(reference.get(other)) == value > 0
            and _money(candidate.get(other)) != value]
    return hits[0] if len(hits) == 1 else None


def _moves(base, mine):
    """모델이 이웃 열에 잘못 배정한 금액(비급여 값이 선택진료료 칸에 등) ``{열: 파서 표가 말하는 열}``.

    파서 행이 아는 열(``leaves``)이 둘 미만이면 단서가 부족하므로 비워 둔다.
    """
    if not base or sum(1 for column in ITEM_COLUMNS if column in base) < 2:
        return {}
    return {column: target for column in ITEM_COLUMNS if (target := _shift_target(base, mine, column))}


def _realign(base, mine, moves):
    """mine의 금액을 moves대로 옮기고 떠난 칸은 파서 표 값(없으면 0)으로 둔다."""
    fixed = dict(mine)
    for column, target in moves.items():
        fixed[target] = mine.get(column)
        fixed[column] = (base or {}).get(column) or "0"
    return fixed


def _column_moves(found):
    """행마다 찾은 열 옮김 중 두 행 이상에서 같은 방향으로만 나온 것. 파서 표에 없는 행(합계·기타 등)에도 적용한다."""
    seen = Counter(pair for moves in found for pair in moves.items())
    sources = Counter(column for column, _ in seen)
    return {column: target for (column, target), count in seen.items() if count >= 2 and sources[column] == 1}


def _receipt_table(doc_type, out, blocks):
    """모델이 뭉치거나 빠뜨린 영수증 항목 행을 파서 표 행으로 바로잡는다.

    파서 표는 서식에 인쇄된 순서와 세분 항목명(``주사료_행위료``·``입원료_1인실``)을 그대로 갖고 있다.
    항목명이 겹치지 않게 넉넉히 복원됐을 때만 그 목록을 뼈대로 삼아 모델 행을 제자리에 맞추고
    (값은 모델 쪽을 쓰되 이웃 열로 밀린 값은 파서 표 기준으로 되돌리며, 빈 칸만 파서 표로 메운다),
    뼈대에 없는 모델 행은 뒤에 남긴다. 복원이 부실하면 예전처럼 빠진 항목만 인쇄 순서 자리에 보충한다.
    어느 쪽이든 파서 행과 짝지어진 모델 행의 열 밀림은 되돌리고, 여러 행에서 같은 방향으로 밀렸으면
    파서 표에 없는 행(합계 등)도 같이 되돌린다.
    """
    if doc_type != "진료비영수증":
        return
    rows, rebuilt = out.get(ITEM_TABLE) or [], _receipt_rows(blocks)
    names = [row["항목"] for row in rebuilt]
    rich = len(rebuilt) >= max(2, len(rows)) and len(set(names)) == len(names)
    pairs = (pair_rows(doc_type, ITEM_TABLE, rebuilt, rows, fallback=False) if rich
             else [(_row_of(rebuilt, row.get("항목")), row) for row in rows])
    found = [_moves(base, mine or {}) for base, mine in pairs]
    column = _column_moves(found)
    merged = []
    for (base, mine), moves in zip(pairs, found):
        if mine is not None and base is None:
            moves = {source: target for source, target in column.items()
                     if _money(mine.get(source)) and not _money(mine.get(target))}
        fixed = _realign(base, mine, moves) if mine is not None else None
        merged.append(fixed if not rich or base is None else {
            **base, **{key: value for key, value in (fixed or {}).items() if value is not None and key != "항목"}})
    if rich:
        out[ITEM_TABLE] = merged
        return
    rows = merged
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
    for key, value in _from_idnum(doc_type, out).items():
        if key in fields and not out.get(key):
            out[key] = value
    if "외래/입원" in fields and not out.get("외래/입원"):
        out["외래/입원"] = _enum("외래/입원", out.get("환자정보-환자구분") or "") or None
    if out.get("외래/입원") == "02" and "환자정보-진료종료일" in fields and not out.get("환자정보-진료종료일"):
        out["환자정보-진료종료일"] = out.get("환자정보-진료시작일")  # 외래 영수증은 하루 진료가 관례다(라벨 16/17)
    room = out.get("환자정보(병실)") or ""
    if "환자정보(입통원구분)" in fields and not out.get("환자정보(입통원구분)") and room:
        out["환자정보(입통원구분)"] = "통원" if "외래" in room else "입원" if _WARD.match(room.replace(" ", "")) or "입원" in room else None
    if "사고발생일자" in fields and not out.get("사고발생일자"):
        start = next((out[key] for key in out if "진료시작일" in key and out.get(key)), None)
        out["사고발생일자"] = start or _earliest(out)
    return out


def _from_idnum(doc_type, out):
    """주민번호 뒷자리 첫 숫자로 알 수 있는 성별·생년월일."""
    idnum = next((normalize("idnum", out[key]) for key, meta in doctypes.spec(doc_type)["fields"].items()
                  if meta["kind"] == "idnum" and out.get(key)), None)
    back = (idnum or "").partition("-")[2][:1]
    if not back or back not in "12345678":
        return {}
    century = "20" if back in "3478" else "19"
    return {"생년월일": normalize("date", century + idnum[:6]), **({"성별": "남" if back in "135" else "여"} if back in "123456" else {})}


def _earliest(out):
    dates = [out[key] for key in _ACCIDENT_DATES if out.get(key)]
    dates += [row[column] for rows in out.values() if isinstance(rows, list)
              for row in rows for column in _ACCIDENT_COLUMNS if row.get(column)]
    return min(dates, default=None)


# ── 진료비영수증 항목내역 검사 ──────────────────────────────────────────────

ITEM_TABLE = "항목내역"
ITEM_COLUMNS = ("본인부담금", "공단부담금", "전액본인부담", "비급여", "선택진료료", "선택진료료외", "급여")
TOLERANCE = 100  # 십의 자리 절사 허용 오차(요건 1절)
SHIFT_REACH = 3  # 세로로 밀린 금액을 찾아볼 위아래 행 수
# 합계 필드 → 합계 행에서 더할 열(요건 1절 합계식). 비급여와 선택진료료·선택진료료외는 한쪽만 값을 갖는
# 묶음 제목·하위 열 관계라 함께 더해도 겹치지 않는다.
TOTAL_FIELDS = {
    "진료비총액": ITEM_COLUMNS,
    "환자부담총액": tuple(column for column in ITEM_COLUMNS if column not in ("공단부담금", "급여")),
    "공단부담총액": ("공단부담금",),
}
FIELD_SUMS = {  # 합계 필드 → 구성 필드. 구성 필드가 둘 이상 읽혔을 때 합을 맞춰 본다.
    "진료비총액": ("환자부담총액", "공단부담총액"),
    "납부한금액_합계": ("납부한금액_카드", "납부한금액_현금영수증", "납부한금액_현금"),
    "급여_급여총액": ("급여_본인부담총액", "급여_공단부담총액", "급여_전액본인부담총액"),
    "진료비내역-총액": ("진료비내역-급여본인부담", "진료비내역-공단부담액", "진료비내역-비급여및전액본인부담금"),
    "진료비내역-환자부담총액": ("진료비내역-급여본인부담", "진료비내역-비급여및전액본인부담금"),
}
SWAPS = (("본인부담금", "공단부담금"), ("선택진료료", "선택진료료외"), ("선택진료료", "비급여"),
         ("선택진료료외", "비급여"))  # 모델이 통째로 맞바꿔 읽기 쉬운 이웃 금액 열
HEADER_COLUMNS = {"단가": ("단가", "금액"), "투여량": ("투여량", "두여량", "투약량", "용량")}  # 세부내역서 열 → 머리글 낱말
GROUPED = {  # 열 → (묶음 제목 후보, 하위 열이 있으면 그 열은 독립 열이 아니다)
    "급여": (("급여", "요양급여"), ("본인부담", "공단부담", "전액본인")),
    "비급여": (("비급여",), ("선택진료",)),
}
ITEM_ALIASES = (  # AO 프롬프트의 항목명 정규화 규칙
    (re.compile(r"^입원료.*1인"), "입원료_1인실"),
    (re.compile(r"^입원료.*[23]"), "입원료_2-3인실"),
    (re.compile(r"^입원료.*4인"), "입원료_4인실이상"),
    (re.compile(r"^입원료.*상급"), "입원료_상급병실"),
    (re.compile(r"^(투약|투약및조제료).*행위"), "투약및조제료_행위료"),
    (re.compile(r"^(투약|투약및조제료).*약품"), "투약및조제료_약품비"),
    (re.compile(r"^주사.*행위"), "주사료_행위료"),
    (re.compile(r"^주사.*약품"), "주사료_약품비"),
    (re.compile(r"^식대?$"), "식대"),
    (re.compile(r"^(계|합계|총계|합계금액)$"), "합계"),
    (re.compile(r"^(시행령별표2제4호|국민건강보험법제41조의4)"), "선별급여"),
)
# 건강보험 진료비 계산서·영수증의 표준 항목. 파서 표에서 새 행을 만들 때만 이 목록을 적용한다.
# 모델이 낸 비정형 항목은 버리지 않고 그대로 보존한다.
RECEIPT_ITEM_NAMES = frozenset((
    "진찰료", "입원료", "입원료_1인실", "입원료_2-3인실", "입원료_4인실이상", "입원료_상급병실", "식대",
    "투약및조제료_행위료", "투약및조제료_약품비", "주사료_행위료", "주사료_약품비",
    "처치및수술", "처치및수술료", "검사료", "영상진단료", "방사선치료료", "마취료", "정신요법료",
    "재활및물리치료료", "치료재료대", "전혈및혈액성분제제료", "CT진단료", "MRI진단료", "PET진단료",
    "초음파진단료", "보철교정료", "제증명료", "정액수가", "정액수가요양병원", "포괄수가진료비",
    "65세이상등정액", "선별급여", "기타", "합계",
    "시술및처치료", "한방물리요법료", "한약첩약", "상급병실료",  # 한방진료비 계산서
))
_ITEM_GROUP = re.compile(r"^(필수항목|선택항목|필수|선택|필)")  # 항목명 앞에 붙어 오는 서식의 분류 칸 글자
LUMP_ITEMS = ("정액수가", "65세이상등정액", "질병군포괄수가")  # 항목 행을 묶어 담는 포괄수가 행
_MULTI_AMOUNT = re.compile(r"\d[\d,]*\s+\d")
_OTHER_THAN = re.compile(r"선택진료[료비]?.?외")  # '이외'를 '미외'로 읽는 등 한 글자 OCR 오독을 허용한다
_RECEIPT_ITEM_TEXT = re.compile(r"^[0-9A-Z가-힣_-]{1,24}$")


def _alias(text):
    return next((canonical for pattern, canonical in ITEM_ALIASES if pattern.match(text)), text or None)


def item(name) -> str | None:
    """진료비영수증 항목명을 AO 프롬프트 규칙대로 정규화한다(입원료 1인실 → 입원료_1인실 등).

    서식의 분류 칸 글자가 붙어 온 이름('필주사료_약품비'·'선택항목_CT진단료')은 떼어 낸 나머지가 표준 항목일 때만 뗀다.
    """
    text = re.sub(r"[^0-9A-Za-z가-힣]", "", str(name or ""))
    bare = _alias(_ITEM_GROUP.sub("", text, count=1))
    name = bare if bare in RECEIPT_ITEM_NAMES else _alias(text)
    return name if name in RECEIPT_ITEM_NAMES or name is None or len(name) < 5 else _misread(name)


def _misread(name):
    """표준 항목명과 같은 길이에 한 글자만 다르고 그런 이름이 하나뿐이면 OCR 오독으로 보고 표준 이름을 돌려준다
    ('시행및처치료' → '시술및처치료'). 짧은 이름은 다른 항목과 헷갈리기 쉬워 다섯 글자 이상만 본다."""
    hits = [known for known in RECEIPT_ITEM_NAMES
            if len(known) == len(name) and sum(a != b for a, b in zip(known, name)) == 1]
    return hits[0] if len(hits) == 1 else name


def _money(value) -> int | None:
    """금액을 부호 있는 정수로. ``normalize``가 지우는 음수 부호를 살린다."""
    text = normalize("amount", value)
    if text is None:
        return None
    number = int(float(text))  # 합계식은 원 단위로 따진다(소수점 이하 버림)
    return -number if str(value).strip().startswith("-") else number


def _rows(fields, table):
    """표의 행 목록. AO는 빈 표를 문자열 '[]'로 주기도 하므로 dict 행만 돌려준다."""
    rows = fields.get(table)
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


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


def _master_checks(fields):
    """마스터에 없는 병명코드를 Judge 참고용으로 알린다(교정은 하지 않는다).

    EDI코드는 원내코드가 섞여 들어와 미적중이 28%(76건 평가)라 신호가 되지 않으므로 보지 않는다.
    명칭 불일치(코드는 마스터에 있는데 인쇄 명칭이 마스터 후보들과 다 다른 경우)도 고시 표기와
    인쇄 표기가 달라 오탐이 절반을 넘어 알리지 않는다. difflib 문자열 유사도로 재봐도(sim<임계값이면
    검토 필요), harness-v2가 쓰는 BAAI/bge-m3 임베딩 코사인 유사도로 재봐도(둘 다 76건 평가) 정밀도
    70%를 못 넘는다 — 진단명이 영문으로 인쇄되면 마스터 한글 명칭과 문자열 유사도가 항상 0에 가까워
    이미 맞는 값까지 걸리고(임베딩은 이 경우는 구제하지만 EDI 표기 차이는 그대로 남는다), EDI는 인쇄
    표기(공백·구두점·어순)가 고시와 달라 낮은 유사도가 오류와 구분되지 않는다:

    | 계통 | 대상행 | 방식 | 최고 정밀도 임계값 | 발동 | 참(true) | 거짓(false) | 정밀도 |
    |---|---:|---|---|---:|---:|---:|---:|
    | 병명(kcd) | 35 | difflib | <0.65 | 7 | 2 | 5 | 29% |
    | 병명(kcd) | 35 | 임베딩 | <0.75 | 5 | 2 | 3 | 40% |
    | EDI | 120 | difflib | <0.55 | 43 | 9 | 34 | 21% |
    | EDI | 120 | 임베딩 | <0.60 | 14 | 3 | 11 | 21% |

    임베딩 단독 최고점(kcd 40%, 표본 5행)도, 임베딩<t1 AND difflib<t2 결합 규칙(kcd 100%지만 표본
    1행이라 신뢰 불가, EDI 최고 27%)도 70%에 못 미친다. 자세한 수치는
    [wiki/2026-09-23-master-name-mismatch-flag.md](../wiki/2026-09-23-master-name-mismatch-flag.md).
    """
    code_column, _name_column, system = MASTER_NAMES["병명내역"]
    if not master.ready():
        return []
    return [_flag("code_unknown", f"병명내역 {index}행 병명코드 '{row[code_column]}'가 KCD 마스터에 없다.",
                  key="병명내역", row=index, column=code_column)
            for index, row in enumerate(fields.get("병명내역") or [])
            if row.get(code_column) and not master.names(system, row[code_column])]


DATE_ORDER = (  # (앞 날짜, 뒤 날짜). 뒤 날짜가 앞서면 한쪽을 잘못 읽은 것이다. 표 열 쌍은 행마다 본다.
    ("입원일자", "퇴원일자"), ("진단일", "발급일"), ("초진일", "발급일"), ("초진일", "진단일"),
    ("환자정보-진료시작일", "환자정보-진료종료일"), ("환자정보(진료시작일)", "환자정보(진료종료일)"),
    ("시작일자", "종료일자"),
)
ISSUED = ("발급일", "발행일")  # 문서의 다른 날짜는 발급일보다 늦을 수 없다
LATER_OK = ("생년월일", "퇴원일자")  # 발급일과 앞뒤를 따지지 않는 날짜(퇴원 예정일은 발급일 뒤일 수 있다)
OLDEST = "19000101"


def _date_checks(doc_type, fields):
    """날짜의 앞뒤가 맞지 않거나(입원>퇴원, 시작>종료, 진단>발급) 발급일 뒤·1900년 전인 날짜."""
    spec = doctypes.spec(doc_type)
    dates = {key: normalize("date", fields.get(key)) for key, meta in spec["fields"].items() if meta["kind"] == "date"}
    issued = next((dates[key] for key in ISSUED if dates.get(key)), None)
    found = [_flag("bad_date", f"{key} {value}이 {'1900년 전' if value < OLDEST else f'발급일 {issued} 뒤'}이다.", key=key)
             for key, value in dates.items() if value and key not in ISSUED
             and (value < OLDEST or issued and value > issued and key not in LATER_OK)]
    found += [_flag("bad_date", f"{first} {dates[first]}이 {last} {dates[last]}보다 늦다.", key=first)
              for first, last in DATE_ORDER if dates.get(first) and dates.get(last) and dates[first] > dates[last]]
    for table, columns in spec["tables"].items():
        for index, row in enumerate(_rows(fields, table)):
            row_dates = {column: normalize("date", row.get(column)) for column in columns
                         if doctypes.kind(doc_type, column, table) == "date"}
            found += [_flag("bad_date", f"{table} {index}행 {first} {row_dates[first]}이 {last} {row_dates[last]}보다 늦다.",
                            key=table, row=index, column=first)
                      for first, last in DATE_ORDER if row_dates.get(first) and row_dates.get(last)
                      and row_dates[first] > row_dates[last]]
            found += [_flag("bad_date", f"{table} {index}행 {column} {value}이 발급일 {issued} 뒤다.",
                            key=table, row=index, column=column)
                      for column, value in row_dates.items() if value and issued and value > issued]
    return found


def _id_checks(doc_type, fields):
    """성별·생년월일이 주민번호와 어긋나는지."""
    kinds = {"성별": "enum", "생년월일": "date"}
    return [_flag("id_mismatch", f"{key} '{fields[key]}'이 주민번호로 본 '{value}'와 다르다.", key=key)
            for key, value in _from_idnum(doc_type, fields).items()
            if fields.get(key) and not same(kinds[key], fields[key], value)]


def check(doc_type: str, ao_fields: dict, docraft_fields: dict, blocks: list[dict]) -> list[dict]:
    """문서의 이상 징후 ``{"code", "key", "row"?, "message"}`` 목록. 모든 유형의 날짜·주민번호·병명코드
    검사에 진료비영수증 항목내역 검사를 더한다."""
    found = (_master_checks(ao_fields) + _date_checks(doc_type, ao_fields) + _id_checks(doc_type, ao_fields)
             + _field_sums(ao_fields) + _detail_checks(doc_type, ao_fields) + _class_checks(doc_type, ao_fields)
             + [_flag("ungrounded", f"{key} {ao_fields[key]}이 문서 글자 어디에도 없거나 항목 한 행의 값과 같다. "
                                    "인쇄되지 않은 합계를 계산하거나 베낀 것이면 비운다.", key=key) for key in _ungrounded(doc_type, ao_fields, blocks or [])])
    rows = _rows(ao_fields, ITEM_TABLE)
    if doc_type != "진료비영수증" or not rows:
        return found
    mine = docraft_fields.get(ITEM_TABLE) or []
    for side, side_rows in (("AO", rows), ("Docraft", mine)):
        for index, row in enumerate(side_rows):
            for column in ITEM_COLUMNS:
                if _MULTI_AMOUNT.search(str(row.get(column) or "")):
                    found.append(_flag("multi_amount", f"{side} 표 {index}행 '{column}' 셀에 금액이 둘 이상 들어 있다: "
                                                       f"{row[column]}", row=index, column=column))
    rebuilt = _receipt_rows(blocks)
    for column in _absent_columns(blocks, rebuilt, mine):
        for index, row in enumerate(rows):
            if _money(row.get(column)):
                found.append(_flag("no_column", f"이 표에는 독립된 '{column}' 열이 없으므로 {index}행 "
                                                f"'{row.get('항목')}'의 {column}는 0이어야 한다.", row=index, column=column))
    found += _row_checks(rows, mine)
    found += _shift_checks(rows, mine)
    found += _item_names(rows)
    found += _row_shifts(rows, mine, rebuilt)
    found += _sum_checks(ao_fields, rows)
    return found


def _absent_columns(blocks, rebuilt, mine):
    """서식에 없는 항목내역 금액 열. 머리글이 묶음 제목이라고 확신하는 급여·비급여와, 파서 표 머리글이
    세 열 이상 읽혔는데 거기 없고 Docraft 표도 비워 둔 열이다(머리글 일부를 못 읽은 파서만 믿지 않는다).
    열 전체가 없는 열로 옮겨 가면 열 합이 맞아 합계 검사로는 못 잡는다."""
    cells = _headers(blocks)
    absent = {column for column, (titles, subs) in GROUPED.items() if _grouped(cells, titles, subs) is True}
    form = {column for row in rebuilt for column in row} - {"항목"}
    if len(form) >= 3:
        absent |= {column for column in set(ITEM_COLUMNS) - form if not any(_money(row.get(column)) for row in mine)}
    return sorted(absent)


def _item_names(rows):
    """AO 항목명이 프롬프트 규칙(선별급여 등 이름 변경)이나 한 글자 오독 교정으로 다른 표준 이름이 되는 행."""
    found = []
    for index, row in enumerate(rows):
        name = item(row.get("항목"))
        if name and name != re.sub(r"[^0-9A-Za-z가-힣_-]", "", str(row.get("항목"))):
            found.append(_flag("item_name", f"AO 표 {index}행 항목명 '{row.get('항목')}'은 '{name}'로 적는다.",
                               row=index, name=name))
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
        # 포괄수가 행은 위쪽 항목 행을 다시 담으므로 합계와 같은 것이 정상이다
        copied = next((index for index in range(total) if _amounts(rows[index]) == _amounts(rows[total])
                       and any(_amounts(rows[total])) and not (item(rows[index].get("항목")) or "").startswith(LUMP_ITEMS)),
                      None)
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


def _shift_checks(rows, mine):
    """AO 행의 금액이 같은 항목의 Docraft(룰 적용 후) 행에서는 다른 열에 있으면 자리가 바뀐 것으로 본다.

    Docraft는 이미 ``_receipt_table``에서 파서 표로 열을 바로잡은 뒤라 열 정체성의 기준이 된다.
    룰이 AO 자체를 고칠 확신이 없을 때도 Judge에게는 알린다.
    """
    found = []
    for index, row in enumerate(rows):
        counterpart = _row_of(mine, row.get("항목"))
        if not counterpart:
            continue
        for column in ITEM_COLUMNS:
            target = _shift_target(counterpart, row, column)
            if target:
                found.append(_flag("column_shift", f"AO 표 {index}행 '{row.get('항목')}'의 '{column}' 값이 "
                                                    f"Docraft가 읽은 '{target}' 열의 값과 같다. 자리가 바뀐 것으로 보인다.",
                                    row=index, column=column, target=target))
    return found


def _row_shifts(rows, mine, rebuilt):
    """AO 행의 금액이 같은 열의 다른 행에 있어야 하면(세로 밀림) 그 자리를 알린다. 열 합은 그대로라 합계 검사로는 못 잡는다.

    Docraft가 위아래 ``SHIFT_REACH``행 안에서 그 값을 가진 행이 하나이고, AO는 그 행에 그 값을 갖지 않으며,
    파서 표도 원래 자리가 아닌 그 행에 값을 둘 때만 본다 — Docraft 혼자 밀려 읽은 경우를 AO 오류로 몰지 않는다.
    부호만 다른 값은 같게 본다.
    """
    def amount(row, column):
        return abs(_money((row or {}).get(column)) or 0)

    body = [index for index, row in enumerate(rows) if not is_total(row)]
    theirs = {index: _row_of(mine, rows[index].get("항목")) for index in body}
    base = {index: _row_of(rebuilt, rows[index].get("항목")) for index in body}
    found = []
    for column in ITEM_COLUMNS:
        for index in body:
            value = amount(rows[index], column)
            if not value or amount(theirs[index], column) == value:
                continue
            hits = [other for other in body if other != index and abs(other - index) <= SHIFT_REACH
                    and amount(theirs[other], column) == value != amount(rows[other], column)]
            if len(hits) != 1:
                continue
            target = hits[0]
            if base[index] is None or not (amount(base[target], column) == value != amount(base[index], column)):
                continue
            found.append(_flag("row_shift", f"AO 표 {index}행 '{rows[index].get('항목')}'의 '{column}' {value:,}은 "
                                            f"{target}행 '{rows[target].get('항목')}' 자리 값이다(Docraft·파서 표가 그 행에서 읽었다).",
                               row=index, column=column, target_row=target))
    return found


def _column_sums(rows):
    """``(합계 행 금액|None, 항목 행 열별 합, 포괄수가 여부)``. 포괄수가 행은 위쪽 항목 행을 다시 담으므로
    그런 표는 열별 합이 합계 행과 어긋나는 것이 정상이다."""
    total = next((row for row in rows if item(row.get("항목")) == "합계"), None)
    added = {column: sum(_money(row.get(column)) or 0 for row in rows if not is_total(row)) for column in ITEM_COLUMNS}
    lump = any(any(_amounts(row)) and (item(row.get("항목")) or "").startswith(LUMP_ITEMS) for row in rows)
    return ({column: _money(total.get(column)) or 0 for column in ITEM_COLUMNS} if total else None), added, lump


def _near(a, b):
    return abs(a - b) < TOLERANCE


def _swaps(rows):
    """항목 행 두 금액 열의 합이 합계 행과 어긋나는데 두 열을 통째로 맞바꾸면 둘 다 맞는 열 쌍.

    한 열이 두 쌍에 걸리면(모호하면) 고르지 않는다."""
    stated, added, lump = _column_sums(rows)
    if not stated or lump:
        return []
    pairs = [(a, b) for a, b in SWAPS if added[a] != added[b] and _near(added[a], stated[b]) and _near(added[b], stated[a])
             and not (_near(added[a], stated[a]) and _near(added[b], stated[b]))]
    columns = [column for pair in pairs for column in pair]
    return [pair for pair in pairs if all(columns.count(column) == 1 for column in pair)]


def _swap(rows, pairs):
    """항목 행(합계 행 제외)의 열 쌍 값을 맞바꾼 새 행 목록."""
    rows = [dict(row) for row in rows]
    for row in rows:
        for a, b in pairs if not is_total(row) else ():
            row[a], row[b] = row.get(b), row.get(a)
    return rows


def _sum_checks(fields, rows):
    """요건 1절의 합계식·열별 합과 항목 열 통째 바뀜을 본다. 십의 자리 절사는 허용한다."""
    found = []
    total, added, lump = _column_sums(rows)
    for column, value in (total if total and not lump else {}).items():
        if not _near(value, added[column]):
            found.append(_flag("sum_mismatch", f"합계 행의 '{column}' {value:,}이 항목 행 합 {added[column]:,}과 다르다."))
    stated = total or added
    for field, columns in TOTAL_FIELDS.items():
        value, computed = _money(fields.get(field)), sum(stated[column] for column in columns)
        if value is not None and not _near(value, computed):
            found.append(_flag("sum_mismatch", f"{field} {value:,}이 합계 행의 {'+'.join(columns)} {computed:,}과 다르다.",
                               key=field))
    found += [_flag("column_shift", f"항목 행의 '{a}'·'{b}' 열을 통째로 맞바꾸면 두 열의 합이 합계 행과 맞는다.",
                    column=a, target=b) for a, b in _swaps(rows)]
    return found


def sum_errors(doc_type: str, fields: dict) -> int:
    """합계식 불일치 수. 합계 필드끼리의 식(``FIELD_SUMS``)과, 진료비영수증이면 합계 행·열별 합·합계 필드 식을 센다.
    두 읽기 중 합계식에 더 맞는 쪽을 고르는 데 쓴다(``verify``)."""
    found = _field_sums(fields)
    if doc_type == "진료비영수증" and _rows(fields, ITEM_TABLE):
        found += [flag for flag in _sum_checks(fields, _rows(fields, ITEM_TABLE)) if flag["code"] == "sum_mismatch"]
    return len(found)


def _relations(fields, key=None):
    """합계식(``FIELD_SUMS``)마다 ``(합계 필드, 합계, {읽힌 구성 필드: 값})``. 합계와 구성 필드 둘 이상이 읽힌 식만,
    key를 주면 key가 걸린 식만 낸다."""
    for field, parts in FIELD_SUMS.items():
        value, terms = _money(fields.get(field)), {part: _money(fields.get(part)) for part in parts}
        terms = {part: term for part, term in terms.items() if term is not None}
        if value is not None and len(terms) >= 2 and key in (None, field, *parts):
            yield field, value, terms


def _fits(fields, key, value):
    """key를 value로 두면 key가 걸린 합계식이 모두 맞는지. 따져 볼 식이 없으면 None."""
    checks = [_near(total, sum(terms.values())) for _, total, terms in _relations({**fields, key: str(value)}, key)]
    return all(checks) if checks else None


def _field_sums(fields):
    """인쇄된 합계 필드가 그 구성 필드의 합과 다른지(구성 필드가 둘 이상 읽혔을 때만)."""
    found = []
    for field, value, terms in _relations(fields):
        if not _near(value, sum(terms.values())):
            message = f"{field} {value:,}이 {'+'.join(terms)} {sum(terms.values()):,}과 다르다. 어느 쪽을 잘못 읽었는지 확인한다."
            found += [_flag("sum_mismatch", message, key=key) for key in (field, *terms)]
    return found


def _detail_checks(doc_type, fields):
    """세부내역서 행의 단가×투여량×횟수×일수와 본인+공단(+전액본인)부담이 총액과 맞는지.

    종별 가산(행위료 ×1.2 등)처럼 문서 안 여러 행이 같은 비율로 어긋나면 그 비율도 맞는 것으로 본다."""
    if doc_type != "세부내역서":
        return []
    rows, found, ratios = _rows(fields, ITEM_TABLE), [], {}
    for index, row in enumerate(rows):
        price, total = _money(row.get("단가")), _money(row.get("총액"))
        counts = [normalize("number", row.get(column)) for column in ("횟수", "일수")]
        if price and total and None not in counts:
            dose = float(normalize("number", row.get("투여량")) or 0) or 1
            base = price * float(counts[0]) * float(counts[1])
            if all(abs(total - value) > 1 for value in (base, base * dose)):  # 원 단위 반올림은 맞는 것으로 본다
                ratios[index] = [round(total / value, 2) for value in {base, base * dose} if value]
        parts = [_money(row.get(column)) for column in ("본인부담", "공단부담")]
        if row.get("급여구분") == "급여" and total is not None and None not in parts and any(parts):
            paid = sum(parts) + (_money(row.get("전액본인부담")) or 0)
            if not _near(paid, total):
                found.append(_flag("row_arith", f"{index}행 본인+공단부담 {paid:,}이 총액 {total:,}과 다르다.",
                                   row=index, column="총액"))
    common = {ratio for ratio in {r for rs in ratios.values() for r in rs} if sum(ratio in rs for rs in ratios.values()) >= 3}
    for index, found_ratios in ratios.items():
        if not common & set(found_ratios):
            found.append(_flag("row_arith", f"{index}행 단가×투여량×횟수×일수가 총액 {rows[index]['총액']}과 맞지 않는다.",
                               row=index, column="총액"))
    found.sort(key=lambda flag: flag["row"])
    # 원내코드만 쓰는 병원도 많아 마스터에 없는 EDI코드만으로는 알리지 않고, 행 금액이 넷 중 하나 넘게 틀릴 때 더한다.
    codes = [row["EDI코드"] for row in rows if row.get("EDI코드")]
    unknown = sum(not master.names("edi", code) for code in codes) if master.ready() else 0
    bad = len({flag["row"] for flag in found})
    if len(rows) >= 5 and bad * 4 >= len(rows) and (bad * 2 > len(rows) or unknown * 2 > len(codes)):
        found.append(_flag("low_quality", "문서 품질이 낮아 표 전체를 이미지로 재확인한다(행 금액이 여럿 맞지 않고 "
                                          "EDI코드도 대부분 마스터에 없다)."))
    return found


def _class_checks(doc_type, fields):
    """세부내역서 급여구분이 정규값(급여·비급여)이 아닌 행(AO의 '열추출' 등). 금액 열로 정해지면 그 값을 붙인다 —
    본인·공단·전액본인부담에만 금액이 있으면 급여, 비급여에만 있으면 비급여. 둘 다 있거나 없으면 Judge에 맡긴다."""
    if doc_type != "세부내역서":
        return []
    found = []
    for index, row in enumerate(_rows(fields, ITEM_TABLE)):
        value = row.get("급여구분")
        if not value or value in ENUMS["급여구분"] or is_total(row):
            continue
        paid = any(_money(row.get(column)) for column in ("본인부담", "공단부담", "전액본인부담"))
        unpaid = bool(_money(row.get("비급여")))
        guess = "급여" if paid and not unpaid else "비급여" if unpaid and not paid else None
        found.append(_flag("item_class", f"{index}행 급여구분 '{value}'은 급여·비급여가 아니다."
                                         + (f" 금액 열로 보아 '{guess}'다." if guess else " 이미지로 확인한다."),
                           row=index, column="급여구분", value=guess))
    return found


def correct(doc_type: str, checks: list[dict], ao_fields: dict, docraft_fields: dict) -> dict:
    """확실한 이상만 Judge 없이 룰로 교정한다. ``{key: (교정값, 사유)}``."""
    rows, mine = [dict(row) for row in ao_fields.get(ITEM_TABLE) or []], docraft_fields.get(ITEM_TABLE) or []
    reasons = []
    shifts = [flag for flag in checks if flag["code"] == "row_shift"]
    moved = {(flag["target_row"], flag["column"]): rows[flag["row"]].get(flag["column"]) for flag in shifts}
    for flag in shifts:  # 모두 떼어 낸 뒤 제자리에 놓아야 연쇄 밀림에서 옮긴 값을 다시 지우지 않는다
        rows[flag["row"]][flag["column"]] = "0"
    for (index, column), value in moved.items():
        rows[index][column] = value
    reasons += [f"row_shift: {rows[flag['row']].get('항목')} 행의 {flag['column']}를 "
                f"{rows[flag['target_row']].get('항목')} 행으로 옮겼다" for flag in shifts]
    order = {"column_shift": 0, "item_name": 1, "row_missing": 2}  # 열 통째 바뀜, 칸, 이름, 행 끼우기 순으로 고친다
    for flag in sorted(checks, key=lambda flag: -1 if "target" in flag and "row" not in flag
                       else order.get(flag["code"], 0)):
        row = rows[flag["row"]] if flag.get("row") is not None and flag["row"] < len(rows) else None
        if flag["code"] == "column_shift" and "row" not in flag:
            rows = _swap(rows, [(flag["column"], flag["target"])])
            reasons.append(f"column_shift: 항목 행의 {flag['column']}·{flag['target']} 열을 맞바꿨다")
        elif flag["code"] == "item_class" and row is not None and flag["value"]:
            reasons.append(f"item_class: {row.get('항목')} 행의 급여구분 {row.get('급여구분')}를 {flag['value']}로 고쳤다")
            row["급여구분"] = flag["value"]
        elif flag["code"] == "item_name" and row is not None:
            reasons.append(f"item_name: {row.get('항목')}를 {flag['name']}로 고쳤다")
            row["항목"] = flag["name"]
        elif flag["code"] == "column_shift" and row is not None:
            column, target = flag["column"], flag["target"]
            source = _row_of(mine, row.get("항목"))
            if source and _money(source.get(target)) == _money(row.get(column)) and not _money(row.get(target)):
                row[target], row[column] = row[column], "0"
                reasons.append(f"column_shift: {row.get('항목')} 행의 {column}를 {target}로 옮겼다")
        elif flag["code"] == "row_missing":
            name = flag["item"]
            source = _row_of(mine, name)
            if source and not any(_amounts(source)):
                rows.insert(_insert_at(rows, mine, name), {**source, "항목": name})
                reasons.append(f"row_missing: 금액이 모두 0인 '{name}' 행을 Docraft에서 채웠다")
    fixes = {flag["key"]: (None, f"{flag['code']}: 인쇄되지 않았거나 구성 금액의 합과 다른 급여 합계라 비웠다")
             for flag in checks if flag["key"] in UNPRINTED_NULL
             and (flag["code"] == "ungrounded" or flag["code"] == "sum_mismatch" and flag["key"] in FIELD_SUMS)}
    return {**fixes, **({ITEM_TABLE: (rows, " / ".join(reasons))} if reasons else {})}


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
        rows = [{column: _value(doc_type, column, row.get(column), table) for column in columns} for row in rows]
        out[table] = [row for row in rows if not _hollow(doc_type, table, row)]
    _serials(doc_type, out, blocks or [])
    _fill(doc_type, out, blocks or [])
    _notes(doc_type, out, blocks or [])
    _split_cells(out)
    _receipt_table(doc_type, out, blocks or [])
    for key in set(_ungrounded(doc_type, out, blocks or [])) & set(UNPRINTED_NULL):
        out[key] = None  # 인쇄되지 않은 합계는 계산해 채우지 않는다(AO 관례). 합계 행이 있으면 _totals가 다시 채운다
    _totals(doc_type, out)
    for key in set(FIELD_SUMS) & set(UNPRINTED_NULL):  # 구성 필드 합과 다른 급여총액은 비급여까지 더한 총액을 옮긴 것이다
        if _fits(out, key, out.get(key)) is False:
            out[key] = None
    _header_columns(doc_type, out, blocks or [])
    if doc_type == "진료비영수증":  # 통째로 맞바뀐 이웃 금액 열을 합계 행에 맞춰 되돌린다
        out[ITEM_TABLE] = _swap(out[ITEM_TABLE], _swaps(out[ITEM_TABLE]))
    _period(out)
    out = derive(doc_type, out)  # derive는 라벨 정리(verify_label.conform)도 쓰므로 마스터 교정은 그 뒤에 한다
    _master_names(out)
    return out
