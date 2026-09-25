import { useEffect, useState } from "react";
import { NavLink, Link } from "react-router-dom";
import { MapContainer, TileLayer, CircleMarker, Tooltip, useMap } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import {
  House, MapPin, Plus, MessageCircleQuestion, Menu, BookOpen, Users, Bell, HeartHandshake, ShieldCheck,
  FlaskConical, Settings, LayoutDashboard, Link2, Siren, Camera, Mic, PenLine, ClipboardCheck, Lock, X, Phone,
  MessageSquareHeart, ChevronDown, LogOut,
} from "lucide-react";
import { api, mediaUrl } from "./api";
import { useAuth } from "./auth";
import { fmtTime, fmtWhen, getDemoLocation } from "./hooks";

// One list drives the desktop header, the phone bottom bar and the More page.
export const PATIENT_NAV = [
  { to: "/", label: "Home", icon: House, end: true, top: true, bottom: true },
  { to: "/save", label: "Save a memory", short: "Save", icon: Plus, save: true, top: true, bottom: true },
  { to: "/ask", label: "Ask", icon: MessageCircleQuestion, top: true, bottom: true },
  { to: "/places", label: "Places", icon: MapPin, top: true, bottom: true },
  { to: "/memories", label: "Memories", icon: BookOpen, top: true, group: "My life" },
  { to: "/people", label: "People", icon: Users, top: true, group: "My life" },
  { to: "/reminders", label: "Reminders", icon: Bell, top: true, group: "My life" },
  { to: "/family", label: "Family access", icon: HeartHandshake, group: "Family and privacy" },
  { to: "/privacy", label: "Who saw my data", icon: ShieldCheck, group: "Family and privacy" },
  { to: "/research", label: "Grounding test", icon: FlaskConical, group: "About this project" },
  { to: "/settings", label: "Settings", icon: Settings, group: "About this project" },
];
export const MORE_LINK = { to: "/more", label: "More", icon: Menu };
const PATIENT_BOTTOM = ["/", "/places", "/save", "/ask"].map((to) => PATIENT_NAV.find((n) => n.to === to));

export const CARER_NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true, top: true, bottom: true },
  { to: "/link", label: "Link a person", icon: Link2, top: true, bottom: true },
  { to: "/settings", label: "Settings", icon: Settings, top: true, bottom: true },
];

export function navGroups(items) {
  const groups = [];
  for (const n of items) {
    const g = n.group || "";
    if (!groups.length || groups[groups.length - 1].name !== g) groups.push({ name: g, items: [] });
    groups[groups.length - 1].items.push(n);
  }
  return groups;
}

export function initials(name) {
  return (name || "?").split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0].toUpperCase()).join("");
}
export function avatarClass(name) {
  let h = 0;
  for (const ch of name || "") h = (h * 31 + ch.charCodeAt(0)) % 5;
  return `avatar c${h + 1}`;
}
export function Avatar({ name, large }) {
  return <span className={`${avatarClass(name)} ${large ? "lg" : ""}`} aria-hidden="true">{initials(name)}</span>;
}

export function Skeleton({ lines = 3 }) {
  return (
    <div className="stack" style={{ gap: 10 }} aria-busy="true" aria-label="Loading">
      {Array.from({ length: lines }).map((_, i) => <div key={i} className={`skeleton line ${i % 3 === 1 ? "w60" : i % 3 === 2 ? "w40" : ""}`} />)}
    </div>
  );
}

function UserMenu() {
  const { user, signOut } = useAuth();
  const links = user.role === "patient" ? PATIENT_NAV.filter((n) => n.group) : [];
  return (
    <details className="menu">
      <summary aria-label="Account menu"><Avatar name={user.name} /><span>{user.name.split(" ")[0]}</span><ChevronDown size={18} aria-hidden="true" /></summary>
      <div className="menu-panel">
        <div className="who"><b>{user.name}</b><br /><span className="small muted">{user.role === "patient" ? "Saving my own memories" : "Caregiver"}</span></div>
        <div className="sep" />
        {links.map((n) => <Link key={n.to} to={n.to} className={n.group === "My life" ? "narrow-only" : ""} onClick={(e) => e.currentTarget.closest("details").removeAttribute("open")}><n.icon size={20} aria-hidden="true" />{n.label}</Link>)}
        {links.length > 0 && <div className="sep" />}
        <button onClick={signOut}><LogOut size={20} aria-hidden="true" />Sign out</button>
      </div>
    </details>
  );
}

