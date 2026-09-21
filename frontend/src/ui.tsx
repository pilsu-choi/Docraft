// 여러 화면에서 함께 쓰는 아이콘, 상태 표기, 세그먼트 전환, 모달.
import { useEffect, useState } from 'react'
export const statusText: Record<string, string> = { queued: '대기 중', parsing: '문서 분석 중', parsed: '분석 완료', extracting: '추출 중', validating: '검증 중', needs_review: '검토 필요', completed: '완료', failed: '처리 실패' }
export function Icon({ name, size = 18 }: { name: 'grid' | 'plus' | 'file' | 'arrow' | 'chevron' | 'refresh' | 'key' | 'spark' | 'check' | 'search' | 'upload' | 'folder' | 'expand' | 'shrink' | 'close'; size?: number }) {
  const paths: Record<typeof name, React.ReactNode> = {
    grid: <><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></>,
    plus: <path d="M12 5v14M5 12h14"/>, file: <><path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><path d="M13 2v7h7M8 14h8M8 18h6"/></>,
    arrow: <path d="M5 12h14m-6-6 6 6-6 6"/>, chevron: <path d="m9 18 6-6-6-6"/>, refresh: <><path d="M20 11a8 8 0 1 0-2.2 6.1"/><path d="M20 4v7h-7"/></>,
    key: <><circle cx="8" cy="15" r="4"/><path d="m11 12 9-9 2 2-3 3 2 2-3 3-2-2-2 2"/></>, spark: <><path d="m12 2 1.8 6.2L20 10l-6.2 1.8L12 18l-1.8-6.2L4 10l6.2-1.8L12 2z"/><path d="m19 17 .6 1.4L21 19l-1.4.6L19 21l-.6-1.4L17 19l1.4-.6L19 17z"/></>,
    check: <path d="m4 12 5 5L20 6"/>, search: <><circle cx="11" cy="11" r="7"/><path d="m16 16 5 5"/></>, upload: <><path d="M12 16V3m-5 5 5-5 5 5"/><path d="M4 16v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3"/></>, folder: <path d="M3 7a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v10H3z"/>,
    expand: <path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/>, shrink: <path d="M4 14h6v6M20 10h-6V4M14 10l7-7M3 21l7-7"/>, close: <path d="M18 6 6 18M6 6l12 12"/>,
  }
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>
}
export function Segments<T extends string>({ label, value, options, onChange }: { label: string; value: T; options: [T, string][]; onChange: (value: T) => void }) {
  return <div className="segments" role="tablist" aria-label={label}>{options.map(([key, text]) => <button key={key} role="tab" aria-selected={value === key} className={value === key ? 'active' : ''} onClick={() => onChange(key)}>{text}</button>)}</div>
}
export function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  const [full, setFull] = useState(false)
  useEffect(() => { const esc = (e: KeyboardEvent) => e.key === 'Escape' && onClose(); addEventListener('keydown', esc); return () => removeEventListener('keydown', esc) }, [onClose])
  return <div className="modal-backdrop" onMouseDown={e => e.target === e.currentTarget && onClose()}><div className={`modal ${full ? 'full' : ''}`} role="dialog" aria-modal="true" aria-label={title}><div className="modal-head"><b>{title}</b><button aria-label={full ? '축소' : '전체 화면'} title={full ? '축소' : '전체 화면'} onClick={() => setFull(!full)}><Icon name={full ? 'shrink' : 'expand'} size={16}/></button><button aria-label="닫기" title="닫기" onClick={onClose}><Icon name="close" size={16}/></button></div><div className="modal-body">{children}</div></div></div>
}
