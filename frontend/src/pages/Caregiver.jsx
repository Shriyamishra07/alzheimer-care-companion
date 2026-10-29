import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Siren, Check, Link2, MapPinned, BookOpen, MessageCircleQuestion, Bell, MessageSquareHeart, Crown, Users, EyeOff } from "lucide-react";
import { api, TZ } from "../api";
import { Avatar, Empty, MemoryItem, Notice, PageHead, WeekChart } from "../components";
import { fmtTime, fmtWhenInline, useApi } from "../hooks";
import { ReminderForm, ReminderRow } from "../reminders";
import { PERMS } from "./CareTeam";

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
        <Empty title="You are not linked to anyone yet" action={<Link className="btn accent" to="/link"><Link2 size={20} aria-hidden="true" />Enter a code</Link>}>
          Ask them, or their primary caregiver, for a 6-digit code.
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

function SharedWithYou({ perms, first }) {
  return (
    <section className="panel tint stack" style={{ gap: 10 }}>
      <div className="row" style={{ gap: 10 }}><EyeOff size={20} aria-hidden="true" /><b>What {first}'s primary caregiver shares with you</b></div>
      <div className="shared-summary">
        {PERMS.map(([k, label]) => <span key={k} className={perms[k] ? "" : "no"}>{label}</span>)}
      </div>
      <p className="small muted">Need more? Ask the primary caregiver. They can change this on the Care team page.</p>
    </section>
  );
}

function Dashboard({ pid }) {
  const d = useApi(`/api/care/dashboard/${pid}?tz=${TZ}`);
  const [note, setNote] = useState("");
  const [msg2, setMsg2] = useState("");
  const [msg, setMsg] = useState(null);

  useEffect(() => { const t = setInterval(d.reload, 30000); return () => clearInterval(t); }, [d.reload]);

  if (d.loading && !d.data) return <p className="muted">Loading…</p>;
  if (d.error) return <Notice kind="err">{d.error}</Notice>;
  const { patient, access, today, reminders, alerts, recent, week, messages } = d.data;
  const P = access.permissions;
  const first = patient.name.split(" ")[0];
  const todayRems = (reminders || []).filter((r) => r.status !== "upcoming");
  const doneCount = todayRems.filter((r) => r.status === "done").length;

  const resolve = async (id) => { await api(`/api/alerts/${id}/resolve`, { method: "POST" }); d.reload(); };
  const removeRem = async (r) => { try { await api(`/api/reminders/${r.id}`, { method: "DELETE" }); d.reload(); } catch (e) { setMsg({ kind: "err", text: e.message }); } };
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

  const roleBadge = access.role === "primary"
    ? <Link to="/team" className="role-badge primary"><Crown size={15} aria-hidden="true" />You are the primary caregiver</Link>
    : <span className="role-badge"><Users size={15} aria-hidden="true" />Caregiver</span>;

  return (
    <div className="stack-lg">
      <PageHead title={`${first}'s day`} sub={today?.last_active ? `Last saved something ${fmtWhenInline(today.last_active)}` : (P.memories ? "Nothing saved yet" : "Here is what is shared with you.")} right={roleBadge} />
      {(alerts || []).map((a) => (
        <div key={a.id} className="notice err" role="alert">
          <Siren size={26} aria-hidden="true" style={{ color: "var(--sos)", flexShrink: 0 }} />
          <div className="grow">
            <p><b>{first} asked for help at {fmtTime(a.created_at)}</b></p>
            {a.lat != null ? <p className="small">Location shared.</p> : <p className="small">{a.location_hidden ? "Location is not shared with you. The primary caregiver can see it." : "Location was not available."}</p>}
            <div className="row" style={{ marginTop: 10 }}>
              {a.lat != null && <a className="btn sm" href={`https://www.openstreetmap.org/?mlat=${a.lat}&mlon=${a.lng}#map=17/${a.lat}/${a.lng}`} target="_blank" rel="noreferrer"><MapPinned size={18} aria-hidden="true" />Open map</a>}
              <button className="btn quiet sm" onClick={() => resolve(a.id)}><Check size={18} aria-hidden="true" />Mark as handled</button>
            </div>
          </div>
        </div>
      ))}
      {access.role !== "primary" && <SharedWithYou perms={P} first={first} />}
      {(P.memories || P.reminders) && (
        <div className="metrics">
          {P.memories && <div className="metric"><BookOpen size={22} aria-hidden="true" /><p className="big-number">{today.memories}</p><p className="muted">memories saved today</p></div>}
          {P.reminders && <div className="metric"><Bell size={22} aria-hidden="true" /><p className="big-number">{doneCount}/{todayRems.length}</p><p className="muted">reminders done today</p></div>}
          {P.memories && <div className="metric"><MessageCircleQuestion size={22} aria-hidden="true" /><p className="big-number">{today.questions}</p><p className="muted">questions asked today (you can't read them)</p></div>}
        </div>
      )}
      {msg && <Notice kind={msg.kind} onClose={() => setMsg(null)}>{msg.text}</Notice>}
      <div className="grid-2">
        <div className="stack-lg">
          {P.memories ? (
            <>
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
            </>
          ) : (
            <section className="panel"><Empty title="Memories are not shared with you">{first}'s primary caregiver decides who can see memories.</Empty></section>
          )}
          {P.reminders && (
            <section className="panel">
              <div className="panel-title"><h2>Reminders</h2><span className="small muted">today and coming up</span></div>
              {reminders.length === 0 && <p className="muted">No reminders yet.</p>}
              <div className="list">{reminders.map((r) => <ReminderRow key={r.id} r={r} name={patient.name} onRemove={removeRem} />)}</div>
            </section>
          )}
        </div>
        <div className="stack-lg">
          {P.messages && (
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
          )}
          {P.reminders && (
            <section className="panel">
              <h2 style={{ marginBottom: 12 }}>Add a reminder for {first}</h2>
              <ReminderForm patientId={pid} forName={first} onSaved={d.reload} />
            </section>
          )}
          {P.add_memories && (
            <section className="panel">
              <h2 style={{ marginBottom: 12 }}>Add a memory for {first}</h2>
              <form className="stack" onSubmit={addNote}>
                <textarea className="textarea" aria-label={`Memory for ${first}`} placeholder="For example: Your nephew Rohan visited on Sunday and brought mangoes." value={note} onChange={(e) => setNote(e.target.value)} required />
                <button className="btn quiet">Add memory</button>
              </form>
            </section>
          )}
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
      <PageHead title="Link a person" sub="Type the 6-digit code from their app, or from their primary caregiver. You will see only what they share with you." />
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
