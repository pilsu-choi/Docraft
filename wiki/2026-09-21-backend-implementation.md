---
type: Implementation Log
title: "Backend P0 implementation (2026-09-21)"
description: "FastAPI 백엔드 P0 최초 구현(SQLite·Tesseract 시기) 기록"
tags: [backend, p0]
status: deprecated
---

# Backend P0 implementation (2026-09-21)

> 현재와 다름: 이후 PostgreSQL 전환([project-workspace-backend](2026-09-21-project-workspace-backend.md))과 PaddleOCR 도입으로 SQLite·Tesseract 내용은 현재와 다르다.

- Added a FastAPI and SQLite service for isolated projects, documents, versioned JSON Schemas, corrections, and audit records.
- Added real PDF, DOCX, XLSX, CSV, text, and optional Tesseract image parsing with normalized blocks and source coordinates where available.
- Added local heuristic and optional OpenAI-compatible schema generation/extraction, JSON Schema validation, grounding, review, approval, retry, and JSON/CSV export APIs.
- Added optional API-key authentication, upload/path checks, async background processing, and original-file serving.
- Verified an end-to-end TXT workflow. A real text PDF produced by the system PDF filter yielded two positioned text blocks; python-docx yielded heading/text/table blocks; openpyxl yielded a table block.
- Verified XLSX table-to-nested-array extraction with per-cell evidence, invalid correction rejection on approval, JSON Pointer and dot-path corrections, JSON/CSV export, and API-key enforcement.
- Verified the complete browser flow in Chrome for both open local mode and enforced API-key mode: create project, upload/parse TXT, generate/select schema, extract, correct, approve, fetch the original through an authenticated Blob URL, and validate the downloaded JSON value.
- Deferred production RBAC, webhooks, retention automation, SDKs, and managed OCR per the PRD's later scope.
