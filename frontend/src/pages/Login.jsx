import { useState } from "react";
import { Link } from "react-router-dom";
import { UserRound, HeartHandshake } from "lucide-react";
import { useAuth } from "../auth";
import { Notice } from "../components";

export default function Login() {
  const { signIn, register } = useAuth();
  const [mode, setMode] = useState("signin");
  const [form, setForm] = useState({ name: "", email: "", password: "", role: "patient", phone: "" });
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const run = async (fn) => {
    setBusy(true); setError(null);
    try { await fn(); } catch (e) { setError(e.message); } finally { setBusy(false); }
  };
  const submit = (e) => {
    e.preventDefault();
    run(() => (mode === "signin" ? signIn(form.email, form.password) : register(form)));
  };

  return (
    <div className="login-wrap">
      <div className="login">
        <div className="stack" style={{ gap: 14 }}>
          <Link to="/" className="small">Back to the website</Link>
          <img src="/icon-192.png" alt="" width="64" height="64" style={{ borderRadius: 16 }} />
          <h1>Alzheimer Care Companion</h1>
          <p className="muted" style={{ fontSize: "1.1rem" }}>Save small moments. Get them back by place, or by asking.</p>
        </div>

        <div className="panel stack">
          <div className="row" role="tablist">
            <button role="tab" aria-selected={mode === "signin"} className={`chip ${mode === "signin" ? "on" : ""}`} onClick={() => setMode("signin")}>Sign in</button>
            <button role="tab" aria-selected={mode === "register"} className={`chip ${mode === "register" ? "on" : ""}`} onClick={() => setMode("register")}>Create account</button>
          </div>
          <form className="stack" onSubmit={submit}>
            {mode === "register" && (
              <>
                <div className="field"><label htmlFor="name">Your name</label><input id="name" className="input" value={form.name} onChange={set("name")} required autoComplete="name" /></div>
                <fieldset className="stack" style={{ border: 0, padding: 0, margin: 0, gap: 10 }}>
                  <legend style={{ fontWeight: 700, marginBottom: 6 }}>Who is this account for?</legend>
                  <label className="switch"><input type="radio" name="role" checked={form.role === "patient"} onChange={() => setForm({ ...form, role: "patient" })} />I am saving my own memories</label>
                  <label className="switch"><input type="radio" name="role" checked={form.role === "caregiver"} onChange={() => setForm({ ...form, role: "caregiver" })} />I care for someone</label>
                </fieldset>
              </>
            )}
            <div className="field"><label htmlFor="email">Email</label><input id="email" type="email" className="input" value={form.email} onChange={set("email")} required autoComplete="email" /></div>
            <div className="field"><label htmlFor="pw">Password</label><input id="pw" type="password" className="input" value={form.password} onChange={set("password")} required minLength={6} autoComplete={mode === "signin" ? "current-password" : "new-password"} /></div>
            {mode === "register" && form.role === "caregiver" && (
              <div className="field"><label htmlFor="phone">Phone number (for the Help button)</label><input id="phone" type="tel" className="input" value={form.phone} onChange={set("phone")} autoComplete="tel" /></div>
            )}
            {error && <Notice kind="err" onClose={() => setError(null)}>{error}</Notice>}
            <button className="btn block" disabled={busy}>{mode === "signin" ? "Sign in" : "Create account"}</button>
          </form>
        </div>

        <div className="stack" style={{ gap: 10 }}>
          <h3>Try the demo</h3>
          <div className="demo-accounts">
            <button className="btn quiet block" disabled={busy} onClick={() => run(() => signIn("suresh@demo.in", "demo1234"))}>
              <UserRound size={22} aria-hidden="true" />Suresh, using the app
            </button>
            <button className="btn quiet block" disabled={busy} onClick={() => run(() => signIn("anita@demo.in", "demo1234"))}>
              <HeartHandshake size={22} aria-hidden="true" />Anita, his daughter and caregiver
            </button>
          </div>
          <p className="small muted">Demo memories are made up. No real patient data is used.</p>
        </div>
      </div>
    </div>
  );
}
