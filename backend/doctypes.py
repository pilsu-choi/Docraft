"""문서 유형별 필드 정의.

AO(Agentic OCR 2.0) 응답의 ``documents[].doc_type`` 값을 그대로 유형 이름으로 쓴다.
현재 범위는 진단서·소견서·진료비영수증·세부내역서 4종이다.

정규 표현(canonical dict): 스칼라 필드는 AO ``key`` 그대로 최상위 키로 두고,
표(``extracted_tables``)는 표 key → 행(dict) 목록으로 둔다. 예::

    {"진단일": "20230228", "이름": "홍길동", "병명내역": [{"병명코드": "J20", "병명": "급성 기관지염"}]}

``schema(doc_type)``는 이 정규 표현을 만들어 내는 JSON Schema를 돌려주며
``engine.extract``에 그대로 넘긴다. ``kind(doc_type, key)``는 값 정규화·비교 방식을 정한다.

kind별 정규형: date=YYYYMMDD, dates=YYYYMMDD를 ", "로 이은 목록, amount=숫자만(금액·일수·등록번호),
number=소수 허용 수량, idnum=``​``123456-1******, phone=숫자와 하이픈, code=병명코드(대문자),
edi=EDI·원내 코드(공백 없는 대문자),
bool=Y/N, enum=정해진 값 중 하나, text=자유 문자열.
"""

KINDS = ("text", "date", "dates", "amount", "number", "idnum", "phone", "code", "edi", "bool", "enum")

# 표 공통 힌트: twin reader가 합계행을 표에서 빼고 합계 필드로 옮기는 동작을 LLM 쪽에도 알린다.
TABLE_HINT = "개별 항목 행만 담는다. '합계'·'계'·'총계'·'소계' 행과 머리글 행은 넣지 않는다. 값이 없는 열은 null."

# 표 행 근거 제약: 서식마다 인쇄된 항목 집합이 다르므로 모델이 외운 표준 항목 목록으로 채우지 않게 한다.
GROUND_HINT = ("문서에 인쇄된 행만 인쇄된 순서대로 넣는다. 인쇄되지 않은 항목 행을 표준 항목 목록에서 가져와 "
               "덧붙이지 않으며, 금액 칸이 모두 비어 있어도 인쇄된 행은 지우지 않는다. 인쇄된 이름이 표준 항목 "
               "목록에 없더라도 뜻이 비슷한 표준 이름으로 바꾸지 않는다.")

_PATIENT = {  # 진단서·소견서 환자정보 그룹(그룹 키는 평탄화해 최상위로 올린다)
    "환자 등록번호": ("text", "환자 등록번호. '등록번호'·'환자번호'·'ID' 라벨의 값."),
    "차트번호": ("text", "차트번호. '차트번호'·'chart no' 라벨의 값."),
    "이름": ("text", "환자 성명. 한글 이름만, 직함·번호 없이."),
    "환자 주민번호": ("idnum", "환자 주민등록번호. '주민등록번호'·'주민번호'·'생년월일(주민번호)' 라벨의 값. 123456-1234567 형식, 마스킹(*)은 그대로 둔다."),
    "성별": ("enum", "환자 성별. '성별'·'남/여' 표기. 남 또는 여."),
    "생년월일": ("date", "환자 생년월일. YYYYMMDD."),
    "주소": ("text", "환자 주소. '주소' 라벨 뒤 부분만, 전화번호는 빼고."),
    "연락처": ("phone", "환자 연락처. '연락처'·'전화번호'·'HP' 라벨의 값. 숫자와 하이픈만."),
}

_MEDICAL_FIELDS = {  # 진단서·소견서 공통 스칼라(AO 응답 순서)
    "통원일수": ("amount", "통원(외래 진료) 일수. '통원일수'·'외래일수'·'통원 치료일수' 라벨의 값. 숫자만."),
    "진단일": ("date", "진단일. '진단일'·'진단연월일'·'진단년월일'·'진단일자' 라벨의 값. YYYYMMDD."),
    "진료과": ("text", "진료과. '진료과'·'진료과목'·'診療科' 라벨의 값."),
    "임상적추정": ("bool", "'임상적 추정' 체크박스. 체크되어 있으면 Y, 아니면 N."),
    "최종진단": ("bool", "'최종진단' 체크박스. 체크되어 있으면 Y, 아니면 N."),
    "입원일자": ("date", "입원일. '입원일'·'입원기간' 시작일. YYYYMMDD."),
    "퇴원일자": ("date", "퇴원일. '퇴원일'·'입원기간' 종료일. YYYYMMDD."),
    "통원일": ("dates", "통원(외래 진료)한 날짜 전부. YYYYMMDD를 ', '로 이어서."),
    "초진일": ("date", "초진일. '초진일'·'최초진료일'·'최초내원일' 라벨의 값. YYYYMMDD."),
    "발급일": ("date", "발급일. '발급일'·'발행일'·'발급연월일'·'작성일' 라벨의 값. YYYYMMDD."),
    "병원명": ("text", "의료기관 명칭. '의료기관명'·'요양기관명'·'병원명'·'명칭' 라벨의 값."),
    "병원주소": ("text", "의료기관 주소. '주소'·'소재지' 라벨의 값."),
    "병원연락처": ("phone", "의료기관 전화번호. FAX 번호는 빼고 숫자와 하이픈만."),
    "면허번호": ("amount", "의사 면허번호. '면허번호'·'면허 제' 라벨의 값. 숫자만."),
    "의사명": ("text", "작성 의사 성명. 한글 이름만, '의사'·'(인)'·면허번호 제외."),
    **_PATIENT,
}

