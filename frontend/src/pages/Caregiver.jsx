import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Siren, Check, Plus, Link2, MapPinned, BookOpen, MessageCircleQuestion, Bell, MessageSquareHeart } from "lucide-react";
import { api, TZ } from "../api";
import { Avatar, Empty, MemoryItem, Notice, PageHead, WeekChart } from "../components";
import { fmtTime, fmtWhenInline, useApi } from "../hooks";

export function CarerHome() {
  const links = useApi("/api/care/links");
  const [pid, setPid] = useState(null);
  useEffect(() => { if (links.data?.length && !pid) setPid(links.data[0].person.id); }, [links.data]);
  if (links.loading) return <p className="muted">Loading…</p>;
  if (links.error) return <Notice kind="err">{links.error}</Notice>;
  if (!links.data.length) {
    return (
      <div className="stack-lg">
        <PageHead title="Welcome" sub="Link to the person you care for to see their day." />
        <Empty title="You are not linked to anyone yet" action={<Link className="btn accent" to="/link"><Link2 size={20} aria-hidden="true" />Enter their code</Link>}>
          Ask them to open Family access in their app and make a code.
        </Empty>
      </div>
    );
  }
  return (
    <div className="stack-lg">
      {links.data.length > 1 && (
        <div className="row">{links.data.map((l) => <button key={l.id} className={`chip ${pid === l.person.id ? "on" : ""}`} onClick={() => setPid(l.person.id)}>{l.person.name}</button>)}</div>
      )}
      {pid && <Dashboard key={pid} pid={pid} />}
    </div>
  );
}

