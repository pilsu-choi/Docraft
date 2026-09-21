import { useEffect, useRef, useState } from 'react'
import * as pdfjs from 'pdfjs-dist'
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
import Rendered, { blockGrounding, markdownHtml } from './Rendered'
import type { Document, Grounding } from './types'
import './viewer.css'

pdfjs.GlobalWorkerOptions.workerSrc = workerUrl

type Size = { width: number; height: number }

export default function Preview({ doc, fileUrl, active, selected, onHover, onSelect }: { doc: Document | null; fileUrl: string; active: Grounding | null; selected: Grounding | null; onHover: (g: Grounding | null) => void; onSelect: (g: Grounding) => void }) {
  const [page, setPage] = useState(1), [pages, setPages] = useState(1), [zoom, setZoom] = useState(1)
  const [availableWidth, setAvailableWidth] = useState(0), [natural, setNatural] = useState<Size>({ width: 0, height: 0 })
  const [size, setSize] = useState<Size>({ width: 0, height: 0 }), [pdfReady, setPdfReady] = useState(0)
  const scroll = useRef<HTMLDivElement>(null), canvas = useRef<HTMLCanvasElement>(null)
  const pdf = useRef<pdfjs.PDFDocumentProxy | null>(null)
  const previousRender = useRef<Promise<unknown>>(Promise.resolve())
  const [markup, setMarkup] = useState('')
  const isPdf = !!doc?.media_type?.includes('pdf'), isImage = !!doc?.media_type?.startsWith('image/')
  const isHtml = /\.html?$/i.test(doc?.filename || ''), isMarkdown = /\.md$/i.test(doc?.filename || '')

  useEffect(() => { setPage(1); setPages(1); setZoom(1); setNatural({ width: 0, height: 0 }); setSize({ width: 0, height: 0 }) }, [doc?.id])
  useEffect(() => { if (scroll.current) { scroll.current.scrollTop = 0; scroll.current.scrollLeft = 0 } }, [doc?.id, page])
  useEffect(() => { if (active?.page) setPage(Math.min(active.page, pages)) }, [active?.page, pages])
  useEffect(() => {
    const node = scroll.current
    if (!node) return
    const observer = new ResizeObserver(() => setAvailableWidth(Math.max(1, node.clientWidth - 40)))
    observer.observe(node)
    return () => observer.disconnect()
  }, [])
  useEffect(() => {
    let cancelled = false
    setMarkup('')
    if ((isHtml || isMarkdown) && fileUrl) fetch(fileUrl).then(r => r.text()).then(text => { if (!cancelled) setMarkup(isHtml ? text : markdownHtml(text)) }).catch(() => {})
    return () => { cancelled = true }
  }, [fileUrl, isHtml, isMarkdown])
  useEffect(() => {
    pdf.current = null
    if (!isPdf || !fileUrl) return
    const loading = pdfjs.getDocument(fileUrl)
    let cancelled = false
    loading.promise.then(value => { if (!cancelled) { pdf.current = value; setPages(value.numPages); setPdfReady(current => current + 1) } }).catch(() => {})
    return () => { cancelled = true; pdf.current = null; void loading.destroy() }
  }, [fileUrl, isPdf])
  useEffect(() => {
    if (!isPdf || !pdf.current || !availableWidth) return
    let cancelled = false, rendering: ReturnType<pdfjs.PDFPageProxy['render']> | undefined
    const document = pdf.current
    ;(async () => {
      await previousRender.current.catch(() => {})
      if (cancelled) return
      const source = await document.getPage(Math.min(page, document.numPages))
      if (cancelled) return
      const base = source.getViewport({ scale: 1 })
      const width = Math.min(base.width, availableWidth) * zoom
      const scale = width / base.width
      const viewport = source.getViewport({ scale })
      const target = canvas.current
      if (!target || cancelled) return
      const ratio = window.devicePixelRatio || 1
      target.width = Math.ceil(viewport.width * ratio)
      target.height = Math.ceil(viewport.height * ratio)
      target.style.width = `${viewport.width}px`
      target.style.height = `${viewport.height}px`
      setNatural({ width: base.width, height: base.height })
      setSize({ width: viewport.width, height: viewport.height })
      rendering = source.render({ canvasContext: target.getContext('2d')!, viewport, transform: [ratio, 0, 0, ratio, 0, 0] })
      previousRender.current = rendering.promise
      await rendering.promise
    })().catch(error => { if (!cancelled && error?.name !== 'RenderingCancelledException') console.error('PDF preview render failed', error) })
    return () => { cancelled = true; rendering?.cancel() }
  }, [isPdf, pdfReady, page, availableWidth, zoom])

  const imageSize = isImage && natural.width && availableWidth ? {
    width: Math.min(natural.width, availableWidth) * zoom,
    height: natural.height * Math.min(natural.width, availableWidth) / natural.width * zoom,
  } : { width: 0, height: 0 }
  const display = isImage ? imageSize : size
  useEffect(() => {
    const node = scroll.current, target = selected && node?.querySelector(`.bbox[data-path="${CSS.escape(selected.path)}"]`)
    if (!selected || !node || !target) return
    const outer = node.getBoundingClientRect(), inner = target.getBoundingClientRect()
    node.scrollBy({ left: inner.left + inner.width / 2 - outer.left - outer.width / 2, top: inner.top + inner.height / 2 - outer.top - outer.height / 2, behavior: 'smooth' })
  }, [selected, page, display.width, display.height])
  const boxes = [...(doc?.blocks || []).map(blockGrounding).filter(g => Array.isArray(g.bbox)), ...(doc?.groundings || [])].filter(g => (g.page || 1) === page)
  const box = (g: Grounding & { page_size?: number[] }) => {
    const b = g.bbox
    if (!b || b.length < 4 || b.some(v => !Number.isFinite(v)) || b[2] <= b[0] || b[3] <= b[1] || !display.width) return null
    // PDF blocks and their groundings use page points, even when every value is < 1.
    // Only image boxes without an explicit page size may use 0–1 coordinates.
    const normalized = isImage && !g.page_size && Math.max(...b) <= 1
    const basis = g.page_size?.length === 2 ? g.page_size : [natural.width, natural.height]
    if (!normalized && (!basis[0] || !basis[1])) return null
    const x = normalized ? display.width : display.width / basis[0]
    const y = normalized ? display.height : display.height / basis[1]
    return { left: b[0] * x, top: b[1] * y, width: (b[2] - b[0]) * x, height: (b[3] - b[1]) * y }
  }
  // 분석 블록은 유형별 색, 추출 필드 근거는 기존 강조색. 둘 다 hover·click이 같은 active/selected로 이어진다.
  const overlays = boxes.map((g, i) => { const rect = box(g); return rect && <span key={i} className={`bbox ${'type' in g ? `block t-${g.type}` : 'field'} ${active?.path === g.path ? 'selected' : ''}`} style={rect} data-path={g.path} title={`${g.path}${g.text ? ` · ${g.text}` : ''}`} onMouseEnter={() => onHover(g)} onMouseLeave={() => onHover(null)} onClick={() => onSelect(g)} /> })

  return <div className="preview"><div className="preview-toolbar"><b>원본 문서</b><div><button disabled={page <= 1} onClick={() => setPage(page - 1)}>‹</button>{page} / {pages}<button disabled={page >= pages} onClick={() => setPage(page + 1)}>›</button><button onClick={() => setZoom(Math.max(.5, zoom - .25))}>−</button>{Math.round(zoom * 100)}%<button onClick={() => setZoom(Math.min(2.5, zoom + .25))}>＋</button></div></div><div className="preview-scroll" ref={scroll}>{doc && fileUrl ? isPdf ? <div className="page-image" style={display}><canvas ref={canvas} />{overlays}</div> : isImage ? <div className="page-image" style={display}><img src={fileUrl} alt={doc.filename} style={display} onLoad={e => setNatural({ width: e.currentTarget.naturalWidth, height: e.currentTarget.naturalHeight })} />{overlays}</div> : isHtml || isMarkdown ? markup && <Rendered key={doc.id} html={markup} title={doc.filename} /> : <div className="empty">미리보기를 지원하지 않는 파일입니다. <a href={fileUrl} download={doc.filename}>원본 다운로드</a></div> : <div className="empty">파일을 선택하면 원본이 표시됩니다.</div>}</div></div>
}