_MEDICAL_TABLES = {
    "병명내역": {
        "병명코드": ("code", "질병분류기호(KCD 코드). 영문 1자 + 숫자 2~5자리, 소수점 뒤 1~2자리 가능. 예: J20.9. " + TABLE_HINT),
        "병명": ("text", "진단명. 코드 표기는 빼고 병명만. " + TABLE_HINT),
    },
    "수술내역": {
        "수술일자": ("date", "수술일. YYYYMMDD. " + TABLE_HINT),
        "수술명": ("text", "수술명. " + TABLE_HINT),
    },
    "검사내역": {
        "검사일": ("date", "검사일. YYYYMMDD. " + TABLE_HINT),
        "검사명": ("text", "검사명. " + TABLE_HINT),
    },
    "치료내역": {
        "치료일": ("date", "치료일. YYYYMMDD. " + TABLE_HINT),
        "치료명": ("text", "치료 내용. " + TABLE_HINT),
    },
    "행위내역": {
        "행위일": ("date", "처치·행위일. YYYYMMDD. " + TABLE_HINT),
        "행위명": ("text", "처치·행위명. " + TABLE_HINT),
    },
}

# 진료비영수증만 AO 스키마가 최종 합계 행을 표 안에 두므로 공통 TABLE_HINT 대신 이 힌트를 쓴다.
RECEIPT_HINT = ("마지막 최종 계·합계 행은 항목 '합계'로 표에 넣고, 소계·중간소계·절사 전 합계·상한액초과금 행은 넣지 않는다. "
                "머리글 행도 넣지 않는다. 값이 없는 열은 0.")

_RECEIPT_ITEM = {  # 진료비영수증 항목내역 열(항목 외에는 모두 금액)
    "항목": ("text", "표의 항목 칸에 인쇄된 진료 항목 구분명. 표준 목록에 없는 이름(의학료·혈액진단료 등)도 "
                     "인쇄된 대로 적는다. 금액이 모두 빈칸·0인 행도 빠뜨리지 않는다. "
                     "입원료 1인실→입원료_1인실, 2·3인실→입원료_2-3인실, 4인실 이상→입원료_4인실이상, "
                     "투약·주사의 행위료·약품비→투약및조제료_행위료·주사료_약품비 식으로 잇고, 최종 계·합계→합계. " + RECEIPT_HINT),
    "본인부담금": ("amount", "급여 본인부담금. 숫자만. " + RECEIPT_HINT),
    "공단부담금": ("amount", "급여 공단부담금. 숫자만. " + RECEIPT_HINT),
    "전액본인부담": ("amount", "급여 전액본인부담. 숫자만. " + RECEIPT_HINT),
    "급여": ("amount", "하위 열 없는 독립된 요양급여 열의 값만. 요양급여가 본인부담금·공단부담금·전액본인부담을 "
                       "묶는 제목이면 0. 숫자만. " + RECEIPT_HINT),
    "선택진료료": ("amount", "비급여 중 선택진료료. 숫자만. " + RECEIPT_HINT),
    "선택진료료외": ("amount", "비급여 중 선택진료료 외. 숫자만. " + RECEIPT_HINT),
    "비급여": ("amount", "하위 열 없는 독립된 비급여 열의 값만. 비급여가 선택진료료·선택진료료외를 묶는 제목이면 0. "
                        "숫자만. " + RECEIPT_HINT),
}

