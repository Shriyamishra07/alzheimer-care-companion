import { useState } from "react";
import { Link } from "react-router-dom";
import {
  Camera, Mic, PenLine, MapPin, MessageCircleQuestion, ShieldCheck, HeartHandshake, Siren, Lock, Check, FlaskConical,
  ALargeSmall, Hand, Ear, Users, Bell, Eye, Volume2, UserRound,
} from "lucide-react";
import { useAuth } from "../auth";
import { Notice } from "../components";
import { AuthCard } from "./Login";

const TARGETS = [
  ["NFR-AI-1", "Every statement traceable to a saved memory", "95% or more"],
  ["NFR-AI-2", "Unsupported statements", "2% or less"],
  ["NFR-AI-3", "Correct refusal when nothing relevant exists", "90% or more"],
  ["NFR-AI-4", "Answers that show their sources", "100%"],
  ["NFR-AI-5", "Medical or dosage advice given", "0"],
  ["NFR-AI-6", "Private memories appearing in answers", "0"],
];

export default function Landing() {
  const { signIn } = useAuth();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const demo = async (email) => {
    setBusy(true); setErr(null);
    try { await signIn(email, "demo1234"); } catch (e) { setErr(e.message); setBusy(false); }
  };

  return (
    <div className="site">
      <header className="site-header">
        <div className="in">
          <Link to="/" className="brand"><img src="/icon-192.png" alt="" /><span className="full">Alzheimer Care Companion</span><span className="short">Care Companion</span></Link>
          <nav className="site-nav" aria-label="Sections">
            <a href="#how">How it works</a>
            <a href="#trust">Answers you can trust</a>
            <a href="#families">For families</a>
            <a href="#research">Research</a>
          </nav>
          <div className="site-cta">
            <Link className="btn quiet sm" to="/login">Sign in</Link>
            <Link className="btn accent sm" to="/login?mode=register">Get started</Link>
          </div>
        </div>
      </header>

      <section className="hero">
        <div className="wrap in hero-grid">
          <h1 className="hero-title">Small moments, saved. Given back when they matter.</h1>
          <div className="hero-auth"><AuthCard /></div>
          <div className="hero-text">
            <p className="lead">Save a photo, a voice note or a few words. The app adds the time and place. When you are back at that place, or when you ask, the memory is there, in your own words.</p>
            <div className="trust-chips">
              <span><ShieldCheck size={18} aria-hidden="true" />Answers only from your memories</span>
              <span><Users size={18} aria-hidden="true" />Family sees only what you allow</span>
              <span><Volume2 size={18} aria-hidden="true" />Reminders read aloud</span>
              <span><Lock size={18} aria-hidden="true" />Names hidden from the AI</span>
            </div>
            <p className="fine">Works on a phone or a computer, straight from the browser. No app store needed.</p>
            {err && <div style={{ marginTop: 14 }}><Notice kind="err" onClose={() => setErr(null)}>{err}</Notice></div>}
          </div>
        </div>
      </section>

      <section className="section alt" id="how">
        <div className="wrap">
          <h2>How it works</h2>
          <p className="intro">Three steps, and the app does the organising in between.</p>
          <div className="how-grid">
            <div className="steps steps-col">
            <div className="step"><div className="n">1</div><h3>Save a moment</h3><p>Tap Save, then take a photo, record a voice note or write a line. The time and place are added for you. Add who was there, if you like.</p></div>
            <div className="step"><div className="n">2</div><h3>It sorts itself</h3><p>Memories are grouped by place, by the people in them and by day, so nothing needs filing and nothing gets lost.</p></div>
            <div className="step"><div className="n">3</div><h3>Get it back</h3><p>Return to a place and the app shows what happened there last time. Or ask a question, out loud or typed, and get an answer built only from your memories.</p></div>
          </div>
            <div className="how-phone"><PhoneMockup /></div>
          </div>
        </div>
      </section>

      <section className="section">
        <div className="wrap">
          <h2>Made for memory loss, not adapted to it</h2>
          <p className="intro">Every screen follows a few rules that make the app calm to use, on a good day or a hard one.</p>
          <div className="feature-grid">
            <div className="feature"><ALargeSmall size={28} aria-hidden="true" /><h3>Big, clear text</h3><p>Large type, strong contrast and one readable font throughout. A larger-text setting makes everything bigger, not just some things.</p></div>
            <div className="feature"><Hand size={28} aria-hidden="true" /><h3>Nothing disappears</h3><p>No pop-ups that vanish, no timers, no surprise moves. Messages stay until you close them, and buttons stay where they were.</p></div>
            <div className="feature"><Eye size={28} aria-hidden="true" /><h3>One thing per screen</h3><p>Each screen does one job and says what happens next. Icons always have words beside them.</p></div>
            <div className="feature"><Ear size={28} aria-hidden="true" /><h3>Say it or type it</h3><p>Ask questions by speaking. Answers can be read aloud. Voice notes are saved as they are.</p></div>
          </div>
        </div>
      </section>

      <section className="section dark" id="trust">
        <div className="wrap">
          <h2>Answers you can trust</h2>
          <p className="intro">Someone with memory loss cannot check an answer against their own memory, so a made-up "memory" might simply be believed. That is why this app is built the way it is.</p>
          <div className="trust">
            <ul>
              <li><Check size={22} aria-hidden="true" /><span>Answers use only what you saved. Nothing is added from the internet or invented.</span></li>
              <li><Check size={22} aria-hidden="true" /><span>Every sentence carries a number that points to the memory it came from.</span></li>
              <li><Check size={22} aria-hidden="true" /><span>If nothing matches, it says so, instead of guessing.</span></li>
              <li><Check size={22} aria-hidden="true" /><span>It never gives medicine or dose advice. Those questions go to your doctor.</span></li>
              <li><Check size={22} aria-hidden="true" /><span>Memories you mark private stay out of answers and out of your family's view.</span></li>
            </ul>
            <div className="stack">
              <p className="small muted">Where did I keep my reading glasses?</p>
              <div className="answer">
                <p className="text">On Wednesday 23 September at Home, you saved: “Kept my reading glasses in the drawer of the TV table.”<span className="cite" aria-hidden="true">1</span></p>
              </div>
              <div className="source">
                <span className="num">1</span>
                <div className="memory" style={{ padding: 0, borderTop: 0 }}>
                  <div className="glyph" aria-hidden="true"><PenLine size={22} /></div>
                  <div><p>Kept my reading glasses in the drawer of the TV table.</p><div className="meta"><span>Wednesday, 11:00 AM</span><span>Home</span></div></div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="section" id="families">
        <div className="wrap">
          <h2>For the people who care</h2>
          <p className="intro">Family members get their own view, and the person using the app decides who gets it.</p>
          <div className="feature-grid">
            <div className="feature"><Users size={28} aria-hidden="true" /><h3>See their day</h3><p>Memories saved today, reminders done or missed, and a week at a glance. Never their private memories, never their questions.</p></div>
            <div className="feature"><Siren size={28} aria-hidden="true" /><h3>Help button</h3><p>One press sends an alert with their location and offers a call to the family. It shows on the family's screen within seconds.</p></div>
            <div className="feature"><Bell size={28} aria-hidden="true" /><h3>Messages and reminders</h3><p>Leave a note that appears on their Home. Add a reminder for a visit or a tablet. Marking it done saves a record they can ask about later.</p></div>
            <div className="feature"><ShieldCheck size={28} aria-hidden="true" /><h3>Access they control</h3><p>Family joins with a one-time code. The person can remove anyone at any time, and a "Who saw my data" screen lists every visit.</p></div>
          </div>
        </div>
      </section>

      <section className="section alt" id="research">
        <div className="wrap">
          <h2>Built as research, tested against numbers</h2>
          <p className="intro">A fixed set of questions runs against a made-up person's memories, and the app counts how often answers stay true to what was saved. You can run it yourself from the demo, on the Grounding test page.</p>
          <table className="targets">
            <thead><tr><th>Requirement</th><th>What is measured</th><th>Target</th></tr></thead>
            <tbody>{TARGETS.map(([id, what, t]) => <tr key={id}><td><b>{id}</b></td><td>{what}</td><td>{t}</td></tr>)}</tbody>
          </table>
          <p className="small muted" style={{ marginTop: 14 }}>No real patient data is used at any stage. The evaluation persona and every memory in it are fictional.</p>
        </div>
      </section>

      <section className="section">
        <div className="wrap">
          <h2>Questions people ask</h2>
          <div className="faq">
            <details><summary>Does it need the internet?</summary><p>Answers and the family view need a connection. If you save a memory while offline on your phone, it is kept on the phone and uploaded when you are back online.</p></details>
            <details><summary>Is it a medical device or a treatment?</summary><p>No. It is a memory aid for everyday moments. It does not diagnose anything and never gives advice about medicines or doses.</p></details>
            <details><summary>Where is my data stored?</summary><p>On the server the family or organisation runs. The demo uses a fictional person. Photos and voice notes are only reachable through links that expire after an hour.</p></details>
            <details><summary>Does it work on an iPhone and on Android?</summary><p>Yes. Open the web address in the phone's browser and choose "Add to Home Screen". It then opens like an app, with the camera, microphone and location.</p></details>
            <details><summary>Who made it?</summary><p>Group A4, Department of Computer Engineering, Terna Engineering College, Nerul, as a final-year project (A.Y. 2026–27) under Dr. R. V. Shahabade.</p></details>
          </div>
        </div>
      </section>

      <footer className="site-footer">
        <div className="wrap in">
          <p><b>Alzheimer Care Companion</b>. A BE project by Purva Dalvi, Aadesh Rathod, Siddhi Deshmukh and Shriya Mishra, Terna Engineering College, Nerul. Guide: Dr. R. V. Shahabade.</p>
          <p>Demo accounts and memories are fictional. Not a medical device.</p>
          <p><Link to="/login">Sign in</Link></p>
        </div>
      </footer>
    </div>
  );
}

