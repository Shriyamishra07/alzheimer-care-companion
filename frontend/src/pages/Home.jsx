import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Camera, Mic, PenLine, Check, MapPin, RotateCcw, Eye, Plus, MessageSquareHeart, Sparkles } from "lucide-react";
import { api, TZ, mediaUrl } from "../api";
import { useAuth } from "../auth";
import { Avatar, MemoryItem, Notice, Skeleton } from "../components";
import { fmtTime, fmtWhenInline, greeting, partOfDay, useApi, useClock, useLocation, setDemoLocation } from "../hooks";

export default function Home() {
  const { user } = useAuth();
  const now = useClock();
  const first = user.name.split(" ")[0];
  const today = now.toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long" });
  return (
    <div className="stack-lg">
      <div className="home-head">
        <div className="stack" style={{ gap: 4 }}>
          <h1>{greeting()}, {first}</h1>
          <p className="muted" style={{ fontSize: "1.1rem" }}>Today is {today}</p>
        </div>
        <div className="clock" aria-live="off">
          <p className="time">{fmtTime(now.toISOString())}</p>
          <p className="muted">{now.toLocaleDateString("en-IN", { weekday: "long" })} {partOfDay(now)}</p>
        </div>
      </div>
      <HereNow />
      <div className="home-grid">
        <div className="area-rem"><RemindersToday /></div>
        <div className="area-fam"><FamilyNotes /></div>
        <div className="area-today"><TodayList /></div>
        <div className="area-ask"><AskShortcut /></div>
        <div className="area-story"><StoryPrompt /></div>
        <div className="area-practice"><Practice /></div>
      </div>
    </div>
  );
}

// Short notes written by family members, shown like a message board.
function FamilyNotes() {
  const { data } = useApi("/api/records?kind=message&limit=3");
  if (!data || data.length === 0) return null;
  return (
    <section className="panel">
      <div className="panel-title"><h2>From your family</h2><MessageSquareHeart size={22} aria-hidden="true" style={{ color: "var(--marigold-deep)" }} /></div>
      {data.map((m) => {
        const [, who, msg] = m.display_text.match(/^Message from ([^:]+): ([\s\S]*)$/) || [null, "Family", m.display_text];
        return (
          <div className="fam-note" key={m.id}>
            <Avatar name={who} />
            <div><p className="msg">{msg}</p><p className="small muted">{who}, {fmtWhenInline(m.created_at)}</p></div>
          </div>
        );
      })}
    </section>
  );
}

// Life-story questions: one a day, answered by saving a memory. Reminiscence, in the person's own words.
const PROMPTS = [
  "Where did you grow up, and what was the street like?",
  "What was your first job? Who did you work with?",
  "Which festival did your family celebrate most? What did you eat?",
  "Tell the story of how you met your closest friend.",
  "What did your mother cook best?",
  "What is a song you loved when you were young?",
  "Describe your school. Who was your favourite teacher?",
  "What was the first place you travelled to by train?",
  "What game did you play as a child, and with whom?",
  "What is one piece of advice you would give your grandchildren?",
  "Tell about a day you were very proud.",
  "What did the monsoon feel like when you were small?",
  "Who taught you to cook, ride a bicycle or swim?",
  "What did your first home look like?",
];
function StoryPrompt() {
  const [offset, setOffset] = useState(0);
  const day = Math.floor(Date.now() / 86400000);
  const q = PROMPTS[(day + offset) % PROMPTS.length];
  return (
    <section className="panel story stack">
      <div className="spread"><h2>Tell your story</h2><Sparkles size={22} aria-hidden="true" style={{ color: "var(--marigold-deep)" }} /></div>
      <p className="q">{q}</p>
      <p className="small muted">Answer in your own words, by voice or by writing. It is saved as a memory you can come back to.</p>
      <div className="row">
        <Link className="btn" to={`/save?kind=voice&prompt=${encodeURIComponent(q)}`}><Mic size={20} aria-hidden="true" />Answer by voice</Link>
        <Link className="btn quiet" to={`/save?kind=text&prompt=${encodeURIComponent(q)}`}><PenLine size={20} aria-hidden="true" />Write it</Link>
        <button className="btn ghost" onClick={() => setOffset((o) => o + 1)}>Another question</button>
      </div>
    </section>
  );
}

