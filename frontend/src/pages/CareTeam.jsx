import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { BookOpen, Bell, Copy, Crown, Link2, LogOut, MapPin, MessageSquareHeart, PenLine, Share2, Siren, UserMinus, UserPlus, X } from "lucide-react";
import { api } from "../api";
import { Avatar, Dialog, Empty, Notice, PageHead } from "../components";
import { fmtDayInline, fmtWhenInline, useApi } from "../hooks";

// Short labels and icons for the permissions the server defines (see backend PERMISSIONS).
export const PERMS = [
  ["memories", "Memories and daily activity", BookOpen],
  ["places", "Places and location", MapPin],
  ["reminders", "Reminders", Bell],
  ["messages", "Send messages", MessageSquareHeart],
  ["add_memories", "Add memories", PenLine],
  ["alerts", "Help alerts", Siren],
];
const DEFAULTS = { memories: true, places: false, reminders: true, messages: true, add_memories: false, alerts: true };

function PermSwitch({ k, label, Icon, on, disabled, onChange }) {
  return (
    <label className={`perm ${on ? "" : "off"}`}>
      <input type="checkbox" role="switch" checked={!!on} disabled={disabled} onChange={(e) => onChange?.(k, e.target.checked)} aria-label={label} />
      <span className="perm-text"><Icon size={18} aria-hidden="true" />{label}</span>
    </label>
  );
}

export function PermGrid({ perms, editable, onChange }) {
  return (
    <div className="perm-grid">
      {PERMS.map(([k, label, Icon]) => <PermSwitch key={k} k={k} label={label} Icon={Icon} on={perms?.[k]} disabled={!editable} onChange={onChange} />)}
    </div>
  );
}

function RoleBadge({ role }) {
  return role === "primary"
    ? <span className="role-badge primary"><Crown size={15} aria-hidden="true" />Primary caregiver</span>
    : <span className="role-badge">Caregiver</span>;
}

