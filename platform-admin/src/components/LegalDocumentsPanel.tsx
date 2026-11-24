import { useEffect, useState } from 'react';

type DocumentSummary = { id: string; title: string; version: string; sha256: string; required: boolean; role: string };
type DocumentFull = DocumentSummary & { body: string };

type Props = { token: string; role: 'dispatcher' | 'admin'; apiBase?: string };

/** Legal documents are drafts until approved and published by VEXA's legal team. */
export default function LegalDocumentsPanel({ token, role, apiBase = '' }: Props) {
  const [docs, setDocs] = useState<DocumentSummary[]>([]);
  const [pending, setPending] = useState<DocumentSummary[]>([]);
  const [history, setHistory] = useState<{ document_id: string; version: string; accepted_at: string }[]>([]);
  const [open, setOpen] = useState<DocumentFull | null>(null);
  const [checked, setChecked] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const headers = { Authorization: `Bearer ${token}` };
  async function fetchJson(path: string, init?: RequestInit) {
    const response = await fetch(`${apiBase}${path}`, { ...init, headers: { ...headers, ...init?.headers } });
    const result = await response.json().catch(() => null);
    if (!response.ok) throw new Error(typeof result?.detail === 'string' ? result.detail : `HTTP ${response.status}`);
    return result;
  }
  async function load() {
    const [items, pendingData, historyData] = await Promise.all([
      fetchJson(`/api/v1/legal/roles/${role}`),
      fetchJson(`/api/v1/legal/account/${role}/pending`),
      fetchJson(`/api/v1/legal/account/${role}/history`),
    ]);
    setDocs(items); setPending(pendingData.pending); setHistory(historyData);
  }
  useEffect(() => {
    let alive = true;
    setDocs([]); setPending([]); setHistory([]); setChecked([]);
    Promise.all([
      fetch(`${apiBase}/api/v1/legal/roles/${role}`).then(r => { if (!r.ok) throw Error('Документы недоступны'); return r.json(); }),
      fetch(`${apiBase}/api/v1/legal/account/${role}/pending`, {headers}).then(r => { if (!r.ok) throw Error('Нужна авторизация'); return r.json(); }),
      fetch(`${apiBase}/api/v1/legal/account/${role}/history`, {headers}).then(r => { if (!r.ok) throw Error('История недоступна'); return r.json(); }),
    ]).then(([items, p, h]) => { if (alive) { setDocs(items); setPending(p.pending); setHistory(h); } })
      .catch(e => { if (alive) setError(String(e)); });
    return () => { alive = false; };
  }, [token, role, apiBase]);
  async function openDocument(doc: DocumentSummary) {
    try { setError(''); setOpen(await fetchJson(`/api/v1/legal/roles/${role}/${encodeURIComponent(doc.id)}`)); }
    catch (e) { setError(String(e)); }
  }
  async function submit() {
    if (!docs.filter(d => d.role === role && d.required).every(d => checked.includes(d.id))) return;
    setBusy(true); setError(''); setNotice('');
    try {
      // The API validates document version and hash from the server-side catalog.
      await fetchJson(`/api/v1/legal/account/${role}/accept`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ selections: docs.filter(d => d.role === role && (d.required || checked.includes(d.id)))
          .map(d => ({ id: d.id, version: d.version, sha256: d.sha256, accepted: true })) }),
      });
      await load(); setChecked([]); setNotice('Подтверждение сохранено.');
    } catch (e) { setError(String(e)); }
    finally { setBusy(false); }
  }
  return <section style={{border:'1px solid #18b7b0',padding:16,borderRadius:12,margin:'16px 0',maxWidth:820}}>
    <h2>Правовые документы VEXA</h2>
    <p style={{color:'#b36a00',fontWeight:700}}>Проекты документов. До утверждения юристом и публикации не являются действующими условиями.</p>
    <p>Редакций, требующих нового подтверждения: {pending.length}. Перед отправкой снова подтвердите все обязательные документы.</p>
    {error && <p role="alert" style={{color:'#c22'}}>{error}</p>}
    {notice && <p role="status">{notice}</p>}
    {docs.map(doc => <div key={doc.id} style={{padding:'8px 0',borderBottom:'1px solid #6664'}}>
      <button type="button" onClick={() => void openDocument(doc)}>{doc.title} · версия {doc.version} (читать полностью)</button>
      {doc.role === role && doc.required && <label style={{display:'block',marginTop:8}}>
        <input type="checkbox" checked={checked.includes(doc.id)} onChange={e => setChecked(old => e.target.checked ? [...old,doc.id] : old.filter(id => id !== doc.id))} />
        Подтверждаю ознакомление и принятие этой редакции
      </label>}
    </div>)}
    {pending.length > 0 && <button type="button" disabled={busy || !docs.filter(d => d.role === role && d.required).every(d => checked.includes(d.id))}
      onClick={() => void submit()} style={{marginTop:12}}>Сохранить подтверждения</button>}
    <details style={{marginTop:16}}><summary>История подтверждений ({history.length})</summary>
      {history.map((h,i)=><p key={i}>{h.document_id} · {h.version} · {h.accepted_at}</p>)}
    </details>
    {open && <div role="dialog" aria-modal="true" aria-label={open.title} style={{position:'fixed',inset:16,background:'#142326',color:'#fff',zIndex:99999,overflow:'auto',padding:20,border:'2px solid #18b7b0',borderRadius:12}}>
      <button type="button" onClick={() => setOpen(null)}>Закрыть документ</button>
      <h2>{open.title}</h2><p>Редакция: {open.version}</p>
      <pre style={{whiteSpace:'pre-wrap',fontFamily:'inherit',lineHeight:1.6}}>{open.body}</pre>
      <button type="button" onClick={() => setOpen(null)}>Вернуться к списку</button>
    </div>}
  </section>;
}