function HereNow() {
  const loc = useLocation();
  const [near, setNear] = useState(null);
  useEffect(() => {
    if (!loc.coords) { setNear(null); return; }
    api(`/api/places/nearby?lat=${loc.coords.lat}&lng=${loc.coords.lng}&tz=${TZ}`).then(setNear).catch(() => setNear([]));
  }, [loc.coords?.lat, loc.coords?.lng]);

  const place = near?.[0];
  if (place) {
    const last = place.last[0];
    return (
      <section className="here" aria-live="polite">
        <p className="where">{loc.status === "demo" ? "Pretending you are at" : "You are at"}</p>
        <p className="place">{place.name}</p>
        <div className="count"><b>{place.memory_count}</b><span>{place.memory_count === 1 ? "memory saved here" : "memories saved here"}</span></div>
        {last && (
          <div className="last">
            <p className="small"><b>Last time here: {last.when}</b></p>
            <p>{last.display_text}</p>
            {place.people.length > 0 && <p className="small">With {place.people.join(", ")}</p>}
          </div>
        )}
        <div className="actions">
          <Link className="btn quiet" to={`/places/${place.id}`}><Eye size={20} aria-hidden="true" />See memories here</Link>
          <Link className="btn quiet" to="/save"><Camera size={20} aria-hidden="true" />Save this moment</Link>
          {loc.status === "demo" && <button className="btn ghost" onClick={() => setDemoLocation(null)}><RotateCcw size={18} aria-hidden="true" />Stop pretending</button>}
        </div>
      </section>
    );
  }

  return (
    <section className="here idle">
      <p className="where">{loc.status === "looking" || loc.status === "checking" ? "Finding where you are…" : "Save this moment"}</p>
      <p className="place">What is happening right now?</p>
      <div className="kinds">
        <Link className="kind" to="/save?kind=photo"><Camera size={28} aria-hidden="true" />Photo</Link>
        <Link className="kind" to="/save?kind=voice"><Mic size={28} aria-hidden="true" />Voice</Link>
        <Link className="kind" to="/save?kind=text"><PenLine size={28} aria-hidden="true" />Write</Link>
      </div>
      {loc.status === "prompt" && (
        <div className="loc-prime">
          <p>Turn on location and the app will remind you what happened when you come back to a place.</p>
          <button className="btn" onClick={loc.request}><MapPin size={20} aria-hidden="true" />Turn on location</button>
        </div>
      )}
      {loc.status === "denied" && <p className="small muted" style={{ marginTop: 14 }}>Location is blocked for this app. To turn it on, tap the lock icon next to the web address and allow Location.</p>}
      {loc.status === "live" && near && near.length === 0 && <p className="small muted" style={{ marginTop: 14 }}>No memories saved near here yet. Anything you save now will be linked to this place.</p>}
    </section>
  );
}

