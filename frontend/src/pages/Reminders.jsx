import { useState } from "react";
import { Check, Plus, Trash2 } from "lucide-react";
import { api, TZ } from "../api";
import { Notice, PageHead } from "../components";
import { useApi } from "../hooks";

export default function Reminders() {
  const { data, setData, reload, error } = useApi(`/api/reminders?tz=${TZ}`);
  const [form, setForm] = useState({ title: "", time: "09:00" });
  const [msg, setMsg] = useState(null);

  const add = async (e) => {
    e.preventDefault();
    try { await api("/api/reminders", { method: "POST", body: form }); setForm({ title: "", time: "09:00" }); reload(); }
    catch (err) { setMsg(err.message); }
  };
  const done = async (id) => setData(await api(`/api/reminders/${id}/done?tz=${TZ}`, { method: "POST" }));
  const remove = async (id) => { await api(`/api/reminders/${id}`, { method: "DELETE" }); reload(); };

  return (
    <div className="stack-lg" style={{ maxWidth: 760 }}>
      <PageHead title="Reminders" sub="Marking one as done saves it, so you can later ask “Did I take my tablet?”" />
      {error && <Notice kind="err">{error}</Notice>}
      <section className="panel">
        <div className="list">
          {(data || []).map((r) => (
            <div className="list-item" key={r.id}>
              <div className="grow"><p><b>{r.title}</b></p><p className="small muted">Every day at {r.time}</p></div>
              <span className={`badge ${r.status}`}>{r.status === "done" ? "Done today" : r.status === "due" ? "Not done yet" : "Later today"}</span>
              {r.status !== "done" && <button className="btn sm" onClick={() => done(r.id)}><Check size={18} aria-hidden="true" />Done</button>}
              <button className="btn ghost sm" onClick={() => remove(r.id)} aria-label={`Remove ${r.title}`}><Trash2 size={18} /></button>
            </div>
          ))}
          {data?.length === 0 && <p className="muted">No reminders yet.</p>}
        </div>
      </section>
      <section className="panel">
        <h2 style={{ marginBottom: 12 }}>Add a reminder</h2>
        <form className="stack" onSubmit={add}>
          <div className="field"><label htmlFor="rt">What to remember</label><input id="rt" className="input" placeholder="For example: Call Ramesh" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} required /></div>
          <div className="field"><label htmlFor="rtime">Time</label><input id="rtime" type="time" className="input" value={form.time} onChange={(e) => setForm({ ...form, time: e.target.value })} required /></div>
          {msg && <Notice kind="err" onClose={() => setMsg(null)}>{msg}</Notice>}
          <button className="btn"><Plus size={20} aria-hidden="true" />Add reminder</button>
        </form>
        <p className="small muted" style={{ marginTop: 12 }}>This app does not give advice about medicines. Ask your doctor about doses.</p>
      </section>
    </div>
  );
}
