import { useState } from "react";
import { ShieldCheck, Lock, MessageCircleQuestion, Check, Sparkles, EyeOff } from "lucide-react";
import { api } from "../api";
import { useAuth } from "../auth";
import { Empty, Notice, PageHead } from "../components";
import { fmtWhen, fmtWhenInline, useApi } from "../hooks";
import { TeamPanel } from "./CareTeam";

export function Family() {
  const { user } = useAuth();
  const links = useApi("/api/care/links");
  const past = (links.data || []).filter((l) => !l.active);
  return (
    <div className="stack-lg" style={{ maxWidth: 900 }}>
      <PageHead title="Family access" sub="Choose who looks after you and what each person can see. Private memories are never shown to anyone." />
      <TeamPanel pid={user.id} patientView />
      {past.length > 0 && (
        <section className="panel">
          <h3 style={{ marginBottom: 8 }}>Access removed</h3>
          {past.map((l) => <p key={l.id} className="small muted">{l.person.name}, removed {fmtWhenInline(l.revoked_at)}</p>)}
        </section>
      )}
    </div>
  );
}

const ACTIONS = {
  view_memories: "looked at your memories", view_dashboard: "opened your daily summary", view_places: "looked at your places",
  view_people: "looked at your people list", view_reminders: "checked your reminders", view_alerts: "checked your Help alerts",
  add_memory: "added a memory for you", add_reminder: "added a reminder for you", remove_reminder: "removed a reminder",
  add_reminder_voice: "recorded a voice reminder for you", resolve_alert: "marked a Help alert as handled",
  linked: "joined your care team", revoked: "removed someone's access", left: "left your care team",
  invited: "invited someone to your care team", permissions_changed: "changed what a caregiver can see",
  made_primary: "chose a new primary caregiver",
};
const DETAILED = new Set(["revoked", "invited", "permissions_changed", "made_primary"]);

// Shows the redacted text with the tokens highlighted.
function Tokens({ text }) {
  const parts = text.split(/(\b(?:PERSON|FAMILY|PLACE)_\d+\b|\bUSER\b|\b(?:EMAIL|CARD|AADHAAR|PAN|PHONE|COORD|PINCODE)_[0-9a-f]{4}\b)/g);
  return <p className="ai-sent">{parts.map((p, i) => (i % 2 ? <span key={i} className="tok">{p}</span> : p))}</p>;
}

function AiPrivacy({ data, onConsent }) {
  const { user, setUser } = useAuth();
  const [busy, setBusy] = useState(false);
  const [text, setText] = useState("Call Anita on 98765 43210 after the walk at Upvan Lake.");
  const [preview, setPreview] = useState(null);
  const [err, setErr] = useState(null);
  const toggle = async (e) => {
    setBusy(true);
    try { const u = await api("/api/me", { method: "PATCH", body: { ai_media_consent: e.target.checked } }); setUser(u); onConsent?.(); }
    catch (er) { setErr(er.message); } finally { setBusy(false); }
  };
  const show = async (e) => {
    e.preventDefault(); setErr(null);
    try { setPreview(await api("/api/privacy/preview", { method: "POST", body: { text } })); } catch (er) { setErr(er.message); }
  };
  return (
    <>
      <section className="panel stack">
        <div className="panel-title"><h2>AI and your privacy</h2><ShieldCheck size={22} aria-hidden="true" style={{ color: "var(--leaf)" }} /></div>
        <ul className="checklist">
          <li><Check size={18} aria-hidden="true" /><span>Names, places, phone numbers and ID numbers are replaced with codes such as PERSON_12 before anything is sent to the AI. The real words are put back only on our own server.</span></li>
          <li><Check size={18} aria-hidden="true" /><span>Only the few memories that match your question are used, never your whole diary.</span></li>
          <li><Check size={18} aria-hidden="true" /><span>Private memories are never used, and family cannot read your questions.</span></li>
          <li><Check size={18} aria-hidden="true" /><span>The AI key stays on the server. Your phone never talks to the AI directly.</span></li>
          <li><Check size={18} aria-hidden="true" /><span>Every request to the AI is recorded with the names already removed, so it can be checked.</span></li>
        </ul>
        <label className="switch">
          <input type="checkbox" checked={!!user.ai_media_consent} disabled={busy} onChange={toggle} />
          Let the AI describe my photos and write down my voice notes
        </label>
        <p className="small muted">Pictures and voices cannot have names removed the way text can, so this stays off unless you switch it on. Location details are removed from photos either way.</p>
        {data && data.questions_asked > 0 && <p className="small muted">{data.questions_sent_to_ai} of your {data.questions_asked} questions used the online AI, with names removed. The rest were answered on our server only.</p>}
      </section>
      <section className="panel stack">
        <div className="panel-title"><h2>See what the AI receives</h2><Sparkles size={22} aria-hidden="true" style={{ color: "var(--marigold-deep)" }} /></div>
        <p className="muted">Type something with names or numbers in it. This is exactly what would be sent.</p>
        <form className="stack" onSubmit={show}>
          <textarea className="textarea" style={{ minHeight: 80 }} aria-label="Text to check" value={text} onChange={(e) => setText(e.target.value)} maxLength={1000} required />
          <button className="btn quiet"><EyeOff size={20} aria-hidden="true" />Show what the AI would receive</button>
        </form>
        {err && <Notice kind="err" onClose={() => setErr(null)}>{err}</Notice>}
        {preview && (
          <div className="stack" style={{ gap: 8 }}>
            <Tokens text={preview.sent_to_ai} />
            {preview.hidden.length > 0
              ? <p className="small muted">Hidden: {preview.hidden.map((h) => `${h.original} → ${h.token}`).join(", ")}</p>
              : <p className="small muted">Nothing personal found in this text.</p>}
          </div>
        )}
      </section>
    </>
  );
}

export function Privacy() {
  const { data, loading, error, reload } = useApi("/api/privacy/log");
  return (
    <div className="stack-lg" style={{ maxWidth: 820 }}>
      <PageHead title="Who saw my data" sub="Every time a family member opens your information, it is written here. So is every change to your care team." />
      {error && <Notice kind="err">{error}</Notice>}
      {loading && !data && <p className="muted">Loading…</p>}
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
                    <div className="grow">
                      <p><b>{e.who}</b> {ACTIONS[e.action] || e.action.replace(/_/g, " ")}</p>
                      {DETAILED.has(e.action) && e.detail && <p className="small">{e.detail}</p>}
                      <p className="small muted">{fmtWhen(e.at)}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>
        </>
      )}
      <AiPrivacy data={data} onConsent={reload} />
    </div>
  );
}
