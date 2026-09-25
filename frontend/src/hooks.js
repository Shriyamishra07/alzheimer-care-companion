import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";

// Load data from the API with loading/error state and a reload() function.
export function useApi(path, deps = []) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(!!path);
  const alive = useRef(true);
  const load = useCallback(async () => {
    if (!path) return;
    setLoading(true); setError(null);
    try { const d = await api(path); if (alive.current) setData(d); }
    catch (e) { if (alive.current) setError(e.message); }
    finally { if (alive.current) setLoading(false); }
  }, [path]);
  useEffect(() => { alive.current = true; load(); return () => { alive.current = false; }; }, [load, ...deps]);
  return { data, setData, error, loading, reload: load };
}

// "Pretend I'm here" lets the review panel see place-triggered recall on a laptop.
export function getDemoLocation() {
  try { return JSON.parse(localStorage.getItem("cc_demo_loc") || "null"); } catch { return null; }
}
export function setDemoLocation(loc) {
  try { loc ? localStorage.setItem("cc_demo_loc", JSON.stringify(loc)) : localStorage.removeItem("cc_demo_loc"); } catch { /* ignore */ }
  window.dispatchEvent(new Event("cc:demo-location"));
}

// Current position while the app is open (browsers do not allow background location).
// Flow: we never trigger the browser's permission pop-up by surprise. If permission
// hasn't been given yet, status is "prompt" and the screen explains why before the
// person taps "Turn on location", which calls request().
// status: checking | prompt | looking | live | demo | denied | unavailable | unsupported
export function useLocation() {
  const [state, setState] = useState(() => {
    const d = getDemoLocation();
    return { coords: d, status: d ? "demo" : "checking" };
  });
  const watch = useRef(null);

  const stop = useCallback(() => {
    if (watch.current != null) navigator.geolocation.clearWatch(watch.current);
    watch.current = null;
  }, []);

  const request = useCallback(() => {
    if (!("geolocation" in navigator)) { setState({ coords: null, status: "unsupported" }); return; }
    if (watch.current != null) return;
    setState((s) => (s.coords ? s : { coords: null, status: "looking" }));
    watch.current = navigator.geolocation.watchPosition(
      (p) => {
        try { localStorage.setItem("cc_loc_ok", "1"); } catch { /* ignore */ }
        setState({ coords: { lat: p.coords.latitude, lng: p.coords.longitude, accuracy: p.coords.accuracy }, status: "live" });
      },
      (err) => { stop(); setState({ coords: null, status: err.code === 1 ? "denied" : "unavailable" }); },
      { enableHighAccuracy: true, maximumAge: 30000, timeout: 20000 }
    );
  }, [stop]);

  useEffect(() => {
    let cancelled = false;
    const init = async () => {
      stop();
      const demo = getDemoLocation();
      if (demo) { setState({ coords: demo, status: "demo" }); return; }
      if (!("geolocation" in navigator)) { setState({ coords: null, status: "unsupported" }); return; }
      let perm = "prompt";
      try { perm = (await navigator.permissions.query({ name: "geolocation" })).state; }
      catch { try { perm = localStorage.getItem("cc_loc_ok") === "1" ? "granted" : "prompt"; } catch { /* ignore */ } }
      if (cancelled) return;
      if (perm === "granted") request();
      else setState({ coords: null, status: perm === "denied" ? "denied" : "prompt" });
    };
    init();
    window.addEventListener("cc:demo-location", init);
    return () => { cancelled = true; window.removeEventListener("cc:demo-location", init); stop(); };
  }, [request, stop]);

  return { ...state, request };
}

export function greeting() {
  const h = new Date().getHours();
  return h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening";
}

export function fmtDay(iso) {
  const d = new Date(iso);
  const today = new Date(); const y = new Date(); y.setDate(today.getDate() - 1);
  if (d.toDateString() === today.toDateString()) return "Today";
  if (d.toDateString() === y.toDateString()) return "Yesterday";
  return d.toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long" });
}
// "3:07 PM" everywhere, matching the times the server writes into answers.
export function fmtTime(iso) {
  return new Date(iso).toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit" }).replace(/\b(am|pm)\b/i, (m) => m.toUpperCase());
}
export function fmtWhen(iso) { return `${fmtDay(iso)}, ${fmtTime(iso)}`; }
// For use inside a sentence: "last visit today", "ran yesterday, 4:10 pm"
export function fmtDayInline(iso) { const d = fmtDay(iso); return d === "Today" || d === "Yesterday" ? d.toLowerCase() : `on ${d}`; }
export function fmtWhenInline(iso) { return `${fmtDayInline(iso)}, ${fmtTime(iso)}`; }

// Orientation cue: the time of day, updated every half minute.
export function useClock() {
  const [now, setNow] = useState(new Date());
  useEffect(() => { const t = setInterval(() => setNow(new Date()), 30000); return () => clearInterval(t); }, []);
  return now;
}
export function partOfDay(d = new Date()) {
  const h = d.getHours();
  return h < 5 ? "night" : h < 12 ? "morning" : h < 17 ? "afternoon" : h < 21 ? "evening" : "night";
}

export function getTheme() { try { return localStorage.getItem("cc_theme") || "system"; } catch { return "system"; } }
export function applyTheme(t) {
  if (t === "system") document.documentElement.removeAttribute("data-theme");
  else document.documentElement.setAttribute("data-theme", t);
  try { localStorage.setItem("cc_theme", t); } catch { /* ignore */ }
}
