import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ArrowLeft, BellRing, Eye, EyeOff, HeartHandshake, Lock, LogIn, ShieldCheck, UserPlus, UserRound, Users } from "lucide-react";
import { useAuth } from "../auth";
import { Avatar, Notice } from "../components";

const DEMOS = [
  { email: "suresh@demo.in", name: "Suresh Patil", who: "Suresh", role: "Person using the app" },
  { email: "anita@demo.in", name: "Anita Patil", who: "Anita", role: "Primary caregiver" },
  { email: "rohan@demo.in", name: "Rohan Patil", who: "Rohan", role: "Caregiver, limited access" },
];

// Sign in or create an account. Used in the website's first screen and on /login.
export function AuthCard({ initialMode = "signin", showDemo = true }) {
  const { signIn, register } = useAuth();
  const [mode, setMode] = useState(initialMode);
  const [form, setForm] = useState({ name: "", email: "", password: "", role: "patient", phone: "" });
  const [show, setShow] = useState(false);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(null);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const run = async (key, fn) => {
    setBusy(key); setError(null);
    try { await fn(); } catch (e) { setError(e.message); setBusy(null); }
  };
  const submit = (e) => {
    e.preventDefault();
    run("form", () => (mode === "signin" ? signIn(form.email, form.password) : register(form)));
  };
  const signin = mode === "signin";

  return (
    <div className="auth-card">
      <div className="auth-head">
        <h2>{signin ? "Welcome back" : "Create your account"}</h2>
        <p className="muted">{signin ? "Sign in to your memories, reminders and family." : "It takes a minute. No app store needed."}</p>
      </div>
      <div className="seg" role="tablist" aria-label="Sign in or create an account">
        <button type="button" role="tab" aria-selected={signin} className={signin ? "on" : ""} onClick={() => { setMode("signin"); setError(null); }}>Sign in</button>
        <button type="button" role="tab" aria-selected={!signin} className={!signin ? "on" : ""} onClick={() => { setMode("register"); setError(null); }}>Create account</button>
      </div>
      <form className="stack" onSubmit={submit}>
        {!signin && (
          <>
            <div className="role-pick" role="radiogroup" aria-label="Who is this account for?">
              <button type="button" role="radio" aria-checked={form.role === "patient"} className="role-card" onClick={() => setForm({ ...form, role: "patient" })}>
                <UserRound size={26} aria-hidden="true" /><span><b>I'm saving my memories</b><small>For the person using the app</small></span>
              </button>
              <button type="button" role="radio" aria-checked={form.role === "caregiver"} className="role-card" onClick={() => setForm({ ...form, role: "caregiver" })}>
                <HeartHandshake size={26} aria-hidden="true" /><span><b>I care for someone</b><small>Family member or carer</small></span>
              </button>
            </div>
            <div className="field"><label htmlFor="a-name">Your name</label><input id="a-name" className="input" value={form.name} onChange={set("name")} required autoComplete="name" /></div>
          </>
        )}
        <div className="field"><label htmlFor="a-email">Email</label><input id="a-email" type="email" className="input" value={form.email} onChange={set("email")} required autoComplete="email" /></div>
        <div className="field">
          <label htmlFor="a-pw">Password</label>
          <div className="pw">
            <input id="a-pw" type={show ? "text" : "password"} className="input" value={form.password} onChange={set("password")} required minLength={6}
              autoComplete={signin ? "current-password" : "new-password"} />
            <button type="button" className="pw-toggle" onClick={() => setShow(!show)} aria-label={show ? "Hide password" : "Show password"}>
              {show ? <EyeOff size={20} /> : <Eye size={20} />}
            </button>
          </div>
          {!signin && <p className="small muted">At least 6 characters.</p>}
        </div>
        {!signin && form.role === "caregiver" && (
          <>
            <div className="field"><label htmlFor="a-phone">Phone number (for the Help button)</label><input id="a-phone" type="tel" className="input" value={form.phone} onChange={set("phone")} autoComplete="tel" /></div>
            <p className="small muted">Have an invite code? You will type it on the next screen.</p>
          </>
        )}
        {error && <Notice kind="err" onClose={() => setError(null)}>{error}</Notice>}
        <button className="btn accent block lg" disabled={!!busy}>
          {signin ? <LogIn size={22} aria-hidden="true" /> : <UserPlus size={22} aria-hidden="true" />}
          {busy === "form" ? "Please wait…" : signin ? "Sign in" : "Create account"}
        </button>
      </form>
      {showDemo && (
        <div className="auth-demo">
          <div className="divider"><span>or try the demo</span></div>
          <div className="demo-grid">
            {DEMOS.map((d) => (
              <button key={d.email} type="button" className="demo-btn" disabled={!!busy} onClick={() => run(d.email, () => signIn(d.email, "demo1234"))}>
                <Avatar name={d.name} /><span><b>{busy === d.email ? "Opening…" : d.who}</b><small>{d.role}</small></span>
              </button>
            ))}
          </div>
          <p className="small muted" style={{ marginTop: 8 }}>Demo memories are made up. No real patient data is used.</p>
        </div>
      )}
    </div>
  );
}

export default function Login() {
  const [params] = useSearchParams();
  const mode = params.get("mode") === "register" ? "register" : "signin";
  return (
    <div className="auth-page">
      <aside className="auth-aside">
        <Link to="/" className="brand"><img src="/icon-192.png" alt="" />Alzheimer Care Companion</Link>
        <div className="aside-body">
          <h1>Small moments, saved. Given back when they matter.</h1>
          <ul className="aside-points">
            <li><ShieldCheck size={24} aria-hidden="true" /><span><b>Answers you can trust</b>Built only from your own memories, with the source shown.</span></li>
            <li><Users size={24} aria-hidden="true" /><span><b>Family, on your terms</b>A primary caregiver decides what each family member can see.</span></li>
            <li><BellRing size={24} aria-hidden="true" /><span><b>Reminders you can hear</b>Read aloud, or in a family member's recorded voice.</span></li>
            <li><Lock size={24} aria-hidden="true" /><span><b>Private by design</b>Names and numbers are hidden before anything reaches the AI.</span></li>
          </ul>
        </div>
        <p className="aside-foot">Works on a phone or a computer, straight from the browser.</p>
      </aside>
      <main className="auth-main">
        <Link to="/" className="back-link"><ArrowLeft size={18} aria-hidden="true" />Back to the website</Link>
        <AuthCard key={mode} initialMode={mode} />
      </main>
    </div>
  );
}
