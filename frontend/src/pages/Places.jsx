import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { MapPin, Pencil, Navigation, Merge } from "lucide-react";
import { api } from "../api";
import { Dialog, Empty, MemoryItem, Notice, PageHead, PlacesMap } from "../components";
import { fmtDayInline, useApi, useLocation, setDemoLocation } from "../hooks";
import { groupByDay } from "./Memories";

export function Places() {
  const { data, loading, error } = useApi("/api/places");
  const loc = useLocation();
  const nav = useNavigate();
  const places = data || [];
  return (
    <div className="stack-lg">
      <PageHead title="Places" sub="Memories are grouped by where you saved them." />
      {error && <Notice kind="err">{error}</Notice>}
      {loading && <p className="muted">Loading…</p>}
      {!loading && places.length === 0 && <Empty title="No places yet">Save a memory with location turned on and its place appears here.</Empty>}
      {places.length > 0 && (
        <div className="grid-2">
          <PlacesMap places={places} here={loc.coords} onPick={(p) => nav(`/places/${p.id}`)} sticky />
          <section className="panel">
            <div className="list">
              {places.map((p) => (
                <Link key={p.id} to={`/places/${p.id}`} className="list-item" style={{ textDecoration: "none", color: "inherit" }}>
                  <div className="memory" style={{ padding: 0, border: 0, gridTemplateColumns: "auto 1fr", width: "100%" }}>
                    <div className="glyph" aria-hidden="true"><MapPin size={22} /></div>
                    <div>
                      <p><b>{p.name}</b></p>
                      <p className="small muted">{p.memory_count} {p.memory_count === 1 ? "memory" : "memories"}. Last visit {fmtDayInline(p.last_visit_at)}</p>
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          </section>
        </div>
      )}
    </div>
  );
}

export function PlaceDetail() {
  const { id } = useParams();
  const nav = useNavigate();
  const places = useApi("/api/places");
  const mems = useApi(`/api/records?place_id=${id}&limit=200`);
  const place = (places.data || []).find((p) => String(p.id) === id);
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState("");
  const [merging, setMerging] = useState(false);
  const [into, setInto] = useState("");
  const [msg, setMsg] = useState(null);

  if (places.loading) return <p className="muted">Loading…</p>;
  if (!place) return <Empty title="Place not found" action={<Link className="btn quiet" to="/places">Back to places</Link>} />;

  const rename = async () => {
    try { await api(`/api/places/${id}`, { method: "PATCH", body: { name } }); setEditing(false); places.reload(); }
    catch (e) { setMsg(e.message); }
  };
  const merge = async () => {
    try { await api(`/api/places/${id}/merge`, { method: "POST", body: { into_id: Number(into) } }); nav(`/places/${into}`); }
    catch (e) { setMsg(e.message); }
  };
  const pretend = () => { setDemoLocation({ lat: place.lat, lng: place.lng }); nav("/"); };

  return (
    <div className="stack-lg">
      <div className="stack" style={{ gap: 8 }}>
        <Link to="/places">All places</Link>
        {editing ? (
          <div className="row" style={{ flexWrap: "nowrap" }}>
            <input className="input" aria-label="Place name" value={name} onChange={(e) => setName(e.target.value)} autoFocus />
            <button className="btn" onClick={rename}>Save name</button>
            <button className="btn quiet" onClick={() => setEditing(false)}>Cancel</button>
          </div>
        ) : <h1>{place.name}</h1>}
        <p className="muted">{place.memory_count} {place.memory_count === 1 ? "memory" : "memories"} saved here</p>
      </div>
      {msg && <Notice kind="err" onClose={() => setMsg(null)}>{msg}</Notice>}
      <div className="row">
        {!editing && <button className="btn quiet" onClick={() => { setName(place.name); setEditing(true); }}><Pencil size={18} aria-hidden="true" />Rename</button>}
        <button className="btn quiet" onClick={() => setMerging(true)}><Merge size={18} aria-hidden="true" />Same as another place</button>
        <button className="btn quiet" onClick={pretend}><Navigation size={18} aria-hidden="true" />Demo: pretend I'm here</button>
      </div>
      <div className="grid-2">
        <div className="stack">
          {groupByDay(mems.data || []).map((g) => (
            <section key={g.day} className="panel">
              <h2 className="day-head" style={{ marginTop: 0 }}>{g.day}</h2>
              {g.items.map((m) => <MemoryItem key={m.id} m={m} showPlace={false} />)}
            </section>
          ))}
        </div>
        <PlacesMap places={[place]} />
      </div>
      {merging && (
        <Dialog title="Is this the same place as another one?" onClose={() => setMerging(false)}>
          <p>All memories from {place.name} will move to the place you choose.</p>
          <select className="select" value={into} onChange={(e) => setInto(e.target.value)} aria-label="Move memories to">
            <option value="">Choose a place</option>
            {(places.data || []).filter((p) => p.id !== place.id).map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
          <div className="actions">
            <button className="btn quiet" onClick={() => setMerging(false)}>Cancel</button>
            <button className="btn" disabled={!into} onClick={merge}>Move memories</button>
          </div>
        </Dialog>
      )}
    </div>
  );
}