_DETAIL_ITEM = {  # 세부내역서 항목내역 19열
    "항목": ("text", "진료 항목 구분명. 합계·소계 행은 표에 넣지 않는다."),
    "시작일자": ("date", "항목 시작일. YYYYMMDD. " + TABLE_HINT),
    "종료일자": ("date", "항목 종료일. 종료일 칸이 따로 없으면 시작일자와 같다. YYYYMMDD. " + TABLE_HINT),
    "원내코드": ("edi", "원내(병원 자체) 코드. 코드 열이 하나뿐이면 그 값은 EDI코드에 적고 여기는 null. " + TABLE_HINT),
    "EDI코드": ("edi", "EDI 코드. '코드'·'청구코드'·'표준코드'·'수가코드'·'EDI코드' 열. " + TABLE_HINT),
    "EDI명칭": ("text", "EDI 명칭. '명칭'·'항목명'·'EDI명칭' 열. 표준 수가 명칭으로 바꾸지 않는다. "
                        "[UNK] 표기는 지운다. " + TABLE_HINT),
    "투여량": ("number", "1회 투여량. 소수 가능. " + TABLE_HINT),
    "단가": ("amount", "단가. '금액'·'단가' 열. 숫자만. " + TABLE_HINT),
    "횟수": ("number", "1일 투여(실시) 횟수. " + TABLE_HINT),
    "일수": ("number", "투여(실시) 일수. " + TABLE_HINT),
    "총액": ("amount", "항목 총액(금액). 숫자만. " + TABLE_HINT),
    "급여구분": ("enum", "급여 또는 비급여. '비급'은 비급여로 본다."),
    "급여": ("amount", "급여 금액. 급여구분이 급여면 총액과 같다. 숫자만. " + TABLE_HINT),
    "본인부담": ("amount", "급여 본인부담금. 숫자만. " + TABLE_HINT),
    "공단부담": ("amount", "급여 공단부담금. 숫자만. " + TABLE_HINT),
    "전액본인부담": ("amount", "급여 전액본인부담금. 숫자만. " + TABLE_HINT),
    "비급여": ("amount", "비급여 금액. 숫자만. " + TABLE_HINT),
    "선택진료료": ("amount", "선택진료료. 숫자만. " + TABLE_HINT),
    "선택진료료외": ("amount", "선택진료료 외. 숫자만. " + TABLE_HINT),
}

_SPEC = {
    "진단서": (_MEDICAL_FIELDS, _MEDICAL_TABLES),
    "소견서": (_MEDICAL_FIELDS, _MEDICAL_TABLES),
    "진료비영수증": ({
        "외래/입원": ("enum", "진료 형태 코드. 입원이면 01, 외래(통원)면 02."),
        "공단부담총액": ("amount", "공단부담금 총액. 숫자만."),
        "발행일": ("date", "영수증 발행일. '발행일'·'발급일'·'영수일자' 라벨의 값. YYYYMMDD."),
        "상환액초과금": ("amount", "본인부담상한액 초과금. 숫자만."),
        "사고발생일자": ("date", "사고(진료 개시) 발생일. 진료시작일과 같다. YYYYMMDD."),
        "의료기관정보-명칭": ("text", "의료기관 명칭. '의료기관명'·'요양기관명'·'명칭' 라벨의 값."),
        "의료기관정보-사업자등록번호": ("amount", "사업자등록번호. 숫자만."),
        "의료기관정보-요양기관종류": ("text", "요양기관 종류(종합병원·의원 등)."),
        "의료기관정보-주소": ("text", "의료기관 주소."),
        "환자정보-성명": ("text", "환자 성명. 한글 이름만."),
        "환자정보-진료과": ("text", "진료과목."),
        "환자정보-질병군(DRG)번호": ("text", "질병군(DRG) 번호."),
        "환자정보-진료시작일": ("date", "진료기간 시작일. YYYYMMDD."),
        "환자정보-진료종료일": ("date", "진료기간 종료일. YYYYMMDD."),
        "환자정보-환자구분": ("text", "환자 구분(건강보험·보험외래·급여 등) 표기 그대로."),
        "환자정보-환자등록번호": ("text", "환자 등록번호."),
        "납부한금액_카드": ("amount", "납부한 금액 중 카드. 숫자만."),
        "납부한금액_현금영수증": ("amount", "납부한 금액 중 현금영수증. 숫자만."),
        "납부한금액_현금": ("amount", "납부한 금액 중 현금. 숫자만."),
        "납부한금액_합계": ("amount", "납부한 금액 합계. 숫자만."),
        "납부할금액": ("amount", "납부할 금액. 숫자만."),
        "이미납부한금액": ("amount", "이미 납부한 금액. 숫자만."),
        "진료비총액": ("amount", "진료비 총액. 숫자만."),
        "환자부담총액": ("amount", "환자부담총액. 숫자만."),
    }, {"항목내역": _RECEIPT_ITEM}),
    "세부내역서": ({
        "사고발생일자": ("date", "사고(진료 개시) 발생일. 진료시작일과 같다. YYYYMMDD."),
        "환자정보(환자등록번호)": ("text", "환자 등록번호."),
        "환자성명": ("text", "환자 성명. 한글 이름만."),
        "환자정보(진료시작일)": ("date", "진료기간 시작일. YYYYMMDD."),
        "환자정보(진료종료일)": ("date", "진료기간 종료일. YYYYMMDD."),
        "환자정보(병실)": ("text", "병실 표기(예: 1203호, 8W/865). 외래면 '외래'."),
        "환자정보(입통원구분)": ("enum", "입원 또는 통원. 병실이 있으면 입원, 외래면 통원."),
        "영수증진료형태(환자구분)": ("text", "환자 구분(건강보험·의료급여·일반 등) 표기 그대로."),
        "급여_본인부담총액": ("amount", "급여 본인부담금 합계. 숫자만."),
        "급여_공단부담총액": ("amount", "급여 공단부담금 합계. 숫자만."),
        "급여_전액본인부담총액": ("amount", "급여 전액본인부담 합계. 숫자만."),
        "급여_급여총액": ("amount", "급여 합계. 숫자만."),
        "선택진료료총액": ("amount", "선택진료료 합계. 숫자만."),
        "선택진료료외총액": ("amount", "선택진료료 외 합계. 숫자만."),
        "비급여총액": ("amount", "비급여 합계. 숫자만."),
    }, {"항목내역": _DETAIL_ITEM}),
}