export function TeamPanel({ pid, patientView = false }) {
  const t = useApi(`/api/care/team/${pid}`);
  const [inv, setInv] = useState({ label: "", permissions: DEFAULTS });
  const [code, setCode] = useState(null);
  const [confirm, setConfirm] = useState(null);
  const [msg, setMsg] = useState(null);
  const [copied, setCopied] = useState(false);

  if (t.loading && !t.data) return <p className="muted">Loading…</p>;
  if (t.error) return <Notice kind="err">{t.error}</Notice>;
  const { patient, can_manage: manage, members, invites } = t.data;
  const first = patient.name.split(" ")[0];
  const hasPrimary = members.some((m) => m.role === "primary");
  const me = members.find((m) => m.is_you);

  const act = async (fn, okText) => {
    setMsg(null);
    try { const r = await fn(); if (r?.members) t.setData(r); else t.reload(); if (okText) setMsg({ kind: "ok", text: okText }); }
    catch (e) { setMsg({ kind: "err", text: e.message }); }
  };
  const setPerm = (m) => (k, v) => act(() => api(`/api/care/links/${m.link_id}`, { method: "PATCH", body: { permissions: { ...m.permissions, [k]: v } } }),
    `${m.name.split(" ")[0]} can ${v ? "now" : "no longer"} see: ${PERMS.find((p) => p[0] === k)[1].toLowerCase()}.`);
  const invite = async (e) => {
    e.preventDefault();
    await act(async () => { const r = await api(`/api/care/team/${pid}/invite`, { method: "POST", body: inv }); setCode(r); setInv({ label: "", permissions: DEFAULTS }); });
  };
  const share = code && `Join ${first}'s care team on Care Companion. Create a caregiver account and enter this code: ${code.code} (works once, for 24 hours).`;

  return (
    <div className="stack-lg">
      {msg && <Notice kind={msg.kind} onClose={() => setMsg(null)}>{msg.text}</Notice>}

      <section className="panel stack">
        <div className="panel-title"><h2>{patientView ? "Your care team" : `${first}'s care team`}</h2><span className="small muted">{members.length} {members.length === 1 ? "person" : "people"}</span></div>
        <p className="muted">
          {hasPrimary
            ? `The primary caregiver sees everything and decides what each other caregiver can see. ${patientView ? "You" : first} can always see this list and remove anyone.`
            : `There is no primary caregiver yet. ${patientView ? "Choose one below, or invite someone: the first person to join becomes the primary caregiver." : ""}`}
        </p>
        {members.length === 0 && <Empty title="Nobody yet">Invite a family member below.</Empty>}
        {members.map((m) => (
          <div key={m.link_id} className={`member ${m.role}`}>
            <div className="member-head">
              <Avatar name={m.name} large />
              <div className="grow">
                <p><b>{m.name}</b>{m.is_you ? " (you)" : ""}</p>
                <p className="small muted">{m.relation || "Family member"} · joined {fmtDayInline(m.since)}</p>
              </div>
              <RoleBadge role={m.role} />
            </div>
            {m.role === "primary"
              ? <p className="small muted">Sees everything and manages the care team.</p>
              : m.permissions && <PermGrid perms={m.permissions} editable={manage} onChange={setPerm(m)} />}
            {!m.permissions && m.role !== "primary" && <p className="small muted">Only the primary caregiver sees what others can access.</p>}
            <div className="member-actions">
              {manage && m.role !== "primary" && <button className="btn quiet sm" onClick={() => setConfirm({ type: "primary", m })}><Crown size={18} aria-hidden="true" />Make primary</button>}
              {manage && !m.is_you && <button className="btn quiet sm" onClick={() => setConfirm({ type: "remove", m })}><UserMinus size={18} aria-hidden="true" />Remove</button>}
              {m.is_you && !patientView && <button className="btn ghost sm" onClick={() => setConfirm({ type: "leave", m })}><LogOut size={18} aria-hidden="true" />Leave this care team</button>}
            </div>
          </div>
        ))}
      </section>

      {manage && (
        <section className="panel stack">
          <div className="panel-title"><h2>Invite a caregiver</h2><UserPlus size={22} aria-hidden="true" style={{ color: "var(--marigold-deep)" }} /></div>
          {code ? (
            <div className="code-box">
              <p className="small">Invitation code {code.label ? `for ${code.label}` : ""}</p>
              <p className="big-number" aria-label={`Code ${code.code.split("").join(" ")}`}>{code.code}</p>
              <p className="small muted">Works once. Expires {fmtWhenInline(code.expires_at)}. {code.role === "primary" ? "This person will become the primary caregiver." : "They will see only what you switched on."}</p>
              <div className="row" style={{ justifyContent: "center" }}>
                <button className="btn quiet sm" onClick={() => { navigator.clipboard?.writeText(code.code); setCopied(true); }}><Copy size={18} aria-hidden="true" />{copied ? "Copied" : "Copy code"}</button>
                <a className="btn quiet sm" href={`https://wa.me/?text=${encodeURIComponent(share)}`} target="_blank" rel="noreferrer"><Share2 size={18} aria-hidden="true" />Share on WhatsApp</a>
                <button className="btn ghost sm" onClick={() => { setCode(null); setCopied(false); }}>Invite someone else</button>
              </div>
            </div>
          ) : (
            <form className="stack" onSubmit={invite}>
              <div className="field"><label htmlFor="inv-label">Who is it for? (optional)</label>
                <input id="inv-label" className="input" placeholder="For example: Rohan, nephew" value={inv.label} onChange={(e) => setInv({ ...inv, label: e.target.value })} maxLength={60} /></div>
              {hasPrimary ? (
                <div className="field"><span style={{ fontWeight: 500 }}>What they can see and do</span>
                  <PermGrid perms={inv.permissions} editable onChange={(k, v) => setInv({ ...inv, permissions: { ...inv.permissions, [k]: v } })} />
                  <p className="small muted">Private memories are never shown to anyone, whatever you choose here.</p>
                </div>
              ) : <p className="small muted">The first person to join becomes the primary caregiver and can see everything that is shared.</p>}
              <button className="btn accent"><UserPlus size={20} aria-hidden="true" />Create invite code</button>
            </form>
          )}
          {invites.length > 0 && (
            <div className="stack" style={{ gap: 8 }}>
              <h3>Waiting to join</h3>
              <div className="list">
                {invites.map((i) => (
                  <div key={i.code} className="list-item">
                    <div className="grow"><p><b>{i.label || "Invitation"}</b> · code {i.code}</p><p className="small muted">Expires {fmtWhenInline(i.expires_at)}</p></div>
                    <button className="btn ghost sm" onClick={() => act(() => api(`/api/care/codes/${i.code}/cancel`, { method: "POST" }), "Invitation cancelled.")}><X size={18} aria-hidden="true" />Cancel</button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </section>
      )}

      {confirm && (
        <Dialog title={{ primary: `Make ${confirm.m.name.split(" ")[0]} the primary caregiver?`, remove: `Remove ${confirm.m.name}?`, leave: "Leave this care team?" }[confirm.type]} onClose={() => setConfirm(null)}>
          <p>{{
            primary: `${confirm.m.name.split(" ")[0]} will see everything that is shared and manage the care team.${me?.role === "primary" ? " You will stay in the team as a caregiver." : ""}`,
            remove: `${confirm.m.name.split(" ")[0]} will stop seeing ${patientView ? "your" : `${first}'s`} information straight away. This is recorded in Who saw my data.`,
            leave: `You will stop seeing ${first}'s information. You can join again with a new code.`,
          }[confirm.type]}</p>
          <div className="actions">
            <button className="btn quiet" onClick={() => setConfirm(null)}>Cancel</button>
            <button className={`btn ${confirm.type === "primary" ? "" : "danger"}`} onClick={async () => {
              const { type, m } = confirm; setConfirm(null);
              if (type === "primary") await act(() => api(`/api/care/links/${m.link_id}/make-primary`, { method: "POST" }), `${m.name.split(" ")[0]} is now the primary caregiver.`);
              else await act(() => api(`/api/care/links/${m.link_id}/revoke`, { method: "POST" }), type === "leave" ? "You left the care team." : `${m.name.split(" ")[0]}'s access was removed.`);
              if (type === "leave") window.location.assign("/");
            }}>{{ primary: "Make primary", remove: "Remove access", leave: "Leave" }[confirm.type]}</button>
          </div>
        </Dialog>
      )}
    </div>
  );
}

// Caregiver: the care team of the person they look after.
export default function CareTeam() {
  const links = useApi("/api/care/links");
  const [pid, setPid] = useState(null);
  useEffect(() => { if (links.data?.length && !pid) setPid(links.data[0].person.id); }, [links.data, pid]);
  if (links.loading) return <p className="muted">Loading…</p>;
  if (links.error) return <Notice kind="err">{links.error}</Notice>;
  if (!links.data.length) {
    return (
      <div className="stack-lg">
        <PageHead title="Care team" sub="Link to the person you care for first." />
        <Empty title="You are not linked to anyone yet" action={<Link className="btn accent" to="/link"><Link2 size={20} aria-hidden="true" />Enter a code</Link>} />
      </div>
    );
  }
  return (
    <div className="stack-lg" style={{ maxWidth: 900 }}>
      <PageHead title="Care team" sub="Who looks after them, and what each person can see." />
      {links.data.length > 1 && (
        <div className="row">{links.data.map((l) => <button key={l.id} className={`chip ${pid === l.person.id ? "on" : ""}`} onClick={() => setPid(l.person.id)}>{l.person.name}</button>)}</div>
      )}
      {pid && <TeamPanel key={pid} pid={pid} />}
    </div>
  );
}
