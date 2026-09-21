# Agentic Document Extraction Platform

## 1. Overview

PDF, 이미지, 스캔 문서 등 다양한 비정형 문서를 AI가 이해하고 **Parse → Extract → Validate → Review → Export**까지 수행하는 Agentic Document Extraction 플랫폼을 구축한다.

사용자는 복잡한 OCR 파이프라인이나 규칙 기반 템플릿을 직접 개발하지 않고도 문서를 업로드하고 원하는 데이터 구조를 정의하는 것만으로 **검증 가능한 Structured Data(JSON)**를 생성할 수 있어야 한다.

### 핵심 가치

**Upload → Define → Extract → Verify**

* 복잡한 설정 없이 빠른 문서 데이터화
* 다양한 문서 Layout에 대응하는 Agentic Parsing
* Schema 기반 구조화 데이터 추출
* 원문 근거(Grounding)를 통한 결과 검증
* Human-in-the-loop 기반 수정 및 개선
* API를 통한 Production 연계

---

# 2. Problem & Goal

## Problem

기존 OCR/Document AI 시스템은 다음 문제를 가진다.

* 문서 유형별 OCR 및 Extraction Pipeline 구축 필요
* Layout 변경 시 Template/Rule 유지보수 필요
* 복잡한 표, 다단 문서, 스캔 문서 처리 어려움
* 추출 결과가 원문의 어디에서 나왔는지 확인하기 어려움
* Schema 설계 및 JSON Mapping 작업에 개발 지식 필요
* 오류 발생 시 사람이 검증하는 UX가 부족함

## Goal

사용자가 **문서와 원하는 결과만 정의하면 AI가 나머지 Extraction Pipeline을 자동 구성**하도록 한다.

특히 다음 세 가지를 핵심 경쟁력으로 한다.

**Easy to Build · Easy to Verify · Easy to Integrate**

---

# 3. Target User

### AI / Backend Developer

Document AI Pipeline을 빠르게 구축하고 API로 서비스에 연결하려는 개발자.

### Data / AI Engineer

문서를 구조화하여 RAG, Search, Analytics 등의 데이터 파이프라인에 활용하려는 사용자.

### Business Operator

개발 지식 없이 계약서, 청구서, 보험서류, 의료문서 등의 데이터를 추출하고 검토하려는 사용자.

---

# 4. Core User Flow

```text
Create Project

      ↓

Upload Documents

      ↓

Parse
Document → Markdown / Blocks / Tables / Layout

      ↓

Define Schema
AI Generate / Natural Language / Manual Edit

      ↓

Extract
Document → Structured JSON

      ↓

Validate
Rule / Type / Confidence / Agent Validation

      ↓

Review
Document ↔ Extracted Value Grounding

      ↓

Correct / Approve

      ↓

Export / Deploy
JSON · CSV · API · Webhook
```

전체 UX는 사용자가 현재 **어느 단계에 있는지 항상 명확하게 인지할 수 있는 Step-based Workflow**를 기본으로 한다.

---

# 5. Functional Requirements

## 5.1 Document Upload

Drag & Drop 중심의 간단한 업로드 UI를 제공한다.

지원 대상:

* PDF
* Image
* Office Document
* Spreadsheet

다중 파일 및 Batch Upload를 지원한다.

---

## 5.2 Agentic Parse

문서를 단순 OCR Text가 아닌 구조화된 Document Representation으로 변환한다.

추출 대상:

* Text
* Title / Heading
* Table
* List
* Form
* Figure
* Checkbox
* Page / Section
* Bounding Box

결과는 Markdown 및 Structured JSON 형태로 확인할 수 있어야 한다.

---

## 5.3 Schema Builder

사용자가 추출할 데이터 구조를 정의한다.

세 가지 생성 방식을 제공한다.

**AI Generate**

> "이 문서에서 환자명, 병원명, 진료일자와 진료내역을 추출해줘."

AI가 자동으로 JSON Schema를 생성한다.

**Generate from Document**

업로드된 Sample Document를 분석하여 Schema 후보를 자동 생성한다.

**Manual Editor**

GUI 또는 JSON Schema Editor에서 직접 수정한다.

Field는 다음 정보를 가진다.

```text
Field Name
Type
Description
Required
Array / Object
Validation Rule
Example
```

Schema Version 관리도 지원한다.

---

## 5.4 Agentic Extract

Schema를 기반으로 문서에서 값을 추출한다.

```json
{
  "hospital_name": "ABC Hospital",
  "patient_name": "John Doe",
  "treatment_date": "2026-09-01",
  "total_amount": 120000
}
```

단순 문자열 Matching이 아니라 문서의 문맥과 Layout을 활용하여 값을 판단한다.

Nested Object / Array / Multi-page Table을 지원한다.

---

## 5.5 Grounding & Review

플랫폼의 핵심 UX로 제공한다.

화면을 **Document / Result Split View** 형태로 구성한다.

