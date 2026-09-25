import { useMemo, useState } from "react";
import { Search, Lock, LockOpen, Trash2 } from "lucide-react";
import { mediaUrl } from "../api";
import { api } from "../api";
import { Dialog, Empty, MemoryItem, Notice, PageHead } from "../components";
import { fmtDay, useApi } from "../hooks";

export function groupByDay(rows) {
  const out = [];
  for (const m of rows) {
    const d = fmtDay(m.created_at);
    if (!out.length || out[out.length - 1].day !== d) out.push({ day: d, items: [] });
    out[out.length - 1].items.push(m);
  }
  return out;
}

export default function Memories() {
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const { data, setData, loading, error } = useApi(`/api/records?limit=200${query ? `&q=${encodeURIComponent(query)}` : ""}`);
  const [confirm, setConfirm] = useState(null);
  const [undo, setUndo] = useState(null);
  const [filter, setFilter] = useState("all");
  const [view, setView] = useState("list");
  const [open, setOpen] = useState(null);
  const filtered = useMemo(() => (data || []).filter((m) =>
    filter === "all" ? m.kind !== "message" : filter === "private" ? m.is_private : filter === "message" ? m.kind === "message" : m.kind === filter), [data, filter]);
  const groups = useMemo(() => groupByDay(filtered), [filtered]);
  const photos = useMemo(() => (data || []).filter((m) => m.media_url && m.media_mime?.startsWith("image/")), [data]);
  const counts = useMemo(() => {
    const c = { all: 0, photo: 0, voice: 0, text: 0, private: 0, message: 0 };
    for (const m of data || []) { if (m.kind !== "message") c.all++; if (c[m.kind] !== undefined) c[m.kind]++; if (m.is_private) c.private++; }
    return c;
  }, [data]);

  const togglePrivate = async (m) => {
    const r = await api(`/api/records/${m.id}`, { method: "PATCH", body: { is_private: !m.is_private } });
    setData((rows) => rows.map((x) => (x.id === m.id ? r : x)));
  };
  const remove = async (m) => {
    await api(`/api/records/${m.id}`, { method: "DELETE" });
    setData((rows) => rows.filter((x) => x.id !== m.id));
    setConfirm(null); setUndo(m);
  };
  const restore = async () => {
    const r = await api(`/api/records/${undo.id}/restore`, { method: "POST" });
    setData((rows) => [r, ...rows].sort((a, b) => b.created_at.localeCompare(a.created_at)));
    setUndo(null);
  };

  return (
    <div className="stack-lg" style={{ maxWidth: 780 }}>
      <PageHead title="My memories" sub="Everything you have saved, newest first." />
      <form className="askbox" onSubmit={(e) => { e.preventDefault(); setQuery(q.trim()); }}>
        <input className="input" aria-label="Search memories" placeholder="Search, for example: keys, Anita, temple" value={q} onChange={(e) => setQ(e.target.value)} />
        <button className="btn"><Search size={20} aria-hidden="true" />Search</button>
      </form>
      <div className="spread">
        <div className="filters" role="group" aria-label="Show">
          {[["all", "All"], ["photo", "Photos"], ["voice", "Voice notes"], ["text", "Notes"], ["message", "From family"], ["private", "Private"]].map(([k, label]) => (
            counts[k] > 0 || k === "all" ? <button key={k} className={`chip ${filter === k ? "on" : ""}`} aria-pressed={filter === k} onClick={() => { setFilter(k); setView("list"); }}>{label} {counts[k] ? `(${counts[k]})` : ""}</button> : null
          ))}
        </div>
        {photos.length > 0 && (
          <div className="seg" role="group" aria-label="View">
            <button className={view === "list" ? "on" : ""} onClick={() => setView("list")}>List</button>
            <button className={view === "photos" ? "on" : ""} onClick={() => setView("photos")}>Photo wall</button>
          </div>
        )}
      </div>
      {undo && <Notice kind="warn" onClose={() => setUndo(null)} action={<button className="btn sm" onClick={restore}>Undo</button>}>Memory deleted.</Notice>}
      {view === "photos" && (
        <div className="gallery">
          {photos.map((m) => (
            <button key={m.id} className="tile" onClick={() => setOpen(m)} aria-label={m.display_text || "Photo"}>
              <img src={mediaUrl(m.media_url)} alt="" loading="lazy" />
              <span className="cap">{fmtDay(m.created_at)}{m.place ? `, ${m.place.name}` : ""}</span>
            </button>
          ))}
        </div>
      )}
      {open && (
        <Dialog title={fmtDay(open.created_at)} onClose={() => setOpen(null)}>
          <MemoryItem m={open} fullDate />
        </Dialog>
      )}
      {loading && <p className="muted">Loading…</p>}
      {error && <Notice kind="err">{error}</Notice>}
      {!loading && filtered.length === 0 && data?.length > 0 && view === "list" && <Empty title="Nothing here yet">Choose another filter, or save a new memory.</Empty>}
      {!loading && data?.length === 0 && <Empty title={query ? "Nothing matches that search" : "No memories yet"}>{query ? "Try a different word, or ask a question on the Ask page." : "Tap Save to keep your first moment."}</Empty>}
      {view === "list" && groups.map((g) => (
        <section key={g.day} className="panel">
          <h2 className="day-head" style={{ marginTop: 0 }}>{g.day}</h2>
          {g.items.map((m) => (
            <MemoryItem key={m.id} m={m} actions={
              <div className="memory-actions">
                <button className="btn ghost sm" onClick={() => togglePrivate(m)}>
                  {m.is_private ? <><LockOpen size={18} aria-hidden="true" />Share with family</> : <><Lock size={18} aria-hidden="true" />Make private</>}
                </button>
                <button className="btn ghost sm" onClick={() => setConfirm(m)}><Trash2 size={18} aria-hidden="true" />Delete</button>
              </div>
            } />
          ))}
        </section>
      ))}
      {confirm && (
        <Dialog title="Delete this memory?" onClose={() => setConfirm(null)}>
          <p>“{confirm.display_text || "This memory"}”</p>
          <div className="actions">
            <button className="btn quiet" onClick={() => setConfirm(null)}>Keep it</button>
            <button className="btn danger" onClick={() => remove(confirm)}>Delete</button>
          </div>
        </Dialog>
      )}
    </div>
  );
}