export function Shell({ children }) {
  const { user } = useAuth();
  const patient = user.role === "patient";
  const nav = patient ? PATIENT_NAV : CARER_NAV;
  const top = nav.filter((n) => n.top);
  const bottom = patient ? [...PATIENT_BOTTOM, MORE_LINK] : CARER_NAV;
  return (
    <div className="shell">
      <header className="topbar">
        <div className="topbar-in">
          <Link to="/" className="brand"><img src="/icon-192.png" alt="" /><span>Care Companion</span></Link>
          <nav className="topnav" aria-label="Main">
            {top.map((n) => (
              <NavLink key={n.to} to={n.to} end={n.end} className={({ isActive }) => `toplink ${n.save ? "save" : ""} ${n.group === "My life" ? "secondary" : ""} ${isActive && !n.save ? "active" : ""}`}>
                <n.icon size={20} aria-hidden="true" />{n.short || n.label}
              </NavLink>
            ))}
          </nav>
          <div className="topbar-right">
            {patient ? <SosButton /> : <span className="small muted">Caregiver</span>}
            <UserMenu />
          </div>
        </div>
      </header>
      <main className="main">{children}</main>
      <nav className="bottomnav" style={{ gridTemplateColumns: `repeat(${bottom.length}, 1fr)` }} aria-label="Main">
        {bottom.map((n) => (
          <NavLink key={n.to} to={n.to} end={n.end} className={({ isActive }) => `navlink ${n.save ? "save" : ""} ${isActive ? "active" : ""}`}>
            {n.save ? <span className="bubble"><n.icon size={28} aria-hidden="true" /></span> : <n.icon size={24} aria-hidden="true" />}
            {n.short || n.label}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}

// Seven bars, no library: memories saved per day for the caregiver.
export function WeekChart({ week }) {
  const max = Math.max(1, ...week.map((d) => d.count));
  const W = 420, H = 150, pad = 10, bw = 40, gap = (W - 2 * pad - 7 * bw) / 6;
  return (
    <svg className="chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Memories saved per day this week: ${week.map((d) => `${d.label} ${d.count}`).join(", ")}`}>
      {week.map((d, i) => {
        const h = Math.round((d.count / max) * 90);
        const x = pad + i * (bw + gap);
        return (
          <g key={d.date}>
            <rect className={i === 6 ? "today" : ""} x={x} y={112 - h} width={bw} height={Math.max(h, 3)} rx="6" />
            <text className="val" x={x + bw / 2} y={106 - h} textAnchor="middle">{d.count || ""}</text>
            <text x={x + bw / 2} y={134} textAnchor="middle">{i === 6 ? "Today" : d.label}</text>
          </g>
        );
      })}
    </svg>
  );
}

function currentPosition() {
  return new Promise((resolve) => {
    const demo = getDemoLocation();
    if (demo) return resolve(demo);
    if (!("geolocation" in navigator)) return resolve(null);
    navigator.geolocation.getCurrentPosition(
      (p) => resolve({ lat: p.coords.latitude, lng: p.coords.longitude }),
      () => resolve(null),
      { enableHighAccuracy: true, timeout: 8000, maximumAge: 60000 }
    );
  });
}
export { currentPosition };

export function SosButton() {
  const [open, setOpen] = useState(false);
  const [state, setState] = useState("ask"); // ask | sending | sent | error
  const [result, setResult] = useState(null);
  const send = async () => {
    setState("sending");
    try {
      const pos = await currentPosition();
      const r = await api("/api/sos", { method: "POST", body: pos || {} });
      setResult({ ...r, pos }); setState("sent");
    } catch (e) { setResult({ error: e.message }); setState("error"); }
  };
  const close = () => { setOpen(false); setState("ask"); setResult(null); };
  return (
    <>
      <button className="sos-btn" onClick={() => setOpen(true)}><Siren size={20} aria-hidden="true" />Help</button>
      {open && (
        <Dialog title={state === "sent" ? "Your family has been told" : "Ask your family for help?"} onClose={close}>
          {state === "ask" && <>
            <p>This sends an alert with your location to the people who care for you.</p>
            <div className="actions">
              <button className="btn quiet" onClick={close}>Cancel</button>
              <button className="btn danger" onClick={send}>Send alert</button>
            </div>
          </>}
          {state === "sending" && <p>Sending your alert…</p>}
          {state === "sent" && <>
            <p>{result.pos ? "Your location was shared." : "Your location could not be found, but the alert was sent."}</p>
            {result.caregivers.length === 0 && <p className="muted">No family member is linked yet. Add one under Family access.</p>}
            {result.caregivers.map((c) => (
              <a key={c.name} className="btn accent block" href={c.phone ? `tel:${c.phone.replace(/\s/g, "")}` : undefined}>
                <Phone size={20} aria-hidden="true" />{c.phone ? `Call ${c.name}` : `${c.name} has no phone number saved`}
              </a>
            ))}
            <button className="btn quiet block" onClick={close}>Close</button>
          </>}
          {state === "error" && <>
            <Notice kind="err">{result.error}</Notice>
            <div className="actions"><button className="btn quiet" onClick={close}>Close</button><button className="btn danger" onClick={send}>Try again</button></div>
          </>}
        </Dialog>
      )}
    </>
  );
}

export function Dialog({ title, children, onClose }) {
  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose?.();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="overlay" role="presentation" onMouseDown={(e) => e.target === e.currentTarget && onClose?.()}>
      <div className="dialog" role="dialog" aria-modal="true" aria-label={title}>
        <div className="spread"><h2>{title}</h2>
          {onClose && <button className="btn ghost sm" onClick={onClose} aria-label="Close"><X size={22} /></button>}
        </div>
        {children}
      </div>
    </div>
  );
}

// Notices never disappear on their own (NFR-U-5). The person closes them.
export function Notice({ kind = "", children, onClose, action }) {
  return (
    <div className={`notice ${kind}`} role={kind === "err" ? "alert" : "status"}>
      <div className="grow">{children}</div>
      {action}
      {onClose && <button className="btn ghost sm" onClick={onClose} aria-label="Close message"><X size={20} /></button>}
    </div>
  );
}

const GLYPH = { text: PenLine, photo: Camera, voice: Mic, log: ClipboardCheck, message: MessageSquareHeart };

export function MemoryItem({ m, showPlace = true, actions, fullDate = false }) {
  const Icon = GLYPH[m.kind] || PenLine;
  return (
    <article className="memory">
      <div className={`glyph ${m.kind === "log" || m.kind === "message" ? m.kind : ""}`} aria-hidden="true"><Icon size={22} /></div>
      <div>
        <p>{m.display_text || (m.kind === "photo" ? "Photo" : m.kind === "voice" ? "Voice note" : "")}</p>
        {m.transcript && m.text && <p className="small muted">Heard: {m.transcript}</p>}
        {m.media_url && m.media_mime?.startsWith("image/") && <img className="photo" src={mediaUrl(m.media_url)} alt={m.caption || m.text || "Saved photo"} loading="lazy" />}
        {m.media_url && m.media_mime?.startsWith("audio/") && <audio controls src={mediaUrl(m.media_url)} preload="none" />}
        <div className="meta">
          <span>{fullDate ? fmtWhen(m.created_at) : fmtTime(m.created_at)}</span>
          {showPlace && m.place && <span>{m.place.name}</span>}
          {m.people.length > 0 && <span>With {m.people.map((p) => p.name).join(", ")}</span>}
          {m.is_private && <span className="lock"><Lock size={14} aria-hidden="true" />Only you</span>}
          {m.added_by_caregiver && <span>Added by family</span>}
        </div>
        {actions}
      </div>
    </article>
  );
}

function FitBounds({ points }) {
  const map = useMap();
  useEffect(() => {
    if (!points.length) return;
    if (points.length === 1) map.setView(points[0], 15);
    else map.fitBounds(points, { padding: [40, 40] });
  }, [map, JSON.stringify(points)]);
  return null;
}

// OpenStreetMap tiles: free, no API key. Circles instead of pin images (no asset paths to break).
export function PlacesMap({ places, here, onPick, sticky = false }) {
  const pts = places.map((p) => [p.lat, p.lng]);
  const center = pts[0] || (here ? [here.lat, here.lng] : [19.076, 72.8777]);
  return (
    <div className={`map ${sticky ? "sticky" : ""}`}>
      <MapContainer center={center} zoom={13} style={{ height: "100%", width: "100%" }} scrollWheelZoom={false}>
        <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" />
        <FitBounds points={pts.length ? pts : here ? [[here.lat, here.lng]] : []} />
        {places.map((p) => (
          <CircleMarker key={p.id} center={[p.lat, p.lng]} radius={10 + Math.min(p.memory_count, 12)}
            pathOptions={{ color: "#1E2A5A", weight: 2, fillColor: "#F0A202", fillOpacity: 0.85 }}
            eventHandlers={{ click: () => onPick?.(p) }}>
            <Tooltip direction="top">{p.name} ({p.memory_count})</Tooltip>
          </CircleMarker>
        ))}
        {here && <CircleMarker center={[here.lat, here.lng]} radius={8} pathOptions={{ color: "#fff", weight: 3, fillColor: "#2F3F86", fillOpacity: 1 }}>
          <Tooltip>You are here</Tooltip></CircleMarker>}
      </MapContainer>
    </div>
  );
}

export function Empty({ title, children, action }) {
  return (
    <div className="panel stack" style={{ textAlign: "left" }}>
      <h3>{title}</h3>
      {children && <p className="muted">{children}</p>}
      {action}
    </div>
  );
}

export function PageHead({ title, sub, right }) {
  return (
    <div className="spread" style={{ marginBottom: 18 }}>
      <div className="stack" style={{ gap: 6 }}>
        <h1>{title}</h1>
        {sub && <p className="muted">{sub}</p>}
      </div>
      {right}
    </div>
  );
}

// ---- offline queue: captures made with no network are kept on the phone and sent later
const DB = "cc-offline", STORE = "captures";
function idb() {
  return new Promise((res, rej) => {
    const r = indexedDB.open(DB, 1);
    r.onupgradeneeded = () => r.result.createObjectStore(STORE, { keyPath: "id", autoIncrement: true });
    r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error);
  });
}
export async function queueCapture(fields) {
  const db = await idb();
  return new Promise((res, rej) => {
    const tx = db.transaction(STORE, "readwrite");
    tx.objectStore(STORE).add({ fields, at: Date.now() });
    tx.oncomplete = res; tx.onerror = () => rej(tx.error);
  });
}
export async function flushQueue() {
  let db; try { db = await idb(); } catch { return 0; }
  const all = await new Promise((res) => { const r = db.transaction(STORE).objectStore(STORE).getAll(); r.onsuccess = () => res(r.result || []); r.onerror = () => res([]); });
  let sent = 0;
  for (const item of all) {
    const fd = new FormData();
    Object.entries(item.fields).forEach(([k, v]) => v != null && fd.append(k, v));
    try {
      await api("/api/records", { method: "POST", form: fd });
      await new Promise((res) => { const tx = db.transaction(STORE, "readwrite"); tx.objectStore(STORE).delete(item.id); tx.oncomplete = res; });
      sent++;
    } catch { break; }
  }
  return sent;
}
