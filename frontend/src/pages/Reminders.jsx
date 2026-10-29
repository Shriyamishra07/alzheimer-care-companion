import { useState } from "react";
import { BellRing, Volume2 } from "lucide-react";
import { api, TZ } from "../api";
import { useAuth } from "../auth";
import { Notice, PageHead } from "../components";
import { useApi } from "../hooks";
import { ReminderForm, ReminderRow, speak } from "../reminders";

function DeviceAlerts({ name }) {
  const supported = typeof window !== "undefined" && "Notification" in window;
  const [perm, setPerm] = useState(supported ? Notification.permission : "unsupported");
  const ask = async () => { try { setPerm(await Notification.requestPermission()); } catch { /* ignored */ } };
  const test = () => speak(`Hello ${(name || "").split(" ")[0]}. This is how your reminders will sound.`);
  return (
    <section className="panel tint stack" style={{ gap: 12 }}>
      <div className="row" style={{ gap: 10 }}><BellRing size={22} aria-hidden="true" /><h2>Reminder alerts on this device</h2></div>
      <p className="muted">When a reminder is due, this app shows it on the full screen and reads it aloud, or plays the recorded voice message.</p>
      <div className="row">
        <button className="btn quiet sm" onClick={test}><Volume2 size={18} aria-hidden="true" />Hear a test reminder</button>
        {supported && perm !== "granted" && <button className="btn accent sm" onClick={ask}><BellRing size={18} aria-hidden="true" />Also show phone notifications</button>}
        {perm === "granted" && <span className="badge done">Phone notifications are on</span>}
      </div>
      {perm === "denied" && <p className="small muted">Notifications are blocked in this browser's settings. The full-screen reminder still works while the app is open.</p>}
      <p className="small muted">Keep the app open, or installed on the home screen, for reminders to appear on time.</p>
    </section>
  );
}

export default function Reminders() {
  const { user } = useAuth();
  const { data, setData, reload, error } = useApi(`/api/reminders?tz=${TZ}&scope=all`);
  const [busy, setBusy] = useState(null);
  const [msg, setMsg] = useState(null);
  const done = async (id) => {
    setBusy(id);
    try { await api(`/api/reminders/${id}/done?tz=${TZ}`, { method: "POST" }); reload(); window.dispatchEvent(new Event("cc:reminders-changed")); }
    finally { setBusy(null); }
  };
  const remove = async (r) => {
    try { await api(`/api/reminders/${r.id}`, { method: "DELETE" }); setData((data || []).filter((x) => x.id !== r.id)); window.dispatchEvent(new Event("cc:reminders-changed")); }
    catch (e) { setMsg(e.message); }
  };
  const today = (data || []).filter((r) => r.status !== "upcoming");
  const upcoming = (data || []).filter((r) => r.status === "upcoming");

  return (
    <div className="stack-lg" style={{ maxWidth: 820 }}>
      <PageHead title="Reminders" sub="Medicine, daily activities and appointments. Marking one as done saves it, so you can later ask “Did I take my tablet?”" />
      {error && <Notice kind="err">{error}</Notice>}
      {msg && <Notice kind="err" onClose={() => setMsg(null)}>{msg}</Notice>}
      <section className="panel">
        <div className="panel-title"><h2>Today</h2></div>
        <div className="list">{today.map((r) => <ReminderRow key={r.id} r={r} name={user.name} busy={busy} onDone={done} onRemove={remove} />)}</div>
        {data && today.length === 0 && <p className="muted">No reminders today.</p>}
      </section>
      {upcoming.length > 0 && (
        <section className="panel">
          <div className="panel-title"><h2>Coming up</h2></div>
          <div className="list">{upcoming.map((r) => <ReminderRow key={r.id} r={r} name={user.name} onRemove={remove} />)}</div>
        </section>
      )}
      <DeviceAlerts name={user.name} />
      <section className="panel">
        <h2 style={{ marginBottom: 12 }}>Add a reminder</h2>
        <ReminderForm onSaved={reload} />
      </section>
    </div>
  );
}
