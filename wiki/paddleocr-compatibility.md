# PaddleOCR 호환성 조사

## 2026-09-21

현재 실행 환경에는 PaddleOCR나 PaddlePaddle을 설치하지 않는다. Docraft는 원격 공식 hosted API 또는 동일한 full layout HTTP 계약을 제공하는 on-prem 서비스만 호출한다.

### Adapter output contract

서비스 응답의 `result.layoutParsingResults[].markdown.text`를 페이지별 Docraft block으로 정규화한다.

```json
{
  "type": "text",
  "page": 1,
  "bbox": [x1, y1, x2, y2],
  "text": "recognized text",
  "confidence": 0.98,
  "source": "paddleocr"
}
```

빈 문자열은 버리고, 배열 길이가 맞지 않거나 좌표가 없는 항목은 해당 bbox를 `null`로 둔다. OCR 실패/모델 다운로드 실패는 `ParseError`로 표면화하며 provider fallback을 암묵적으로 수행하지 않는다. PDF 이미지 페이지는 페이지 번호를 1-based로 보존한다.

## 원격/호스팅 경로

- Paddle 공식 Python SDK는 로컬 추론을 실행하지 않고 공식 managed API에 작업을 제출한다. 문서 파싱 모델로 `PaddleOCR-VL-1.6` 등을 선택할 수 있고 인증·polling·결과 파싱 오류 타입을 제공한다.
- PaddleOCR-VL 문서는 SiliconFlow와 Novita AI 같은 OpenAI-compatible managed VLM service를 예시로 들지만, 이는 VLM 단계만 담당하며 완전한 문서 파싱 API와 다르다. 완전한 API가 필요하면 공식 API 또는 PaddleOCR-VL service deployment를 사용한다.
- 사내 서비스는 PaddleX serving의 `paddlex --serve --pipeline OCR` 또는 PaddleOCR MCP의 `self_hosted` source로 구성할 수 있다. Docraft adapter는 base URL/API key/model을 설정으로 받고 서비스 응답을 Docraft block 계약으로 변환한다.
- 현재 OpenRouter의 승인된 Qwen 모델은 PaddleOCR 모델이 아니므로 PaddleOCR-VL 대체로 자동 사용하지 않는다. Paddle OCR이 필요하면 공식 API 또는 별도 Paddle self-hosted endpoint를 명시적으로 설정한다.

공식 PaddleOCR-VL/PaddleX 서비스의 full document parsing HTTP 계약은 `POST /layout-parsing`이며 JSON body의 `file`은 서버가 접근 가능한 URL 또는 Base64 파일 내용, `fileType`은 PDF `0`/이미지 `1`이다. 성공 응답은 `result.layoutParsingResults[]` 아래 `prunedResult`와 `markdown.text`를 제공하고, PDF 각 페이지가 결과 원소가 된다. Docraft remote adapter는 업로드 파일을 Base64로 보내고 `markdown.text`를 페이지별 block text로 보존한다. 현재 원격 Markdown block의 bbox는 정직하게 `null`로 두며, HTTP 오류나 누락 결과는 `ParseError`로 반환한다.

공식 근거: [PaddlePaddle macOS pip 설치](https://www.paddlepaddle.org.cn/documentation/docs/en/install/pip/macos-pip_en.html), [PaddleOCR quick start](https://www.paddleocr.ai/main/en/quick_start.html), [PaddleOCR-VL hardware/API service](https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/PaddleOCR-VL.html), [PaddleOCR official Python API](https://www.paddleocr.ai/main/en/version3.x/inference_deployment/serving/paddleocr_official_api/python.html), [PaddleX serving](https://paddlepaddle.github.io/PaddleOCR/main/en/version3.x/deployment/serving.html), [PaddleOCR MCP self-hosted/Ai Studio](https://paddlepaddle.github.io/PaddleOCR/main/en/version3.x/deployment/mcp_server.html), [PaddleOCR/PaddleX/Paddle 호환표](https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/paddleocr_and_paddlex.md), [PaddleOCR 3.3.0 PyPI wheel](https://pypi.org/project/paddleocr/3.3.0/).
