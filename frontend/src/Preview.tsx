import { useEffect, useRef, useState } from 'react'
import * as pdfjs from 'pdfjs-dist'
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
import type { Document, Grounding } from './types'
import './viewer.css'

pdfjs.GlobalWorkerOptions.workerSrc = workerUrl

type Size = { width: number; height: number }

export default function Preview({ doc, fileUrl, selected }: { doc: Document | null; fileUrl: string; selected: Grounding | null }) {
  const [page, setPage] = useState(1), [pages, setPages] = useState(1), [zoom, setZoom] = useState(1)
  const [availableWidth, setAvailableWidth] = useState(0), [natural, setNatural] = useState<Size>({ width: 0, height: 0 })
  const [size, setSize] = useState<Size>({ width: 0, height: 0 }), [pdfReady, setPdfReady] = useState(0)
  const scroll = useRef<HTMLDivElement>(null), canvas = useRef<HTMLCanvasElement>(null)
  const pdf = useRef<pdfjs.PDFDocumentProxy | null>(null)
  const previousRender = useRef<Promise<unknown>>(Promise.resolve())
  const isPdf = !!doc?.media_type?.includes('pdf'), isImage = !!doc?.media_type?.startsWith('image/')

  useEffect(() => { setPage(1); setPages(1); setZoom(1); setNatural({ width: 0, height: 0 }); setSize({ width: 0, height: 0 }) }, [doc?.id])
  useEffect(() => { if (scroll.current) { scroll.current.scrollTop = 0; scroll.current.scrollLeft = 0 } }, [doc?.id, page])
  useEffect(() => { if (selected?.page) setPage(Math.min(selected.page, pages)) }, [selected?.page, pages])
  useEffect(() => {
    const node = scroll.current
    if (!node) return
    const observer = new ResizeObserver(() => setAvailableWidth(Math.max(1, node.clientWidth - 40)))
    observer.observe(node)
    return () => observer.disconnect()
  }, [])
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
  const boxes = [...(doc?.blocks || []).filter((block): block is { page?: number; bbox: number[]; page_size?: number[] } => !!block && typeof block === 'object' && !Array.isArray(block) && Array.isArray((block as { bbox?: unknown }).bbox)).map(block => ({ path: 'parse-block', ...block })), ...(doc?.groundings || [])].filter(g => (g.page || 1) === page)
  const box = (g: Grounding & { page_size?: number[] }) => {
    const b = g.bbox
    if (!b || b.length < 4 || b.some(v => !Number.isFinite(v)) || b[2] <= b[0] || b[3] <= b[1] || !display.width) return null
    const normalized = Math.max(...b) <= 1
    const basis = g.page_size?.length === 2 ? g.page_size : [natural.width, natural.height]
    if (!normalized && (!basis[0] || !basis[1])) return null
    const x = normalized ? display.width : display.width / basis[0]
    const y = normalized ? display.height : display.height / basis[1]
    return { left: b[0] * x, top: b[1] * y, width: (b[2] - b[0]) * x, height: (b[3] - b[1]) * y }
  }
  const overlays = boxes.map((g, i) => { const rect = box(g); return rect && <span key={i} className={`bbox ${selected?.path === g.path ? 'selected' : ''}`} style={rect} /> })

  return <div className="preview"><div className="preview-toolbar"><b>원본 문서</b><div><button disabled={page <= 1} onClick={() => setPage(page - 1)}>‹</button>{page} / {pages}<button disabled={page >= pages} onClick={() => setPage(page + 1)}>›</button><button onClick={() => setZoom(Math.max(.5, zoom - .25))}>−</button>{Math.round(zoom * 100)}%<button onClick={() => setZoom(Math.min(2.5, zoom + .25))}>＋</button></div></div><div className="preview-scroll" ref={scroll}>{doc && fileUrl ? isPdf ? <div className="page-image" style={display}><canvas ref={canvas} />{overlays}</div> : isImage ? <div className="page-image" style={display}><img src={fileUrl} alt={doc.filename} style={display} onLoad={e => setNatural({ width: e.currentTarget.naturalWidth, height: e.currentTarget.naturalHeight })} />{overlays}</div> : <div className="empty">미리보기를 지원하지 않는 파일입니다. <a href={fileUrl} download={doc.filename}>원본 다운로드</a></div> : <div className="empty">파일을 선택하면 원본이 표시됩니다.</div>}</div></div>
}
