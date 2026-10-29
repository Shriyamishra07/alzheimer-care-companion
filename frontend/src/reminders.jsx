// Voice reminders: medicine, activities and appointments, spoken aloud or played in a family member's voice.
import { useCallback, useEffect, useRef, useState } from "react";
import { AlarmClock, Bell, CalendarClock, Check, Footprints, Mic, Pill, Play, Plus, Square, Trash2, Volume2 } from "lucide-react";
import { api, mediaUrl, TZ } from "./api";
import { Notice } from "./components";

export const KINDS = {
  medication: { label: "Medicine", icon: Pill, say: "Time for your medicine" },
  activity: { label: "Activity", icon: Footprints, say: "Time for" },
  appointment: { label: "Appointment", icon: CalendarClock, say: "Remember your appointment" },
  other: { label: "Other", icon: Bell, say: "A reminder" },
};
export const kindOf = (k) => KINDS[k] || KINDS.other;

export function KindIcon({ kind, size = 22 }) {
  const Icon = kindOf(kind).icon;
  return <span className={`kind-ico ${KINDS[kind] ? kind : "other"}`} aria-hidden="true"><Icon size={size} /></span>;
}

const pad = (n) => String(n).padStart(2, "0");
export const localToday = () => { const d = new Date(); return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`; };
const nowHHMM = () => { const d = new Date(); return `${pad(d.getHours())}:${pad(d.getMinutes())}`; };
export function clock12(hhmm) {
  const [h, m] = hhmm.split(":").map(Number);
  return `${h % 12 || 12}:${pad(m)} ${h < 12 ? "AM" : "PM"}`;
}
export function whenText(r) {
  if (r.repeat === "once" && r.on_date) {
    const d = new Date(`${r.on_date}T00:00:00`);
    const day = d.toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" });
    return `${day}, ${clock12(r.time)}`;
  }
  return `Every day, ${clock12(r.time)}`;
}

// ---------------------------------------------------------------- speaking and playing
export function speak(text) {
  if (!("speechSynthesis" in window)) return false;
  window.speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.rate = 0.88;
  const en = window.speechSynthesis.getVoices().find((v) => /en[-_]IN/i.test(v.lang)) || null;
  if (en) u.voice = en;
  window.speechSynthesis.speak(u);
  return true;
}

export function spokenText(r, name) {
  const first = (name || "").split(" ")[0];
  const k = kindOf(r.kind);
  const what = r.kind === "activity" ? `${k.say} ${r.title}` : `${k.say}: ${r.title}`;
  return `${first ? `Hello ${first}. ` : ""}It is ${clock12(r.time)}. ${what}.${r.note ? ` ${r.note}` : ""}`;
}

// Plays the family recording if there is one, otherwise reads the reminder aloud. Resolves false if the browser blocked sound.
export async function playReminder(r, name) {
  if (r.voice_url) {
    try { const a = new Audio(mediaUrl(r.voice_url)); await a.play(); return true; } catch { /* fall back to speech */ }
  }
  if (r.speak !== false || !r.voice_url) return speak(spokenText(r, name));
  return false;
}

// ---------------------------------------------------------------- dictation and recording
function useDictation(onText) {
  const SR = typeof window !== "undefined" && (window.SpeechRecognition || window.webkitSpeechRecognition);
  const [on, setOn] = useState(false);
  const rec = useRef(null);
  const start = () => {
    if (!SR) return;
    const r = new SR();
    r.lang = "en-IN"; r.interimResults = false; r.maxAlternatives = 1;
    r.onresult = (e) => onText(e.results[0][0].transcript.replace(/^\w/, (c) => c.toUpperCase()));
    r.onend = () => setOn(false);
    r.onerror = () => setOn(false);
    rec.current = r; setOn(true); r.start();
  };
  return { supported: !!SR, on, start, stop: () => rec.current?.stop() };
}

export function VoiceRecorder({ value, onChange }) {
  const [rec, setRec] = useState(null);
  const [secs, setSecs] = useState(0);
  const [err, setErr] = useState(null);
  const chunks = useRef([]);
  useEffect(() => { if (!rec) return; const t = setInterval(() => setSecs((s) => s + 1), 1000); return () => clearInterval(t); }, [rec]);
  useEffect(() => { if (rec && secs >= 60) rec.stop(); }, [secs, rec]);
  const start = async () => {
    setErr(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const type = ["audio/webm;codecs=opus", "audio/mp4", "audio/webm"].find((t) => window.MediaRecorder?.isTypeSupported?.(t)) || "";
      const mr = new MediaRecorder(stream, type ? { mimeType: type } : undefined);
      chunks.current = [];
      mr.ondataavailable = (e) => e.data.size && chunks.current.push(e.data);
      mr.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunks.current, { type: mr.mimeType || "audio/webm" });
        onChange({ blob, url: URL.createObjectURL(blob) }); setRec(null);
      };
      setSecs(0); mr.start(); setRec(mr);
    } catch { setErr("The microphone is not available. Allow microphone access in the browser, then try again."); }
  };
  if (rec) {
    return (
      <div className="rec">
        <span className="rec-dot" aria-hidden="true" /><span>Recording… {secs}s (up to 60s)</span>
        <button type="button" className="btn sm" onClick={() => rec.stop()}><Square size={18} aria-hidden="true" />Stop</button>
      </div>
    );
  }
  return (
    <div className="stack" style={{ gap: 8 }}>
      {value ? (
        <div className="rec">
          <audio controls src={value.url} style={{ maxWidth: "100%" }} />
          <button type="button" className="btn ghost sm" onClick={() => onChange(null)}><Trash2 size={18} aria-hidden="true" />Remove</button>
        </div>
      ) : (
        <button type="button" className="btn quiet sm" onClick={start}><Mic size={18} aria-hidden="true" />Record a voice message</button>
      )}
      {err && <Notice kind="err" onClose={() => setErr(null)}>{err}</Notice>}
    </div>
  );
}

// ---------------------------------------------------------------- the form
const EMPTY = { title: "", kind: "medication", time: "09:00", repeat: "daily", on_date: "", note: "", speak: true };

export function ReminderForm({ patientId, forName, onSaved }) {
  const [f, setF] = useState(EMPTY);
  const [voice, setVoice] = useState(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);
  const dict = useDictation((t) => setF((x) => ({ ...x, title: t })));
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  const submit = async (e) => {
    e.preventDefault(); setBusy(true); setMsg(null);
    try {
      const body = { ...f, on_date: f.repeat === "once" ? f.on_date : null, ...(patientId ? { patient_id: patientId } : {}) };
      const r = await api(`/api/reminders?tz=${TZ}`, { method: "POST", body });
      if (voice?.blob) {
        const fd = new FormData();
        fd.append("file", voice.blob, voice.blob.type.includes("mp4") ? "voice.m4a" : "voice.webm");
        await api(`/api/reminders/${r.id}/voice`, { method: "POST", form: fd });
      }
      setF(EMPTY); setVoice(null);
      setMsg({ kind: "ok", text: "Reminder saved." });
      window.dispatchEvent(new Event("cc:reminders-changed"));
      onSaved?.();
    } catch (err) { setMsg({ kind: "err", text: err.message }); }
    finally { setBusy(false); }
  };

  return (
    <form className="stack" onSubmit={submit}>
      <div className="field">
        <label htmlFor="rem-title">What to remember{forName ? ` for ${forName}` : ""}</label>
        <div className="row" style={{ flexWrap: "nowrap" }}>
          <input id="rem-title" className="input" placeholder="For example: Morning tablet" value={f.title} onChange={set("title")} required maxLength={160} />
          {dict.supported && (
            <button type="button" className={`btn ${dict.on ? "danger" : "quiet"}`} onClick={dict.on ? dict.stop : dict.start}
              aria-label={dict.on ? "Stop listening" : "Say it instead of typing"} title="Say it instead of typing">
              <Mic size={20} aria-hidden="true" />
            </button>
          )}
        </div>
      </div>
      <fieldset className="field" style={{ border: 0, padding: 0, margin: 0 }}>
        <legend style={{ fontWeight: 500, marginBottom: 6 }}>Type</legend>
        <div className="kind-pick">
          {Object.entries(KINDS).map(([k, v]) => {
            const Icon = v.icon;
            return <button type="button" key={k} className={`chip ${f.kind === k ? "on" : ""}`} aria-pressed={f.kind === k}
              onClick={() => setF({ ...f, kind: k, repeat: k === "appointment" ? "once" : f.repeat })}><Icon size={18} aria-hidden="true" />{v.label}</button>;
          })}
        </div>
      </fieldset>
      <div className="grid-auto">
        <div className="field"><label htmlFor="rem-time">Time</label><input id="rem-time" type="time" className="input" value={f.time} onChange={set("time")} required /></div>
        <div className="field">
          <span style={{ fontWeight: 500 }}>Repeat</span>
          <div className="seg" role="radiogroup" aria-label="Repeat">
            <button type="button" role="radio" aria-checked={f.repeat === "daily"} className={f.repeat === "daily" ? "on" : ""} onClick={() => setF({ ...f, repeat: "daily" })}>Every day</button>
            <button type="button" role="radio" aria-checked={f.repeat === "once"} className={f.repeat === "once" ? "on" : ""} onClick={() => setF({ ...f, repeat: "once" })}>One time</button>
          </div>
        </div>
      </div>
      {f.repeat === "once" && (
        <div className="field"><label htmlFor="rem-date">Date</label><input id="rem-date" type="date" className="input" min={localToday()} value={f.on_date} onChange={set("on_date")} required /></div>
      )}
      <div className="field"><label htmlFor="rem-note">Note (optional)</label><input id="rem-note" className="input" placeholder="For example: After breakfast, with water" value={f.note} onChange={set("note")} maxLength={300} /></div>
      <div className="field">
        <span style={{ fontWeight: 500 }}>Voice</span>
        <label className="switch"><input type="checkbox" checked={f.speak} onChange={(e) => setF({ ...f, speak: e.target.checked })} />Read the reminder aloud when it is time</label>
        <p className="small muted">You can also record it in your own voice. A familiar voice is easier to follow.</p>
        <VoiceRecorder value={voice} onChange={setVoice} />
      </div>
      {msg && <Notice kind={msg.kind} onClose={() => setMsg(null)}>{msg.text}</Notice>}
      <button className="btn accent" disabled={busy}><Plus size={20} aria-hidden="true" />{busy ? "Saving…" : "Save reminder"}</button>
      <p className="small muted">This app does not give advice about medicines. Ask your doctor about doses.</p>
    </form>
  );
}

// ---------------------------------------------------------------- one reminder in a list
export function ReminderRow({ r, name, onDone, onRemove, busy }) {
  const statusText = { done: "Done today", due: "Not done yet", later: "Later today", upcoming: "Coming up" }[r.status];
  return (
    <div className="list-item rem-row">
      <KindIcon kind={r.kind} />
      <div className="grow">
        <p><b>{r.title}</b></p>
        <p className="small muted">{whenText(r)}{r.note ? ` · ${r.note}` : ""}</p>
        {(r.voice_url || r.speak) && <p className="small rem-voice"><Volume2 size={14} aria-hidden="true" />{r.voice_url ? "Recorded voice message" : "Read aloud"}</p>}
      </div>
      <button type="button" className="btn ghost sm" onClick={() => playReminder(r, name)} aria-label={`Play the ${r.title} reminder`}><Play size={18} aria-hidden="true" /></button>
      {statusText && <span className={`badge ${r.status === "upcoming" ? "later" : r.status}`}>{statusText}</span>}
      {onDone && r.status !== "done" && r.status !== "upcoming" && (
        <button className="btn sm" disabled={busy === r.id} onClick={() => onDone(r.id)}><Check size={18} aria-hidden="true" />Done</button>
      )}
      {onRemove && <button className="btn ghost sm" onClick={() => onRemove(r)} aria-label={`Remove ${r.title}`}><Trash2 size={18} /></button>}
    </div>
  );
}

// ---------------------------------------------------------------- the alert when a reminder is due
const stateKey = () => `cc_rem_${localToday()}`;
const readState = () => { try { return JSON.parse(localStorage.getItem(stateKey()) || "{}"); } catch { return {}; } };
const writeState = (s) => { try { localStorage.setItem(stateKey(), JSON.stringify(s)); } catch { /* private mode */ } };
const minutesSince = (hhmm) => { const [h, m] = hhmm.split(":").map(Number); const d = new Date(); return d.getHours() * 60 + d.getMinutes() - (h * 60 + m); };

async function notify(r, name) {
  if (!("Notification" in window) || Notification.permission !== "granted" || document.visibilityState === "visible") return;
  try {
    const reg = await navigator.serviceWorker?.ready;
    const opts = { body: `${clock12(r.time)}${r.note ? ` · ${r.note}` : ""}`, tag: `rem-${r.id}`, renotify: true, requireInteraction: true, icon: "/icon-192.png", badge: "/icon-192.png" };
    if (reg) reg.showNotification(r.title, opts); else new Notification(r.title, opts);
  } catch { /* notifications are a bonus; the in-app alert is the main one */ }
}

export function ReminderAlerts({ name }) {
  const [list, setList] = useState([]);
  const [current, setCurrent] = useState(null);
  const [blocked, setBlocked] = useState(false);
  const load = useCallback(async () => { try { setList(await api(`/api/reminders?tz=${TZ}`)); } catch { /* offline: try later */ } }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 60000);
    const again = () => load();
    window.addEventListener("focus", again);
    window.addEventListener("cc:reminders-changed", again);
    return () => { clearInterval(t); window.removeEventListener("focus", again); window.removeEventListener("cc:reminders-changed", again); };
  }, [load]);

  useEffect(() => {
    const check = () => {
      if (current) return;
      const st = readState();
      const now = Date.now();
      const hhmm = nowHHMM();
      const due = list.find((r) => r.status !== "done" && r.status !== "upcoming" && r.time <= hhmm && minutesSince(r.time) <= 120 &&
        (!st[r.id] || (st[r.id].snooze && now >= st[r.id].snooze)));
      if (!due) return;
      writeState({ ...st, [due.id]: { shown: now } });
      setCurrent(due);
      notify(due, name);
      playReminder(due, name).then((ok) => setBlocked(!ok));
    };
    check();
    const t = setInterval(check, 15000);
    return () => clearInterval(t);
  }, [list, current, name]);

  if (!current) return null;
  const done = async () => {
    try { setList(await api(`/api/reminders/${current.id}/done?tz=${TZ}`, { method: "POST" })); window.dispatchEvent(new Event("cc:reminders-changed")); } catch { /* keep it open */ }
    window.speechSynthesis?.cancel(); setCurrent(null);
  };
  const snooze = () => {
    writeState({ ...readState(), [current.id]: { snooze: Date.now() + 10 * 60000 } });
    window.speechSynthesis?.cancel(); setCurrent(null);
  };
  return (
    <div className="rem-alert" role="alertdialog" aria-modal="true" aria-labelledby="rem-alert-title">
      <div className="card">
        <KindIcon kind={current.kind} size={40} />
        <p className="eyebrow">{kindOf(current.kind).label} reminder</p>
        <h2 id="rem-alert-title">{current.title}</h2>
        <p className="time">{clock12(current.time)}{current.note ? ` · ${current.note}` : ""}</p>
        <div className="actions">
          <button className={`btn ${blocked ? "accent" : "quiet"} lg`} onClick={() => playReminder(current, name).then((ok) => setBlocked(!ok))}>
            <Volume2 size={22} aria-hidden="true" />{blocked ? "Play the reminder" : "Play again"}
          </button>
          <button className="btn lg" onClick={done}><Check size={22} aria-hidden="true" />Done</button>
          <button className="btn quiet lg" onClick={snooze}><AlarmClock size={22} aria-hidden="true" />Remind me in 10 minutes</button>
        </div>
      </div>
    </div>
  );
}