function TodayList() {
  const { data, loading, error } = useApi("/api/records?limit=120");
  const rows = (data || []).filter((m) => m.kind !== "message");
  const todays = rows.filter((m) => new Date(m.created_at).toDateString() === new Date().toDateString());
  const weekAgo = Date.now() - 7 * 86400000;
  const week = rows.filter((m) => new Date(m.created_at).getTime() >= weekAgo);
  const places = new Set(week.map((m) => m.place?.id).filter(Boolean)).size;
  const people = new Set(week.flatMap((m) => m.people.map((p) => p.id))).size;
  return (
    <section className="panel">
      <div className="panel-title"><h2>Today</h2><Link to="/memories">All memories</Link></div>
      {week.length > 0 && <p className="small muted" style={{ marginBottom: 10 }}>This week: {week.length} {week.length === 1 ? "memory" : "memories"}{places ? `, ${places} ${places === 1 ? "place" : "places"}` : ""}{people ? `, ${people} ${people === 1 ? "person" : "people"}` : ""}.</p>}
      {loading && <Skeleton lines={4} />}
      {error && <Notice kind="err">{error}</Notice>}
      {!loading && !error && todays.length === 0 && (
        <div className="stack" style={{ gap: 12 }}>
          <p className="muted">Nothing saved today yet.</p>
          <Link className="btn accent" to="/save" style={{ justifySelf: "start" }}><Plus size={20} aria-hidden="true" />Save a memory</Link>
        </div>
      )}
      {todays.map((m) => <MemoryItem key={m.id} m={m} />)}
    </section>
  );
}

function RemindersToday() {
  const { data, setData, error } = useApi(`/api/reminders?tz=${TZ}`);
  const [busy, setBusy] = useState(null);
  const done = async (id) => {
    setBusy(id);
    try { setData(await api(`/api/reminders/${id}/done?tz=${TZ}`, { method: "POST" })); } finally { setBusy(null); }
  };
  if (error) return <Notice kind="err">{error}</Notice>;
  if (!data) return <section className="panel"><div className="panel-title"><h2>Reminders</h2></div><Skeleton lines={3} /></section>;
  const open = data.filter((r) => r.status !== "done").length;
  return (
    <section className="panel">
      <div className="panel-title">
        <h2>Reminders</h2>
        <Link to="/reminders">{data.length ? "Change" : "Add one"}</Link>
      </div>
      {data.length === 0 && <p className="muted">No reminders set.</p>}
      {data.length > 0 && open === 0 && <p className="small muted" style={{ marginBottom: 6 }}>All done for today.</p>}
      <div className="list">
        {data.map((r) => (
          <div className="list-item" key={r.id}>
            <div className="grow">
              <p><b>{r.title}</b></p>
              <p className="small muted">{r.time}{r.status === "done" && r.done_at ? `, done at ${fmtTime(r.done_at)}` : ""}</p>
            </div>
            {r.status === "done"
              ? <span className="badge done"><Check size={16} aria-hidden="true" />Done</span>
              : <button className="btn sm" disabled={busy === r.id} onClick={() => done(r.id)}><Check size={18} aria-hidden="true" />Mark done</button>}
          </div>
        ))}
      </div>
    </section>
  );
}

const SUGGEST = ["What did I do today?", "Where did I keep my reading glasses?", "Did I take my morning tablet today?"];

function AskShortcut() {
  const nav = useNavigate();
  return (
    <section className="panel stack">
      <h2>Ask your memories</h2>
      <div className="row">
        {SUGGEST.map((q) => <button key={q} className="chip" onClick={() => nav(`/ask?q=${encodeURIComponent(q)}`)}>{q}</button>)}
      </div>
    </section>
  );
}

function Practice() {
  const { data, reload } = useApi("/api/practice");
  const [shown, setShown] = useState(false);
  if (!data) return null;
  const m = data.memory;
  return (
    <section className="practice stack">
      <h2>Memory practice</h2>
      {m.media_url && m.media_mime?.startsWith("image/") && <img className="preview" src={mediaUrl(m.media_url)} alt="" />}
      <p style={{ fontSize: "1.15rem" }}>{data.prompt}</p>
      {shown ? (
        <div className="notice ok"><div className="grow">
          <p>{m.display_text}</p>
          {m.people.length > 0 && <p className="small"><b>With {m.people.map((p) => p.name).join(", ")}</b></p>}
        </div></div>
      ) : <p className="small muted">Take your time. Think about it, then tap Show.</p>}
      <div className="row">
        {!shown && <button className="btn" onClick={() => setShown(true)}>Show</button>}
        <button className="btn quiet" onClick={() => { setShown(false); reload(); }}>Another one</button>
      </div>
    </section>
  );
}