ENUMS = {  # 필드 → 정규값: [동의어]. rules가 값 매핑에 쓰고 schema가 enum 목록에 쓴다.
    "성별": {"남": ["남", "남자", "m", "man", "male", "1"], "여": ["여", "여자", "f", "w", "woman", "female", "2"]},
    "외래/입원": {"01": ["01", "입원", "입원환자"], "02": ["02", "외래", "통원", "외래환자"]},
    "환자정보(입통원구분)": {"통원": ["통원", "외래"], "입원": ["입원"]},
    "급여구분": {"비급여": ["비급여", "비급", "비"], "급여": ["급여", "급"]},
}


DOC_TYPES: dict[str, dict] = {
    name: {
        "fields": {key: {"kind": k, "description": d, "enum": sorted(ENUMS[key]) if key in ENUMS else None}
                   for key, (k, d) in fields.items()},
        "tables": {table: {col: {"kind": k, "description": d, "enum": sorted(ENUMS[col]) if col in ENUMS else None}
                           for col, (k, d) in cols.items()}
                   for table, cols in tables.items()},
    }
    for name, (fields, tables) in _SPEC.items()
}
"""유형 이름 → {"fields": {key: {"kind": str, "description": str, "enum": [...]|None}},
"tables": {table_key: {col_key: {"kind": str, "description": str}}}}"""


# 유형별 표 힌트. 없으면 TABLE_HINT. 항목 행이 서식마다 다른 두 유형에만 근거 제약을 덧붙인다.
HINTS = {"진료비영수증": f"{RECEIPT_HINT} {GROUND_HINT}", "세부내역서": f"{TABLE_HINT} {GROUND_HINT}"}


def _property(meta):
    prop = {"type": ["string", "null"], "description": meta["description"]}
    if meta["enum"]:
        prop["enum"] = [*meta["enum"], None]
    return prop


def schema(doc_type: str) -> dict:
    """유형의 JSON Schema. properties 순서는 AO 응답의 필드 순서를 따른다."""
    spec = DOC_TYPES[doc_type]
    properties = {key: _property(meta) for key, meta in spec["fields"].items()}
    for table, cols in spec["tables"].items():
        properties[table] = {
            "type": "array",
            "description": f"{table}. {HINTS.get(doc_type, TABLE_HINT)}",
            "items": {"type": "object",
                      "properties": {col: _property(meta) for col, meta in cols.items()},
                      "required": list(cols)},
        }
    return {"title": doc_type, "type": "object", "properties": properties, "required": list(properties)}


def spec(doc_type: str) -> dict:
    """유형 정의. 모르는 유형이면 빈 정의를 돌려준다."""
    return DOC_TYPES.get(doc_type) or {"fields": {}, "tables": {}}


def kind(doc_type: str, key: str, table: str | None = None) -> str:
    """필드(또는 표 열)의 kind. 정의에 없으면 ``"text"``."""
    source = spec(doc_type)["tables"].get(table, {}) if table else spec(doc_type)["fields"]
    return source.get(key, {}).get("kind", "text")
