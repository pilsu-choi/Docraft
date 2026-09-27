이 Docraft의 목적은 Agentic OCR 2.0이라는 솔루션의 결과를 검증하는 것이다.
Agentic OCR 2.0은 AI Document Extractor 제품이다.
Parse 이후 LLM 을 이용한 key-value 매핑을 이용한 Extract 결과를 제공한다.
여기서 Docraft도 개별 Parse(OCR) + Extract(key-value mapping) 프로세스를 거쳐서 나온 결과를 비교하고 보정하여 최종 JSON을 산출하는 목적에 있다.
단, 현재 LLM을 이용한 Key-value mapping extraction 과정이 성능 튜닝이 필요한 상황이다.
이를 보정하기 위해 rule-base를 이용한 key-value 추출도 고려하고 있는 상황이다.


현재 상황은 데이터 추출 정확도 99%를 보장해야 하는 상황이다.

Agentic OCR 2.0에서 데이터 추출이 정확하다면 상관없겠지만 해당 부분이 미비해 하네스 및 Docraft로 보정해서 99%를 달성해야 하는 상황이다.
