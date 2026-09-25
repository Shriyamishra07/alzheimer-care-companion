import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Camera, Mic, PenLine, Square, MapPin, Lock, Check, Trash2, Plus } from "lucide-react";
import { api } from "../api";
import { MemoryItem, Notice, PageHead, queueCapture } from "../components";
import { useApi, useLocation } from "../hooks";

// Photos are shrunk on the phone before upload: faster on mobile data, small enough to store.
async function shrinkImage(file, max = 1280) {
  const img = await new Promise((res, rej) => { const i = new Image(); i.onload = () => res(i); i.onerror = rej; i.src = URL.createObjectURL(file); });
  const scale = Math.min(1, max / Math.max(img.width, img.height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(img.width * scale); canvas.height = Math.round(img.height * scale);
  canvas.getContext("2d").drawImage(img, 0, 0, canvas.width, canvas.height);
  return new Promise((res) => canvas.toBlob((b) => res(b), "image/jpeg", 0.82));
}

export default function Capture() {
  const [params] = useSearchParams();
  const prompt = params.get("prompt") || "";
  const [kind, setKind] = useState(params.get("kind") || "photo");
  const [text, setText] = useState("");
  const [blob, setBlob] = useState(null);
  const [preview, setPreview] = useState(null);
  const [picked, setPicked] = useState([]);
  const [newName, setNewName] = useState("");
  const [newPeople, setNewPeople] = useState([]);
  const [isPrivate, setIsPrivate] = useState(false);
  const [state, setState] = useState({ busy: false, done: null, error: null });
  const loc = useLocation();
  const people = useApi("/api/people");

  useEffect(() => { setBlob(null); setPreview(null); }, [kind]);

  const reset = () => { setText(""); setBlob(null); setPreview(null); setPicked([]); setNewPeople([]); setIsPrivate(false); setState({ busy: false, done: null, error: null }); };

  const onPhoto = async (e) => {
    const f = e.target.files?.[0]; if (!f) return;
    const small = await shrinkImage(f).catch(() => f);
    setBlob(small); setPreview(URL.createObjectURL(small));
  };

  const addName = () => {
    const n = newName.trim(); if (!n) return;
    const existing = (people.data || []).find((p) => p.name.toLowerCase() === n.toLowerCase());
    if (existing) setPicked((p) => (p.includes(existing.id) ? p : [...p, existing.id]));
    else setNewPeople((p) => (p.includes(n) ? p : [...p, n]));
    setNewName("");
  };

  const save = async () => {
    if (prompt && !text.trim() && !blob) { setState({ ...state, error: kind === "voice" ? "Record your answer first." : "Write your answer first." }); return; }
    if (!text.trim() && !blob) { setState({ ...state, error: kind === "text" ? "Write a few words first." : kind === "photo" ? "Take or choose a photo first." : "Record a voice note first." }); return; }
    const saved = prompt ? `${prompt} ${text.trim()}`.trim() : text;
    const fields = { kind, text: saved, is_private: String(isPrivate), person_ids: picked.join(","), new_people: newPeople.join(",") };
    if (loc.coords) { fields.lat = String(loc.coords.lat); fields.lng = String(loc.coords.lng); }
    const fd = new FormData();
    Object.entries(fields).forEach(([k, v]) => fd.append(k, v));
    if (blob) fd.append("file", blob, kind === "photo" ? "photo.jpg" : `voice.${blob.type.includes("mp4") ? "m4a" : "webm"}`);
    setState({ busy: true, done: null, error: null });
    try {
      const rec = await api("/api/records", { method: "POST", form: fd });
      setState({ busy: false, done: { rec, offline: false }, error: null });
    } catch (e) {
      if (e.status === 0) {
        await queueCapture({ ...fields, file: blob || null });
        setState({ busy: false, done: { offline: true }, error: null });
      } else setState({ busy: false, done: null, error: e.message });
    }
  };

  if (state.done) {
    const rec = state.done.rec;
    const sub = state.done.offline ? "Saved on this phone. It will upload by itself when you are back online."
      : rec?.place ? `Linked to ${rec.place.name}.` : "Saved without a place, because location was off.";
    return (
      <div className="stack-lg" style={{ maxWidth: 720 }}>
        <PageHead title="Memory saved" sub={sub} />
        {rec && <section className="panel"><MemoryItem m={rec} fullDate /></section>}
        <div className="row">
          <button className="btn accent" onClick={reset}><Plus size={20} aria-hidden="true" />Save another</button>
          {rec?.place && <Link className="btn quiet" to={`/places/${rec.place.id}`}><MapPin size={20} aria-hidden="true" />Open {rec.place.name}</Link>}
          <Link className="btn quiet" to="/">Go to Home</Link>
        </div>
      </div>
    );
  }

  return (
    <div className="stack-lg" style={{ maxWidth: 720 }}>
      <PageHead title={prompt ? "Tell your story" : "Save a memory"} sub={prompt ? "Answer in your own words. It is saved as a memory." : "The time and place are added for you."} />
      {prompt && <div className="panel story"><p className="q">{prompt}</p></div>}
      <div className="kinds" role="radiogroup" aria-label="Type of memory">
        {[["photo", "Photo", Camera], ["voice", "Voice", Mic], ["text", "Write", PenLine]].map(([k, label, Icon]) => (
          <button key={k} role="radio" aria-checked={kind === k} className={`kind ${kind === k ? "on" : ""}`} onClick={() => setKind(k)}>
            <Icon size={30} aria-hidden="true" />{label}
          </button>
        ))}
      </div>

      {kind === "photo" && (
        <div className="stack">
          {preview && <img className="preview" src={preview} alt="The photo you chose" />}
          <label className="btn accent block" style={{ cursor: "pointer" }}>
            <Camera size={22} aria-hidden="true" />{preview ? "Take a different photo" : "Take a photo"}
            <input type="file" accept="image/*" capture="environment" onChange={onPhoto} className="sr-only" />
          </label>
        </div>
      )}
      {kind === "voice" && <VoiceRecorder blob={blob} onDone={(b) => { setBlob(b); setPreview(b ? URL.createObjectURL(b) : null); }} preview={preview} />}

      <div className="field">
        <label htmlFor="words">{prompt ? (kind === "text" ? "Your answer" : "Add a few words (you can skip this)") : kind === "text" ? "What do you want to remember?" : "Add a few words (you can skip this)"}</label>
        <textarea id="words" className="textarea" value={text} onChange={(e) => setText(e.target.value)}
          placeholder={kind === "text" ? "For example: I kept the house keys in the blue bowl." : "For example: Lunch with Anita."} />
      </div>

      <div className="stack" style={{ gap: 10 }}>
        <p><b>Who was with you?</b></p>
        <div className="row">
          {(people.data || []).map((p) => (
            <button key={p.id} className={`chip ${picked.includes(p.id) ? "on" : ""}`} aria-pressed={picked.includes(p.id)}
              onClick={() => setPicked((x) => (x.includes(p.id) ? x.filter((i) => i !== p.id) : [...x, p.id]))}>{p.name}</button>
          ))}
          {newPeople.map((n) => <button key={n} className="chip on" onClick={() => setNewPeople((x) => x.filter((y) => y !== n))}>{n}</button>)}
        </div>
        <div className="row" style={{ flexWrap: "nowrap" }}>
          <input className="input" aria-label="Add a name" placeholder="Add a name" value={newName} onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addName(); } }} />
          <button className="btn quiet" onClick={addName}>Add</button>
        </div>
      </div>

      <label className="switch">
        <input type="checkbox" checked={isPrivate} onChange={(e) => setIsPrivate(e.target.checked)} />
        <span><Lock size={18} aria-hidden="true" /> <b>Keep private.</b> Family can't see it and Ask won't use it.</span>
      </label>

      <LocationLine loc={loc} />

      {state.error && <Notice kind="err" onClose={() => setState({ ...state, error: null })}>{state.error}</Notice>}
      <button className="btn accent block" onClick={save} disabled={state.busy}><Check size={22} aria-hidden="true" />{state.busy ? "Saving…" : "Save memory"}</button>
    </div>
  );
}

