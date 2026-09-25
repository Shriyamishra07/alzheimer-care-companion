import { useState } from "react";
import { Link } from "react-router-dom";
import { LogOut, ChevronRight } from "lucide-react";
import { api } from "../api";
import { useAuth } from "../auth";
import { Notice, PageHead, PATIENT_NAV, navGroups } from "../components";
import { applyTheme, getTheme, useApi } from "../hooks";

export function Settings() {
  const { user, setUser, signOut } = useAuth();
  const health = useApi("/api/health");
  const [form, setForm] = useState({ name: user.name, phone: user.phone || "" });
  const [larger, setLarger] = useState(document.documentElement.classList.contains("larger"));
  const [theme, setTheme] = useState(getTheme());
  const pickTheme = (t) => { setTheme(t); applyTheme(t); };
  const [saved, setSaved] = useState(false);

  const toggleLarger = (on) => {
    setLarger(on);
    document.documentElement.classList.toggle("larger", on);
    try { localStorage.setItem("cc_larger", on ? "1" : "0"); } catch { /* ignore */ }
  };
  const save = async (e) => { e.preventDefault(); setUser(await api("/api/me", { method: "PATCH", body: form })); setSaved(true); };

  return (
    <div className="stack-lg" style={{ maxWidth: 680 }}>
      <PageHead title="Settings" />
      <section className="panel stack">
        <h2>Reading</h2>
        <label className="switch"><input type="checkbox" checked={larger} onChange={(e) => toggleLarger(e.target.checked)} /><span><b>Larger text</b> everywhere in the app</span></label>
        <div className="stack" style={{ gap: 8 }}>
          <p><b>Colours</b></p>
          <div className="seg" role="group" aria-label="Colours">
            {[["system", "Match my device"], ["light", "Light"], ["dark", "Dark"]].map(([k, label]) => <button key={k} className={theme === k ? "on" : ""} aria-pressed={theme === k} onClick={() => pickTheme(k)}>{label}</button>)}
          </div>
        </div>
      </section>
      <section className="panel">
        <h2 style={{ marginBottom: 12 }}>Your details</h2>
        <form className="stack" onSubmit={save}>
          <div className="field"><label htmlFor="sn">Name</label><input id="sn" className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
          <div className="field"><label htmlFor="sp">Phone number</label><input id="sp" type="tel" className="input" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} /></div>
          {saved && <Notice kind="ok" onClose={() => setSaved(false)}>Details saved.</Notice>}
          <button className="btn">Save details</button>
        </form>
      </section>
      <section className="panel stack">
        <h2>About</h2>
        <p className="muted">Signed in as {user.email}. Answers use {health.data ? <b>{health.data.provider}</b> : "…"} mode.</p>
        <p className="small muted">Alzheimer Care Companion, BE project, Department of Computer Engineering, Terna Engineering College, Nerul. A.Y. 2026–27.</p>
        <button className="btn quiet" onClick={signOut}><LogOut size={20} aria-hidden="true" />Sign out</button>
      </section>
    </div>
  );
}

export function More() {
  // Everything that isn't already in the bottom bar, in the same groups as the desktop sidebar.
  const groups = navGroups(PATIENT_NAV.filter((n) => !n.bottom));
  return (
    <div className="stack-lg">
      <PageHead title="More" />
      {groups.map((g) => (
        <section key={g.name} className="stack" style={{ gap: 8 }}>
          <h2 className="small muted" style={{ fontSize: "0.95rem", fontWeight: 600 }}>{g.name}</h2>
          <div className="panel" style={{ padding: "4px 20px" }}>
            <div className="list">
              {g.items.map((n) => (
                <Link key={n.to} to={n.to} className="list-item">
                  <n.icon size={24} aria-hidden="true" style={{ color: "var(--ink-2)", flexShrink: 0 }} />
                  <span className="grow"><b>{n.label}</b></span>
                  <ChevronRight size={22} aria-hidden="true" className="muted" />
                </Link>
              ))}
            </div>
          </div>
        </section>
      ))}
    </div>
  );
}
