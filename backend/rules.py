"""twin reader 플러그인에서 이식한 룰 기반 정규화·추출·후처리.

- ``normalize(kind, value)``: 값 하나를 kind에 맞게 정규화한다(날짜 → YYYYMMDD, 금액 → 숫자 문자열 등).
  비교 가능한 정규형이 없으면 None을 돌려준다.
- ``apply(doc_type, result, blocks)``: ``engine.extract`` 결과(정규 표현, doctypes 참고)에
  파싱 블록(``parsers.parse``의 blocks)을 근거로 룰을 적용해 새 정규 표현을 돌려준다.
  값 정규화, 빠진 필드의 라벨 동의어 기반 보충, 파생 필드(성별·생년월일·사고발생일자 등),
  병명코드 분리, 체크박스 코드값 변환을 포함한다.
- ``same(kind, a, b)``: 두 값이 정규화 후 같은지.
"""


def normalize(kind: str, value) -> str | None:
    raise NotImplementedError


def same(kind: str, a, b) -> bool:
    raise NotImplementedError


def apply(doc_type: str, result: dict, blocks: list[dict]) -> dict:
    raise NotImplementedError
