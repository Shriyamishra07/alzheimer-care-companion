import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Mic, Send, Volume2, Square, PenLine } from "lucide-react";
import { api, TZ } from "../api";
import { MemoryItem, Notice, PageHead } from "../components";
import { useApi } from "../hooks";

const SUGGEST = [
  "What did I do today?",
  "Who did I walk with this morning?",
  "Where are my car keys?",
  "Did I take my morning tablet today?",
  "When is Anita's birthday?",
];

const REASONS = {
  no_relevant_memory: "No saved memory matched the question.",
  unknown_name: "The question mentions a name or place that is not in your memories.",
  no_memories_in_that_time: "Nothing was saved in that time.",
  no_memories_yet: "Nothing has been saved yet.",
  guard_removed_everything: "The answer could not be matched to your memories, so it was not shown.",
  model_found_nothing: "Your memories do not answer this.",
  medical_advice_request: "Questions about medicines or doses go to a doctor.",
};

const Recognition = typeof window !== "undefined" && (window.SpeechRecognition || window.webkitSpeechRecognition);

export default function Ask() {
  const [params] = useSearchParams();
  const [q, setQ] = useState(params.get("q") || "");
  const [res, setRes] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const [listening, setListening] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const recRef = useRef(null);
  const resultRef = useRef(null);
  // On phones the answer appears below the suggestions: bring it into view.
  useEffect(() => { if (res && resultRef.current && window.innerWidth < 1120) resultRef.current.scrollIntoView({ behavior: "smooth", block: "start" }); }, [res]);
  const history = useApi("/api/ask/history");

  const ask = async (question) => {
    const text = (question ?? q).trim();
    if (text.length < 2) return;
    setQ(text); setBusy(true); setErr(null); setRes(null); window.speechSynthesis?.cancel(); setSpeaking(false);
    try { setRes(await api("/api/ask", { method: "POST", body: { question: text, tz: TZ } })); history.reload(); }
    catch (e) { setErr(e.message); }
    finally { setBusy(false); }
  };

  useEffect(() => { if (params.get("q")) ask(params.get("q")); }, []); // eslint-disable-line

  const listen = () => {
    if (!Recognition) return;
    const r = new Recognition();
    r.lang = "en-IN"; r.interimResults = true; r.maxAlternatives = 1;
    r.onresult = (e) => { const t = Array.from(e.results).map((x) => x[0].transcript).join(""); setQ(t); if (e.results[e.results.length - 1].isFinal) { r.stop(); ask(t); } };
    r.onend = () => setListening(false);
    r.onerror = () => { setListening(false); setErr("I couldn't hear that. You can type your question instead."); };
    recRef.current = r; setListening(true); r.start();
  };

  const speak = () => {
    if (!res || !window.speechSynthesis) return;
    if (speaking) { window.speechSynthesis.cancel(); setSpeaking(false); return; }
    const u = new SpeechSynthesisUtterance(res.answer.replace(/[“”]/g, ""));
    u.lang = "en-IN"; u.rate = 0.9;
    u.onend = () => setSpeaking(false);
    setSpeaking(true); window.speechSynthesis.speak(u);
  };

  const jump = (n) => document.getElementById(`source-${n}`)?.scrollIntoView({ behavior: "smooth", block: "center" });

  return (
    <div className="stack-lg">
      <PageHead title="Ask your memories" sub="Answers only use what you saved. Each part shows where it came from." />
      <form className="askbox" onSubmit={(e) => { e.preventDefault(); ask(); }}>
        <input className="input" aria-label="Your question" placeholder="Ask, for example: Where did I keep my glasses?" value={q} onChange={(e) => setQ(e.target.value)} style={{ fontSize: "1.1rem" }} />
        <div className="row" style={{ flexWrap: "nowrap", gap: 8 }}>
          {Recognition && (
            <button type="button" className={`btn ${listening ? "danger" : "quiet"}`} onClick={listening ? () => recRef.current?.stop() : listen} aria-label={listening ? "Stop listening" : "Ask by speaking"}>
              {listening ? <Square size={20} /> : <Mic size={22} />}
            </button>
          )}
          <button className="btn" disabled={busy}><Send size={20} aria-hidden="true" />Ask</button>
        </div>
      </form>
      {listening && <Notice kind="warn">Listening. Say your question.</Notice>}
      <div className="row">{SUGGEST.map((s) => <button key={s} className="chip" onClick={() => ask(s)}>{s}</button>)}</div>

      <div className="ask-layout" ref={resultRef}>
        <div className="stack">
          {busy && <p className="muted" aria-live="polite">Looking through your memories…</p>}
          {err && <Notice kind="err" onClose={() => setErr(null)}>{err}</Notice>}
          {res && !res.refused && (
            <section className="stack" aria-live="polite">
              <div className="answer stack">
                <p className="text">
                  {res.claims.map((c, i) => (
                    <span key={i}>{c.sentence}{c.source_numbers.map((n) => (
                      <button key={n} className="cite" onClick={() => jump(n)} aria-label={`Source ${n}`}>{n}</button>
                    ))}{" "}</span>
                  ))}
                </p>
                <div className="row">
                  {window.speechSynthesis && <button className="btn quiet sm" onClick={speak}><Volume2 size={18} aria-hidden="true" />{speaking ? "Stop reading" : "Read aloud"}</button>}
                </div>
              </div>
              <Checked res={res} />
            </section>
          )}
          {res && res.refused && (
            <section className="answer refused stack" aria-live="polite">
              <p className="text">{res.answer}</p>
              <p className="muted">{REASONS[res.reason] || ""}</p>
              {res.reason !== "medical_advice_request" && (
                <div className="row"><Link className="btn accent" to="/save?kind=text"><PenLine size={20} aria-hidden="true" />Save a memory about this</Link></div>
              )}
              <Checked res={res} />
            </section>
          )}
          {!res && !busy && !err && (
            <div className="panel tint">
              <p className="muted">Ask about anything you saved: where you kept something, who you met, what the doctor said, what you did yesterday.</p>
            </div>
          )}
        </div>
        <div className="stack">
          {res && !res.refused && (
            <section className="stack">
              <h2>Where this came from</h2>
              {res.sources.map((m, i) => (
                <div key={m.id} id={`source-${i + 1}`} className="source">
                  <span className="num">{i + 1}</span>
                  <MemoryItem m={m} fullDate />
                </div>
              ))}
            </section>
          )}
          {history.data?.length > 0 && (
            <section className="panel">
              <div className="panel-title"><h2>Recent questions</h2></div>
              <div className="list">
                {history.data.slice(0, 6).map((h) => (
                  <button key={h.id} className="list-item" style={{ background: "none", border: 0, borderTop: "1px solid var(--line)", textAlign: "left", cursor: "pointer", width: "100%" }} onClick={() => ask(h.question)}>
                    <div className="grow"><p><b>{h.question}</b></p><p className="small muted">{h.refused ? "No memory found" : h.answer.slice(0, 80) + (h.answer.length > 80 ? "…" : "")}</p></div>
                  </button>
                ))}
              </div>
            </section>
          )}
        </div>
      </div>
    </div>
  );
}

function Checked({ res }) {
  return (
    <details className="small muted">
      <summary style={{ cursor: "pointer", minHeight: 44, display: "flex", alignItems: "center" }}>How this answer was checked</summary>
      <div className="stack" style={{ gap: 6, paddingTop: 8 }}>
        <p>Memories looked at: {res.retrieved.length}. Sentences removed by the checker: {res.dropped.length}.</p>
        {res.dropped.map((d, i) => <p key={i}>Removed: “{d.sentence}” ({d.reason.replace(/_/g, " ")})</p>)}
        <p>Answered by: {res.provider}. Time: {res.latency_ms} ms.</p>
      </div>
    </details>
  );
}
