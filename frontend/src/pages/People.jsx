import { useState } from "react";
import { UserRound, Plus } from "lucide-react";
import { api } from "../api";
import { Avatar, Empty, MemoryItem, Notice, PageHead } from "../components";
import { fmtDayInline, useApi } from "../hooks";

export default function People() {
  const { data, loading, error, reload } = useApi("/api/people");
  const [open, setOpen] = useState(null);
  const [form, setForm] = useState({ name: "", relation: "" });
  const [msg, setMsg] = useState(null);
  const mems = useApi(open ? `/api/records?person_id=${open}&limit=20` : null, [open]);

  const add = async (e) => {
    e.preventDefault();
    try { await api("/api/people", { method: "POST", body: form }); setForm({ name: "", relation: "" }); reload(); }
    catch (err) { setMsg(err.message); }
  };

  return (
    <div className="stack-lg">
      <PageHead title="People" sub="The people in your memories, and when you last saw them." />
      {error && <Notice kind="err">{error}</Notice>}
      {loading && <p className="muted">Loading…</p>}
      <div className="grid-2">
        <div className="stack">
          {data?.length === 0 && <Empty title="No people yet">Add a name when you save a memory, or add someone here.</Empty>}
          <div className="people-grid">
            {(data || []).map((p) => (
              <button key={p.id} className={`person-card ${open === p.id ? "on" : ""}`} onClick={() => setOpen(open === p.id ? null : p.id)} aria-expanded={open === p.id}>
                <Avatar name={p.name} large />
                <div>
                  <p><b>{p.name}</b></p>
                  {p.relation && <p className="small muted">{p.relation}</p>}
                  <p className="small muted" style={{ marginTop: 6 }}>{p.memory_count} {p.memory_count === 1 ? "memory" : "memories"}{p.last_seen ? `. Last together ${fmtDayInline(p.last_seen)}${p.last_place ? ` at ${p.last_place}` : ""}` : ""}</p>
                </div>
              </button>
            ))}
          </div>
          {open && (
            <section className="panel">
              <div className="panel-title"><h2>With {(data || []).find((p) => p.id === open)?.name}</h2><button className="btn ghost sm" onClick={() => setOpen(null)}>Close</button></div>
              {mems.loading && <p className="muted">Loading…</p>}
              {(mems.data || []).map((m) => <MemoryItem key={m.id} m={m} />)}
              {mems.data?.length === 0 && <p className="muted">No memories together yet.</p>}
            </section>
          )}
        </div>
        <section className="panel">
          <h2 style={{ marginBottom: 12 }}>Add a person</h2>
          <form className="stack" onSubmit={add}>
            <div className="field"><label htmlFor="pn">Name</label><input id="pn" className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required /></div>
            <div className="field"><label htmlFor="pr">Who they are to you</label><input id="pr" className="input" placeholder="For example: daughter, neighbour" value={form.relation} onChange={(e) => setForm({ ...form, relation: e.target.value })} /></div>
            {msg && <Notice kind="err" onClose={() => setMsg(null)}>{msg}</Notice>}
            <button className="btn"><Plus size={20} aria-hidden="true" />Add person</button>
          </form>
        </section>
      </div>
    </div>
  );
}
