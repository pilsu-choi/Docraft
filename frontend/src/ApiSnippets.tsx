import { useState } from 'react'
import { Segments } from './ui'

type Step = { title: string; method: 'GET' | 'POST'; path: string; body?: Record<string, unknown>; upload?: boolean; save?: string }
type Lang = 'curl' | 'python' | 'js'
const q = JSON.stringify, note = 'X-API-Key는 서버에 DOCRAFT_API_KEY가 설정된 경우에만 필요합니다.'

// 단계 정의 하나에서 세 언어 스니펫을 만든다.
const steps = (p: string, d: string, s: string): Step[] => [
  { title: '1. 파일 업로드', method: 'POST', path: `/projects/${p}/documents`, upload: true },
  { title: '2. 처리 상태 확인', method: 'GET', path: `/documents/${d}` },
  { title: '3. 단일 문서 추출', method: 'POST', path: `/documents/${d}/extract`, body: { schema_id: s } },
  { title: '4. 여러 문서 일괄 추출', method: 'POST', path: `/projects/${p}/extract`, body: { schema_id: s, document_ids: [d] } },
  { title: '5-1. 문서 결과 내보내기 (format=json|csv|xlsx)', method: 'GET', path: `/documents/${d}/export?format=json`, save: 'result.json' },
  { title: '5-2. 프로젝트 결과 내보내기 (format=json|csv|xlsx)', method: 'GET', path: `/projects/${p}/export?format=xlsx&schema_id=${s}`, save: 'results.xlsx' },
]
const render: Record<Lang, [string, (s: Step) => string]> = {
  curl: [`# ${note}\nBASE=${q(`${location.origin}/api`)}`, s => [`curl -X ${s.method} "$BASE${s.path}"`, '-H "X-API-Key: <API_KEY>"', s.upload && '-F "files=@sample.pdf"', s.body && '-H "Content-Type: application/json"', s.body && `-d '${q(s.body)}'`, s.save && `-o ${s.save}`].filter(Boolean).join(' \\\n  ')],
  python: [`import requests\n\nBASE = ${q(`${location.origin}/api`)}\nHEADERS = {"X-API-Key": "<API_KEY>"}  # ${note}`, s => `r = requests.${s.method.toLowerCase()}(BASE + ${q(s.path)}, headers=HEADERS${s.upload ? ', files=[("files", open("sample.pdf", "rb"))]' : ''}${s.body ? `, json=${q(s.body)}` : ''})\n${s.save ? `open("${s.save}", "wb").write(r.content)` : 'print(r.json())'}`],
  js: [`import { openAsBlob, writeFileSync } from 'node:fs'\n\nconst BASE = ${q(`${location.origin}/api`)}\nconst headers = { 'X-API-Key': '<API_KEY>' } // ${note}\nlet r`, s => `${s.upload ? "const form = new FormData()\nform.append('files', await openAsBlob('sample.pdf'), 'sample.pdf')\n" : ''}r = await fetch(BASE + ${q(s.path)}, { method: '${s.method}', ${s.body ? `headers: { ...headers, 'Content-Type': 'application/json' }, body: JSON.stringify(${q(s.body)})` : `headers${s.upload ? ', body: form' : ''}`} })\n${s.save ? `writeFileSync('${s.save}', Buffer.from(await r.arrayBuffer()))` : 'console.log(await r.json())'}`],
}

export default function ApiSnippets({ projectId, documentId, schemaId, notify, fail }: { projectId: string; documentId?: string; schemaId: string; notify: (message: string) => void; fail: (message: string) => void }) {
  const [lang, setLang] = useState<Lang>('curl'), [head, step] = render[lang]
  const code = [head, ...steps(projectId, documentId || '<DOCUMENT_ID>', schemaId || '<SCHEMA_ID>').map(s => `${lang === 'js' ? '//' : '#'} ${s.title}\n${step(s)}`)].join('\n\n')
  return <><div className="api-head"><Segments label="코드 언어" value={lang} options={[['curl', 'cURL'], ['python', 'Python'], ['js', 'JavaScript']]} onChange={setLang} /><button className="quiet" onClick={() => navigator.clipboard.writeText(code).then(() => notify('코드를 복사했습니다.'), () => fail('클립보드에 복사하지 못했습니다.'))}>코드 복사</button></div><pre className="output api-code">{code}</pre><p className="muted api-note">현재 프로젝트{documentId ? '·선택 문서' : ''}{schemaId ? '·스키마' : ''} ID가 채워져 있습니다. {note}</p></>
}
