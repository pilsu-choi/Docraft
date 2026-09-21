import { marked } from 'marked'
import type { Block, BlockType } from './types'

export const markdownHtml = (markdown: string) => marked.parse(markdown, { async: false, gfm: true, breaks: true })

export const kinds: Record<BlockType, string> = { text: '텍스트', heading: '제목', table: '표', figure: '그림', marginalia: '여백', formula: '수식' }
// 블록 id는 배열 index다. 추출 필드 grounding과 같은 active/selected 흐름을 타도록 "#index" 경로를 붙인다.
export const blockGrounding = (block: Block, i: number) => ({ ...block, path: `#${i}` })
const escape = (text: string) => text.replace(/[&<>"]/g, c => `&${{ '&': 'amp', '<': 'lt', '>': 'gt', '"': 'quot' }[c]};`)
// OCR 결과에 줄바꿈이 실제 개행 또는 "\n" 문자열로 섞여 온다.
const lines = (html: string) => html.replace(/\\n|\n/g, '<br>')
// 표 rows는 병합 셀 값이 덮는 칸마다 반복된 격자다. spans([행, 열, rowspan, colspan])의 첫 칸만 그리고 나머지 칸은 건너뛴다.
export const tableCells = ({ rows = [], spans = [] }: Block) => {
  const origin = new Map(spans.map(([r, c, rowSpan, colSpan]) => [`${r},${c}`, { rowSpan, colSpan }]))
  const covered = new Set(spans.flatMap(([r, c, rowSpan, colSpan]) => Array.from({ length: rowSpan * colSpan }, (_, k) => `${r + Math.floor(k / colSpan)},${c + k % colSpan}`)))
  return rows.map((row, r) => row.flatMap((text, c) => origin.has(`${r},${c}`) || !covered.has(`${r},${c}`) ? [{ text, rowSpan: 1, colSpan: 1, ...origin.get(`${r},${c}`) }] : []))
}
const spanAttrs = ({ rowSpan, colSpan }: { rowSpan: number; colSpan: number }) => (rowSpan > 1 ? ` rowspan="${rowSpan}"` : '') + (colSpan > 1 ? ` colspan="${colSpan}"` : '')
export const blockHtml = (block: Block) => block.type === 'heading' ? `<h2>${escape(block.text)}</h2>`
  : block.type !== 'table' ? `<p>${lines(escape(block.text))}</p>`
  : block.rows ? `<table>${tableCells(block).map((row, i) => `<tr>${row.map(cell => { const tag = i ? 'td' : 'th'; return `<${tag}${spanAttrs(cell)}>${lines(escape(cell.text))}</${tag}>` }).join('')}</tr>`).join('')}</table>`
  : block.text.replace(/^```\w*\n?|\n?```$/g, '').replace(/\\n/g, '<br>') // PaddleOCR 표는 HTML 원문이며 sandbox iframe 안에서만 렌더링된다.

// 분석 블록을 LandingAI Parse 화면처럼 "번호 - 유형" 카드로 렌더링한다.
export const blocksHtml = (blocks: Block[]) => blocks.map((block, i) => `<section><span class="tag">${i + 1} - ${kinds[block.type] || block.type}${block.page ? ` · p.${block.page}` : ''}</span>${blockHtml(block)}</section>`).join('\n')

// sandbox="" + CSP: 업로드·파싱된 HTML의 스크립트, 폼, 외부 리소스 요청을 모두 막는다.
const style = `<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src data:"><style>body{margin:0;padding:18px 22px;font:14px/1.65 system-ui,sans-serif;color:#1d2b25;word-break:break-word}h1,h2,h3{line-height:1.3;margin:1.1em 0 .5em}table{border-collapse:collapse;margin:12px 0;max-width:100%}th,td{border:1px solid #d7e3dc;padding:6px 10px;text-align:left;vertical-align:top;word-break:keep-all;min-width:2.5em}th,tr:first-child td{background:#f3f8f5;font-weight:600}tr:nth-child(even) td{background:#fafcfb}pre{background:#f6f8f7;padding:12px;overflow:auto}code{font-size:13px}img{max-width:100%}section{border:1px solid #e5ede8;border-radius:8px;padding:10px 14px;margin:0 0 10px;overflow-x:auto}section p,section h2,section table{margin:6px 0 2px}section table{width:100%}.tag{display:inline-block;font-size:11px;font-weight:600;color:#40564c;background:#eef4f1;border-radius:4px;padding:1px 6px}</style>`

export default function Rendered({ html, title }: { html: string; title: string }) {
  return <iframe className="rendered" title={title} sandbox="" srcDoc={style + html} />
}

// JSON 문법 강조: key·문자열·숫자·true/false/null을 색으로 구분한다.
const token = /("(?:\\.|[^"\\])*")(\s*:)?|\b(?:true|false|null)\b|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?/g
export function Json({ value }: { value: unknown }) {
  // 숫자·문자열만 담은 배열(bbox 등)은 한 줄로 접는다. JSON 문자열에는 개행이 없으므로 ",\n" 치환은 안전하다.
  const text = JSON.stringify(value ?? null, null, 2).replace(/\[\n\s*([^[\]{}]*?)\n\s*\]/g, (_, inner: string) => `[${inner.replace(/,\n\s*/g, ', ')}]`), parts: React.ReactNode[] = []
  let last = 0
  for (const m of text.matchAll(token)) {
    parts.push(text.slice(last, m.index), <span key={m.index} className={m[2] ? 'json-key' : m[1] ? 'json-string' : /\d/.test(m[0][0]) || m[0][0] === '-' ? 'json-number' : 'json-literal'}>{m[1] || m[0]}</span>, m[2] || '')
    last = m.index + m[0].length
  }
  return <pre className="output json">{parts}{text.slice(last)}</pre>
}
