import { useEffect, useState } from "react";
import { FlaskConical, CheckCircle2, XCircle } from "lucide-react";
import { api } from "../api";
import { Notice, PageHead } from "../components";
import { fmtWhenInline } from "../hooks";

const TYPE_LABEL = { answerable: "Has an answer", unanswerable: "No answer exists", private: "Asks about a private memory", medical: "Asks for medical advice" };

export default function Research() {
  const [rep, setRep] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const [onlyFailed, setOnlyFailed] = useState(false);

  useEffect(() => { api("/api/eval/latest").then(setRep).catch(() => {}); }, []);
  const run = async () => {
    setBusy(true); setErr(null);
    try { setRep(await api("/api/eval/run", { method: "POST" })); } catch (e) { setErr(e.message); } finally { setBusy(false); }
  };
  const rows = rep ? rep.rows.filter((r) => !onlyFailed || !r.passed) : [];

  return (
    <div className="stack-lg">
      <PageHead title="Grounding test"
        sub="Asks a made-up person's memories a fixed set of questions and counts how often the answers stay true to what was saved. No real patient is involved."
        right={<button className="btn accent" onClick={run} disabled={busy}><FlaskConical size={20} aria-hidden="true" />{busy ? "Running…" : "Run the test"}</button>} />
      {err && <Notice kind="err" onClose={() => setErr(null)}>{err}</Notice>}
      {!rep && !busy && <p className="muted">No results yet. Run the test to measure the six AI requirements.</p>}
      {rep && (
        <>
          <p className="muted">Last run {fmtWhenInline(rep.ran_at)} using <b>{rep.provider}</b>. {rep.corpus.memories} memories ({rep.corpus.private} private), {rep.corpus.queries} questions: {rep.corpus.answerable} with an answer, {rep.corpus.unanswerable} without, {rep.corpus.private_probes} private, {rep.corpus.medical_probes} medical.</p>
          <div className="metrics">
            {rep.metrics.map((m) => (
              <div key={m.id} className={`metric ${m.passed ? "pass" : "fail"}`}>
                <div className="spread"><b>{m.id}</b>{m.passed ? <CheckCircle2 size={22} color="var(--leaf)" aria-label="Meets target" /> : <XCircle size={22} color="var(--sos)" aria-label="Misses target" />}</div>
                <p className="big-number" style={{ margin: "8px 0 4px" }}>{typeof m.value === "number" && m.id !== "NFR-AI-5" && m.id !== "NFR-AI-6" ? `${m.value}%` : m.value}</p>
                <p>{m.label}</p>
                <p className="small muted">Target {m.target}</p>
              </div>
            ))}
            <div className="metric">
              <b>Answer accuracy</b>
              <p className="big-number" style={{ margin: "8px 0 4px" }}>{rep.answer_accuracy.value}%</p>
              <p>Questions with an answer that cited the right memory</p>
              <p className="small muted">{rep.answer_accuracy.correct} of {rep.answer_accuracy.total}. Shows the system is not just refusing everything.</p>
            </div>
          </div>
          <section className="panel">
            <div className="panel-title">
              <h2>Every question</h2>
              <label className="switch" style={{ minHeight: 44 }}><input type="checkbox" checked={onlyFailed} onChange={(e) => setOnlyFailed(e.target.checked)} />Only show failures</label>
            </div>
            <div className="scroll-x">
              <table className="table">
                <thead><tr><th>Result</th><th>Question</th><th>Kind</th><th>What happened</th></tr></thead>
                <tbody>
                  {rows.map((r, i) => (
                    <tr key={i}>
                      <td>{r.passed ? <span className="badge done">Pass</span> : <span className="badge due">Fail</span>}</td>
                      <td><b>{r.question}</b></td>
                      <td className="muted">{TYPE_LABEL[r.type]}</td>
                      <td>{r.refused ? `Refused (${r.reason.replace(/_/g, " ")})` : `Answered, cited ${r.cited.join(", ")}`}{r.gold.length > 0 && <span className="muted"> Expected {r.gold.join(" or ")}.</span>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