function PhoneMockup() {
  return (
    <div className="device" aria-hidden="true">
      <div className="notch" />
      <section className="here">
        <p className="where">You are at</p>
        <p className="place">Upvan Lake</p>
        <div className="count"><b>4</b><span>memories saved here</span></div>
        <div className="last"><p className="small"><b>Last time here: Wednesday, 7:30 AM</b></p><p>Morning walk around Upvan Lake with Ramesh. We fed the fish near the boating point.</p></div>
      </section>
      <div className="panel">
        <div className="spread" style={{ marginBottom: 8 }}><b>Reminders</b></div>
        <div className="list">
          <div className="list-item" style={{ minHeight: 48, padding: "8px 0" }}><span className="grow">Morning tablet</span><span className="badge done"><Check size={14} aria-hidden="true" />Done</span></div>
          <div className="list-item" style={{ minHeight: 48, padding: "8px 0" }}><span className="grow">Drink a glass of water</span><span className="badge later">12:00</span></div>
        </div>
      </div>
      <div className="row" style={{ marginTop: 12, gap: 8 }}>
        <span className="chip" style={{ minHeight: 36 }}><Camera size={16} aria-hidden="true" />Photo</span>
        <span className="chip" style={{ minHeight: 36 }}><Mic size={16} aria-hidden="true" />Voice</span>
        <span className="chip" style={{ minHeight: 36 }}><MessageCircleQuestion size={16} aria-hidden="true" />Ask</span>
        <span className="chip" style={{ minHeight: 36 }}><MapPin size={16} aria-hidden="true" />Places</span>
        <span className="chip" style={{ minHeight: 36 }}><Volume2 size={16} aria-hidden="true" />Read aloud</span>
        <span className="chip" style={{ minHeight: 36 }}><Lock size={16} aria-hidden="true" />Private</span>
      </div>
      <p className="small muted" style={{ marginTop: 10 }}><FlaskConical size={14} aria-hidden="true" style={{ verticalAlign: -2 }} /> Grounding test included</p>
    </div>
  );
}