function Dashboard({ pid }) {
  const d = useApi(`/api/care/dashboard/${pid}?tz=${TZ}`);
  const [rem, setRem] = useState({ title: "", time: "18:00" });
  const [note, setNote] = useState("");
  const [msg2, setMsg2] = useState("");
  const [msg, setMsg] = useState(null);

  useEffect(() => { const t = setInterval(d.reload, 30000); return () => clearInterval(t); }, [d.reload]);

  if (d.loading && !d.data) return <p className="muted">Loading…</p>;
  if (d.error) return <Notice kind="err">{d.error}</Notice>;
  const { patient, today, reminders, alerts, recent, week, messages } = d.data;
  const first = patient.name.split(" ")[0];
  const doneCount = reminders.filter((r) => r.status === "done").length;

  const resolve = async (id) => { await api(`/api/alerts/${id}/resolve`, { method: "POST" }); d.reload(); };
  const addRem = async (e) => {
    e.preventDefault();
    try { await api("/api/reminders", { method: "POST", body: { ...rem, patient_id: pid } }); setRem({ title: "", time: "18:00" }); d.reload(); setMsg({ kind: "ok", text: "Reminder added." }); }
    catch (err) { setMsg({ kind: "err", text: err.message }); }
  };
  const sendMessage = async (e) => {
    e.preventDefault();
    const fd = new FormData(); fd.append("kind", "message"); fd.append("text", msg2); fd.append("patient_id", String(pid));
    try { await api("/api/records", { method: "POST", form: fd }); setMsg2(""); d.reload(); setMsg({ kind: "ok", text: `Your message now shows on ${first}'s Home.` }); }
    catch (err) { setMsg({ kind: "err", text: err.message }); }
  };
  const addNote = async (e) => {
    e.preventDefault();
    const fd = new FormData(); fd.append("kind", "text"); fd.append("text", note); fd.append("patient_id", String(pid));
    try { await api("/api/records", { method: "POST", form: fd }); setNote(""); d.reload(); setMsg({ kind: "ok", text: `Memory added for ${first}. It shows as added by family.` }); }
    catch (err) { setMsg({ kind: "err", text: err.message }); }
  };

  return (
    <div className="stack-lg">
      <PageHead title={`${first}'s day`} sub={today.last_active ? `Last saved something ${fmtWhenInline(today.last_active)}` : "Nothing saved yet"} />
      {alerts.map((a) => (
        <div key={a.id} className="notice err" role="alert">
          <Siren size={26} aria-hidden="true" style={{ color: "var(--sos)", flexShrink: 0 }} />
          <div className="grow">
            <p><b>{first} asked for help at {fmtTime(a.created_at)}</b></p>
            {a.lat != null ? <p className="small">Location shared.</p> : <p className="small">Location was not available.</p>}
            <div className="row" style={{ marginTop: 10 }}>
              {a.lat != null && <a className="btn sm" href={`https://www.openstreetmap.org/?mlat=${a.lat}&mlon=${a.lng}#map=17/${a.lat}/${a.lng}`} target="_blank" rel="noreferrer"><MapPinned size={18} aria-hidden="true" />Open map</a>}
              <button className="btn quiet sm" onClick={() => resolve(a.id)}><Check size={18} aria-hidden="true" />Mark as handled</button>
            </div>
          </div>
        </div>
      ))}
      <div className="metrics">
        <div className="metric"><BookOpen size={22} aria-hidden="true" /><p className="big-number">{today.memories}</p><p className="muted">memories saved today</p></div>
        <div className="metric"><Bell size={22} aria-hidden="true" /><p className="big-number">{doneCount}/{reminders.length}</p><p className="muted">reminders done today</p></div>
        <div className="metric"><MessageCircleQuestion size={22} aria-hidden="true" /><p className="big-number">{today.questions}</p><p className="muted">questions asked today (you can't read them)</p></div>
      </div>
      {msg && <Notice kind={msg.kind} onClose={() => setMsg(null)}>{msg.text}</Notice>}
      <div className="grid-2">
        <div className="stack-lg">
        <section className="panel">
          <div className="panel-title"><h2>This week</h2><span className="small muted">memories saved per day</span></div>
          {week && <WeekChart week={week} />}
        </section>
        <section className="panel">
          <div className="panel-title"><h2>Recent memories</h2></div>
          {recent.length === 0 && <p className="muted">Nothing shared yet.</p>}
          {recent.map((m) => <MemoryItem key={m.id} m={m} />)}
          <p className="small muted" style={{ marginTop: 12 }}>Memories {first} marked private are never shown here.</p>
        </section>
        </div>
        <div className="stack-lg">
          <section className="panel">
            <div className="panel-title"><h2>Leave a message</h2><MessageSquareHeart size={22} aria-hidden="true" style={{ color: "var(--marigold-deep)" }} /></div>
            <p className="small muted" style={{ marginBottom: 10 }}>It appears on {first}'s Home screen, with your name.</p>
            <form className="stack" onSubmit={sendMessage}>
              <textarea className="textarea" style={{ minHeight: 90 }} aria-label={`Message for ${first}`} placeholder="For example: I'm coming on Sunday with Aarav. Love you!" value={msg2} onChange={(e) => setMsg2(e.target.value)} required />
              <button className="btn accent">Send message</button>
            </form>
            {messages?.length > 0 && (
              <div className="list" style={{ marginTop: 14 }}>
                {messages.map((m) => (
                  <div key={m.id} className="list-item" style={{ minHeight: 0, alignItems: "flex-start" }}>
                    <Avatar name={(m.display_text.match(/^Message from ([^:]+):/) || [null, "Family"])[1]} />
                    <div className="grow"><p>{m.display_text.replace(/^Message from [^:]+: /, "")}</p><p className="small muted">{fmtWhenInline(m.created_at)}</p></div>
                  </div>
                ))}
              </div>
            )}
          </section>
          <section className="panel">
            <div className="panel-title"><h2>Reminders today</h2></div>
            <div className="list">
              {reminders.map((r) => (
                <div key={r.id} className="list-item">
                  <div className="grow"><p><b>{r.title}</b></p><p className="small muted">{r.time}</p></div>
                  <span className={`badge ${r.status}`}>{r.status === "done" ? "Done" : r.status === "due" ? "Not done yet" : "Later"}</span>
                </div>
              ))}
            </div>
            <form className="stack" onSubmit={addRem} style={{ marginTop: 14 }}>
              <div className="field"><label htmlFor="cr">Add a reminder for {first}</label><input id="cr" className="input" placeholder="For example: Drink water" value={rem.title} onChange={(e) => setRem({ ...rem, title: e.target.value })} required /></div>
              <div className="row" style={{ flexWrap: "nowrap" }}>
                <input type="time" className="input" aria-label="Time" value={rem.time} onChange={(e) => setRem({ ...rem, time: e.target.value })} />
                <button className="btn"><Plus size={20} aria-hidden="true" />Add</button>
              </div>
            </form>
          </section>
          <section className="panel">
            <h2 style={{ marginBottom: 12 }}>Add a memory for {first}</h2>
            <form className="stack" onSubmit={addNote}>
              <textarea className="textarea" aria-label={`Memory for ${first}`} placeholder="For example: Your nephew Rohan visited on Sunday and brought mangoes." value={note} onChange={(e) => setNote(e.target.value)} required />
              <button className="btn quiet">Add memory</button>
            </form>
          </section>
        </div>
      </div>
    </div>
  );
}

export function LinkPerson() {
  const [code, setCode] = useState("");
  const [err, setErr] = useState(null);
  const nav = useNavigate();
  const submit = async (e) => {
    e.preventDefault(); setErr(null);
    try { await api("/api/care/link", { method: "POST", body: { code: code.trim() } }); nav("/"); }
    catch (e2) { setErr(e2.message); }
  };
  return (
    <div className="stack-lg" style={{ maxWidth: 560 }}>
      <PageHead title="Link a person" sub="Type the 6-digit code from their app. They can remove your access at any time." />
      <form className="panel stack" onSubmit={submit}>
        <div className="field"><label htmlFor="code">Code</label>
          <input id="code" className="input" inputMode="numeric" pattern="[0-9]{6}" maxLength={6} value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} style={{ fontSize: "1.6rem", letterSpacing: "0.3em" }} required />
        </div>
        {err && <Notice kind="err" onClose={() => setErr(null)}>{err}</Notice>}
        <button className="btn accent block"><Link2 size={20} aria-hidden="true" />Link</button>
      </form>
    </div>
  );
}
