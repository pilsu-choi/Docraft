import { useEffect, useRef } from 'react'
import Rendered, { blockGrounding, blockHtml, kinds, tableCells } from './Rendered'
import type { Block, Grounding } from './types'

// 분석 블록 카드 목록. 카드 hover·click과 원문 bbox hover가 같은 active/selected 상태를 공유한다.
export default function Blocks({ blocks, active, onHover, onSelect }: { blocks: Block[]; active: Grounding | null; onHover: (g: Grounding | null) => void; onSelect: (g: Grounding) => void }) {
  const list = useRef<HTMLDivElement>(null)
  // 원문에서 가리킨 블록 카드가 보이지 않으면 목록 컨테이너만 스크롤한다(페이지는 움직이지 않음).
  useEffect(() => {
    const node = list.current, card = node?.querySelector('.block-card.active')
    if (!node || !card) return
    const outer = node.getBoundingClientRect(), inner = card.getBoundingClientRect()
    if (inner.top < outer.top || inner.bottom > outer.bottom) node.scrollBy({ top: inner.top - outer.top - Math.max(0, outer.height - inner.height) / 2, behavior: 'smooth' })
  }, [active?.path])
  return <div className="block-list" ref={list}>{blocks.map((block, i) => {
    const g = blockGrounding(block, i), text = block.text.replace(/\\n/g, '\n')
    return <section key={i} className={`block-card t-${block.type} ${active?.path === g.path ? 'active' : ''}`} onMouseEnter={() => onHover(g)} onMouseLeave={() => onHover(null)} onClick={() => onSelect(g)}>
      <span className="block-tag">{i + 1} - {kinds[block.type] || block.label || block.type}{block.page ? ` · p.${block.page}` : ''}</span>
      {block.type === 'heading' ? <h3>{text}</h3> : block.type !== 'table' ? <p>{text}</p> : block.rows ? <div className="block-table"><table><tbody>{tableCells(block).map((row, r) => <tr key={r}>{row.map(({ text, rowSpan, colSpan }, c) => { const Cell = r ? 'td' : 'th'; return <Cell key={c} rowSpan={rowSpan} colSpan={colSpan}>{text.replace(/\\n/g, '\n')}</Cell> })}</tr>)}</tbody></table></div> : <Rendered html={blockHtml(block)} title={`표 ${i + 1}`} />}
    </section>
  })}</div>
}
