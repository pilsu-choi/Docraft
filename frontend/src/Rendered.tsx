import { marked } from 'marked'

export const markdownHtml = (markdown: string) => marked.parse(markdown, { async: false, gfm: true, breaks: true })

// sandbox="" + CSP: 업로드·파싱된 HTML의 스크립트, 폼, 외부 리소스 요청을 모두 막는다.
const style = `<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src data:"><style>body{margin:0;padding:18px 22px;font:14px/1.65 system-ui,sans-serif;color:#1d2b25;word-break:break-word}h1,h2,h3{line-height:1.3;margin:1.1em 0 .5em}table{border-collapse:collapse;margin:12px 0;max-width:100%}th,td{border:1px solid #d7e3dc;padding:6px 10px;text-align:left}th{background:#f3f8f5}pre{background:#f6f8f7;padding:12px;overflow:auto}code{font-size:13px}img{max-width:100%}</style>`

export default function Rendered({ html, title }: { html: string; title: string }) {
  return <iframe className="rendered" title={title} sandbox="" srcDoc={style + html} />
}
