import { useEffect } from "react";
import { Navigate, Route, Routes, useLocation as useRoute } from "react-router-dom";
import { useAuth } from "./auth";
import { Shell } from "./components";
import Login from "./pages/Login";
import Landing from "./pages/Landing";
import Home from "./pages/Home";
import Capture from "./pages/Capture";
import Memories from "./pages/Memories";
import { Places, PlaceDetail } from "./pages/Places";
import Ask from "./pages/Ask";
import People from "./pages/People";
import Reminders from "./pages/Reminders";
import { Family, Privacy } from "./pages/Family";
import Research from "./pages/Research";
import { Settings, More } from "./pages/Settings";
import { CarerHome, LinkPerson } from "./pages/Caregiver";

// Every new screen starts at the top, like a new page on a website.
function ScrollToTop() {
  const { pathname } = useRoute();
  useEffect(() => { window.scrollTo(0, 0); }, [pathname]);
  return null;
}

export default function App() {
  return <><ScrollToTop /><Screens /></>;
}

function Screens() {
  const { user, ready } = useAuth();
  if (!ready) return <div className="login-wrap"><p className="muted">Opening…</p></div>;
  if (!user) {
    return (
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="*" element={<Landing />} />
      </Routes>
    );
  }
  if (user.role === "caregiver") {
    return (
      <Shell>
        <Routes>
          <Route path="/" element={<CarerHome />} />
          <Route path="/link" element={<LinkPerson />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Shell>
    );
  }
  return (
    <Shell>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/save" element={<Capture />} />
        <Route path="/memories" element={<Memories />} />
        <Route path="/places" element={<Places />} />
        <Route path="/places/:id" element={<PlaceDetail />} />
        <Route path="/ask" element={<Ask />} />
        <Route path="/people" element={<People />} />
        <Route path="/reminders" element={<Reminders />} />
        <Route path="/family" element={<Family />} />
        <Route path="/privacy" element={<Privacy />} />
        <Route path="/research" element={<Research />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="/more" element={<More />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Shell>
  );
}
