import { useState } from "react";
import { KeyRound, UserMinus, ShieldCheck, Lock, MessageCircleQuestion } from "lucide-react";
import { api } from "../api";
import { Dialog, Empty, Notice, PageHead } from "../components";
import { fmtWhen, fmtWhenInline, useApi } from "../hooks";

export function Family() {
  const links = useApi("/api/care/links");
  const [code, setCode] = useState(null);
  const [confirm, setConfirm] = useState(null);
  const [err, setErr] = useState(null);
  const makeCode = async () => { try { setCode(await api("/api/care/code", { method: "POST" })); } catch (e) { setErr(e.message); } };
  const revoke = async (l) => { await api(`/api/care/links/${l.id}/revoke`, { method: "POST" }); setConfirm(null); links.reload(); };
  const active = (links.data || []).filter((l) => l.active);
  const past = (links.data || []).filter((l) => !l.active);

  return (
    <div className="stack-lg" style={{ maxWidth: 760 }}>
      <PageHead title="Family access" sub="Choose who can see your memories. Private memories are never shown to them." />
      {err && <Notice kind="err" onClose={() => setErr(null)}>{err}</Notice>}
      <section className="panel stack">
        <h2>Add a family member</h2>
        <p>Give them this code. They type it in their own Care Companion account.</p>
        {code ? (
          <div className="stack" style={{ gap: 6 }}>
            <p className="big-number" style={{ letterSpacing: "0.2em" }} aria-label={`Code ${code.code.split("").join(" ")}`}>{code.code}</p>
            <p className="small muted">Works once. Expires {fmtWhenInline(code.expires_at)}.</p>
          </div>
        ) : <button className="btn accent" onClick={makeCode}><KeyRound size={20} aria-hidden="true" />Make a code</button>}
      </section>
      <section className="panel">
        <div className="panel-title"><h2>Can see your memories</h2></div>
        {active.length === 0 && <p className="muted">Nobody yet.</p>}
        <div className="list">
          {active.map((l) => (
            <div className="list-item" key={l.id}>
              <div className="grow"><p><b>{l.person.name}</b></p><p className="small muted">Linked {fmtWhenInline(l.created_at)}</p></div>
              <button className="btn quiet sm" onClick={() => setConfirm(l)}><UserMinus size={18} aria-hidden="true" />Remove access</button>
            </div>
          ))}
        </div>
        {past.length > 0 && <>
          <h3 style={{ marginTop: 18 }}>Access removed</h3>
          {past.map((l) => <p key={l.id} className="small muted">{l.person.name}, removed {fmtWhenInline(l.revoked_at)}</p>)}
        </>}
      </section>
      {confirm && (
        <Dialog title={`Remove ${confirm.person.name}'s access?`} onClose={() => setConfirm(null)}>
          <p>They will stop seeing your memories straight away. You can add them again later with a new code.</p>
          <div className="actions">
            <button className="btn quiet" onClick={() => setConfirm(null)}>Keep access</button>
            <button className="btn danger" onClick={() => revoke(confirm)}>Remove access</button>
          </div>
        </Dialog>
      )}
    </div>
  );
}

const ACTIONS = {
  view_memories: "looked at your memories", view_dashboard: "opened your daily summary", view_places: "looked at your places",
  view_people: "looked at your people list", view_reminders: "checked your reminders", view_alerts: "checked your Help alerts",
  add_memory: "added a memory for you", add_reminder: "added a reminder for you", resolve_alert: "marked a Help alert as handled",
  linked: "joined as your family member", revoked: "removed someone's access",
};

export function Privacy() {
  const { data, loading, error } = useApi("/api/privacy/log");
  return (
    <div className="stack-lg" style={{ maxWidth: 760 }}>
      <PageHead title="Who saw my data" sub="Every time a family member opens your information, it is written here." />
      {error && <Notice kind="err">{error}</Notice>}
      {loading && <p className="muted">Loading…</p>}
      {data && (
        <>
          <div className="metrics">
            <div className="metric"><Lock size={22} aria-hidden="true" /><p className="big-number">{data.private_memories}</p><p className="muted">private memories, seen only by you</p></div>
            <div className="metric"><MessageCircleQuestion size={22} aria-hidden="true" /><p className="big-number">{data.questions_asked}</p><p className="muted">questions you asked. Family cannot read them.</p></div>
          </div>
          <section className="panel">
            {data.events.length === 0 ? <Empty title="Nobody has looked yet" /> : (
              <div className="list">
                {data.events.map((e) => (
                  <div key={e.id} className="list-item">
                    <ShieldCheck size={22} aria-hidden="true" style={{ color: "var(--ink-2)", flexShrink: 0 }} />
                    <div className="grow"><p><b>{e.who}</b> {ACTIONS[e.action] || e.action}</p><p className="small muted">{fmtWhen(e.at)}</p></div>
                  </div>
                ))}
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}
