"""문서 유형별 필드 정의.

AO(Agentic OCR 2.0) 응답의 ``documents[].doc_type`` 값을 그대로 유형 이름으로 쓴다.
현재 범위는 진단서·소견서·진료비영수증·세부내역서 4종이다.

정규 표현(canonical dict): 스칼라 필드는 AO ``key`` 그대로 최상위 키로 두고,
표(``extracted_tables``)는 표 key → 행(dict) 목록으로 둔다. 예::

    {"진단일": "20230228", "이름": "홍길동", "병명내역": [{"병명코드": "J20", "병명": "급성 기관지염"}]}

``schema(doc_type)``는 이 정규 표현을 만들어 내는 JSON Schema를 돌려주며
``engine.extract``에 그대로 넘긴다. ``kind(doc_type, key)``는 값 정규화·비교 방식을 정한다.
"""

KINDS = ("text", "date", "dates", "amount", "number", "idnum", "phone", "code", "bool", "enum")

DOC_TYPES: dict[str, dict] = {}
"""유형 이름 → {"fields": {key: {"kind": str, "description": str, "enum": [...]|None}},
"tables": {table_key: {col_key: {"kind": str, "description": str}}}}"""


def schema(doc_type: str) -> dict:
    """유형의 JSON Schema. properties 순서는 AO 응답의 필드 순서를 따른다."""
    raise NotImplementedError


def kind(doc_type: str, key: str, table: str | None = None) -> str:
    """필드(또는 표 열)의 kind. 정의에 없으면 ``"text"``."""
    raise NotImplementedError