function VoiceRecorder({ blob, onDone, preview }) {
  const [rec, setRec] = useState(null);
  const [secs, setSecs] = useState(0);
  const [err, setErr] = useState(null);
  const chunks = useRef([]);
  useEffect(() => {
    if (!rec) return;
    const t = setInterval(() => setSecs((s) => { if (s >= 119) rec.stop(); return s + 1; }), 1000);
    return () => clearInterval(t);
  }, [rec]);

  const start = async () => {
    setErr(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const type = ["audio/webm;codecs=opus", "audio/mp4", "audio/webm"].find((t) => window.MediaRecorder?.isTypeSupported?.(t)) || "";
      const mr = new MediaRecorder(stream, type ? { mimeType: type } : undefined);
      chunks.current = [];
      mr.ondataavailable = (e) => e.data.size && chunks.current.push(e.data);
      mr.onstop = () => { stream.getTracks().forEach((t) => t.stop()); onDone(new Blob(chunks.current, { type: mr.mimeType || "audio/webm" })); setRec(null); };
      mr.start(); setSecs(0); setRec(mr);
    } catch { setErr("The microphone could not start. Allow microphone access in your browser settings."); }
  };

  return (
    <div className="stack">
      {rec ? (
        <button className="btn danger block" onClick={() => rec.stop()}><Square size={20} aria-hidden="true" />Stop recording ({secs}s)</button>
      ) : (
        <button className="btn accent block" onClick={start}><Mic size={22} aria-hidden="true" />{blob ? "Record again" : "Start recording"}</button>
      )}
      {rec && <p className="row"><span className="rec-dot" aria-hidden="true" /> Recording. Speak normally.</p>}
      {preview && !rec && (
        <div className="row" style={{ flexWrap: "nowrap" }}>
          <audio controls src={preview} style={{ flex: 1 }} />
          <button className="btn ghost" aria-label="Remove recording" onClick={() => onDone(null)}><Trash2 size={20} /></button>
        </div>
      )}
      {err && <Notice kind="err">{err}</Notice>}
    </div>
  );
}

function LocationLine({ loc }) {
  if (loc.coords) {
    return (
      <p className="small muted"><MapPin size={16} aria-hidden="true" style={{ verticalAlign: "-3px", marginRight: 6 }} />
        {loc.status === "demo" ? "Using the pretend location." : "Your location will be saved with this memory."}</p>
    );
  }
  if (loc.status === "prompt") {
    return (
      <div className="loc-prime" style={{ marginTop: 0 }}>
        <p>Location is off, so this memory won't be linked to a place.</p>
        <button type="button" className="btn quiet sm" onClick={loc.request}><MapPin size={18} aria-hidden="true" />Turn on location</button>
      </div>
    );
  }
  const text = {
    denied: "Location is blocked for this app, so this memory won't be linked to a place.",
    unavailable: "Your location could not be found, so this memory won't be linked to a place.",
    unsupported: "This device can't share its location.",
  }[loc.status] || "Finding your location…";
  return <p className="small muted">{text}</p>;
}