```text
┌─────────────────────────┬────────────────────────┐
│                         │ Extracted Fields       │
│   Original Document     │                        │
│                         │ Hospital    ABC        │
│   [ Highlight Area ] ←──┼─ Patient     John     │
│                         │ Date        09/01      │
│                         │ Amount      120,000    │
└─────────────────────────┴────────────────────────┘
```

사용자가 추출 값을 클릭하면 원문의 해당 위치를 즉시 Highlight한다.

각 값에 대해 다음 정보를 제공한다.

* Extracted Value
* Confidence
* Source Page
* Bounding Box
* Source Text
* Validation Status

LandingAI가 field-level source grounding을 제공하는 것처럼 결과와 원문 사이의 **추적 가능성(Traceability)**을 핵심 기능으로 취급한다.

---

## 5.6 Validation

Extraction 이후 자동 검증 단계를 제공한다.

지원 방식:

* Required Field
* Data Type
* Regex
* Range
* Enum
* Cross-field Validation
* Custom Prompt Validation
* Reference Data Validation

Low Confidence 또는 Validation Failed 결과는 자동으로 **Needs Review** 상태로 전환한다.

---

## 5.7 Human Feedback

사용자는 잘못 추출된 값을 직접 수정할 수 있다.

```text
AI Result
    ↓
Human Correction
    ↓
Feedback History
    ↓
Agent / Configuration Optimization
```

반복되는 Correction 데이터를 이용하여 Extraction 설정을 개선할 수 있는 구조를 제공한다.

Upstage Studio의 Table View와 Quick Tune처럼 **검수 결과가 다음 Extraction 품질 개선으로 이어지는 Feedback Loop**를 지향한다.

---

## 5.8 API & Integration

Playground에서 만든 Extraction Workflow를 별도 개발 없이 API로 사용할 수 있도록 한다.

제공 기능:

* REST API
* API Key
* Batch API
* Async Job
* Webhook
* SDK
* API Example Generator

UI에서 설정한 Schema와 Extraction Configuration이 API에서도 동일하게 동작해야 한다.

---

# 6. UX / UI Requirements

## Design Principle

**AI Tool처럼 보이기보다 현대적인 Developer SaaS처럼 보여야 한다.**

참고 방향:

Linear / Vercel / Supabase / Retool 스타일의 간결하고 밀도 높은 UI.

### 핵심 Layout

```text
Sidebar
 ├ Projects
 ├ Documents
 ├ Schemas
 ├ Agents
 └ API

Workspace
 ├ Document Viewer
 ├ Schema / Extraction Result
 └ Agent Activity
```

### UX 원칙

**Progressive Disclosure**

처음에는 필요한 기능만 노출하고 Advanced Configuration은 필요할 때 펼친다.

**Visual First**

JSON만 보여주지 않고 Schema와 Extraction Result를 시각적으로 표현한다.

**Instant Feedback**

Parse / Extract 실행 결과가 즉시 Workspace에 반영된다.

**Explainable AI**

AI가 추출한 모든 주요 값은 가능하면 원문 근거와 연결한다.

**Low-Code First**

복잡한 Agent Workflow Canvas를 처음부터 노출하기보다,

> Upload → 원하는 데이터 설명 → 결과 확인

만으로 첫 Extraction을 완료할 수 있도록 한다.

---

# 7. Non-Functional Requirements

### Performance

* 일반 문서 처리 상태 실시간 표시
* 대용량 문서 Async Processing
* Batch Processing 지원

### Reliability

각 Processing Step에 상태를 기록한다.

`Queued → Parsing → Extracting → Validating → Review → Completed / Failed`

실패 단계부터 Retry할 수 있어야 한다.

### Security

* Project 단위 데이터 격리
* RBAC
* API Key 관리
* Audit Log
* Data Retention 설정

Enterprise 환경을 위해 향후 **Private Cloud / On-Premise Deployment**를 고려한 구조로 설계한다.

---

# 8. MVP Scope

MVP에서는 범위를 다음 Pipeline에 집중한다.

**Document Upload → Parse → Schema Builder → Extract → Grounding Review → Export/API**

### P0

* Document Upload
* Agentic Parse
* Markdown / Structured Output
* AI Schema Generation
* Schema Editor
* Schema-based Extraction
* JSON Output
* Document ↔ Result Grounding
* Human Correction
* REST API

### Later

* Document Classification
* Automatic Split
* Validation Agent
* Feedback Learning / Quick Tune
* Workflow Builder
* Connector / MCP
* Batch Automation
* Evaluation Dashboard
* On-Premise Deployment

---

# 9. Success Metrics

제품 성공 여부는 단순 OCR Accuracy보다 **실제 Extraction Workflow 효율**을 중심으로 측정한다.

* Field Extraction Accuracy
* Table Extraction Accuracy
* Schema Generation Success Rate
* Human Correction Rate
* Manual Review Time
* Document Processing Time
* Extraction Failure Rate
* First Extraction까지 걸리는 시간

가장 중요한 Product KPI는:

> **사용자가 문서를 업로드한 뒤 신뢰할 수 있는 Structured Data를 얻기까지 걸리는 시간(Time to Trusted Data)**

으로 정의한다.

