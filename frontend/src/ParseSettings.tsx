import type { ParseOptions } from './types'

const parsers = { auto: '자동', library: '기본 라이브러리', paddle: 'PaddleOCR' }

// 접힌 상태에서도 기본값이 아닌 설정을 한 줄로 보여 준다(예: p.1-3 · PaddleOCR).
export default function ParseSettings({ value, onChange, pdf, ocr }: { value: ParseOptions; onChange: (value: ParseOptions) => void; pdf: boolean; ocr: boolean }) {
  const set = (patch: ParseOptions) => onChange({ ...value, ...patch })
  const summary = [pdf && value.pages?.trim() && `p.${value.pages.trim()}`, value.provider && value.provider !== 'auto' && parsers[value.provider], value.table_format === 'html' && 'HTML 표'].filter(Boolean).join(' · ')
  return <details className="parse-settings"><summary>분석 설정{summary && <small>{summary}</small>}</summary><div className="parse-fields">
    <label>페이지 범위<input value={pdf ? value.pages || '' : ''} placeholder={pdf ? '예: 1-3,5' : 'PDF만 지정 가능'} disabled={!pdf} onChange={e => set({ pages: e.target.value })} /></label>
    <label>파서<select value={value.provider || 'auto'} onChange={e => set({ provider: e.target.value as ParseOptions['provider'] })}>{Object.entries(parsers).map(([key, text]) => <option key={key} value={key} disabled={key === 'paddle' && !ocr}>{key === 'paddle' && !ocr ? `${text} (OCR 미설정)` : text}</option>)}</select></label>
    <label>표 형식<select value={value.table_format || 'markdown'} onChange={e => set({ table_format: e.target.value as ParseOptions['table_format'] })}><option value="markdown">Markdown</option><option value="html">HTML</option></select></label>
  </div>{!ocr && <small className="muted">PaddleOCR는 서버에 OCR 엔진이 설정된 경우에만 선택할 수 있습니다.</small>}</details>
}
