---
type: Implementation Log
title: "Agentic OCR 2.0.1 fixture conversion"
description: "Agentic OCR 2.0.1 PNG fixture를 텍스트 레이어 포함 PDF로 변환한 절차"
tags: [samples, ocr]
status: stable
---

# Agentic OCR 2.0.1 fixture conversion

The five supplied PNG fixtures are copied without modification to `samples/agentic-ocr-2.0.1-results/images/<document category>/`.

Each image has a corresponding one-page PDF under `samples/agentic-ocr-2.0.1-results/pdf/<document category>/`. The PDF retains the source image and adds an invisible Korean/English text layer recognized by macOS Vision. `PyMuPDF` embeds the macOS `AppleGothic.ttf` font for that layer so the existing `pypdf` parser can recover Korean Unicode text while the configured remote OCR service remains optional.

Fixture binaries are ignored through `samples/` in `.gitignore` because they may contain personal medical information. The conversion completed on 2026-09-21 with five copied PNGs and five one-page PDFs across the five source categories. SHA-256 checks confirmed every copied PNG matches its source byte-for-byte. The largest PDF is 12,113,966 bytes, below the default 25 MiB upload limit.

`backend.parsers.parse_pdf` and direct `pypdf` extraction were run against all five generated PDFs using the project's existing environment. Every PDF returned text blocks and at least one Hangul character. The check recorded counts only, without printing or storing fixture text.

To regenerate locally, compile `scripts/vision_ocr_lines.swift` with the installed macOS Swift/Vision frameworks, run it for each image into a temporary JSON file, then run `scripts/ocr_json_to_searchable_pdf.py`. The Python conversion helper requires `PyMuPDF`; temporary JSON is removed after each PDF is written.
