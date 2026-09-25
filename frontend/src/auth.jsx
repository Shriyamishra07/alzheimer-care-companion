import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, getToken, setToken } from "./api";

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!getToken()) { setReady(true); return; }
    api("/api/me").then(setUser).catch(() => setToken(null)).finally(() => setReady(true));
    const onLogout = () => setUser(null);
    window.addEventListener("cc:logout", onLogout);
    return () => window.removeEventListener("cc:logout", onLogout);
  }, []);

  const signIn = useCallback(async (email, password) => {
    const r = await api("/api/auth/login", { method: "POST", body: { email, password } });
    setToken(r.token); setUser(r.user); return r.user;
  }, []);
  const register = useCallback(async (payload) => {
    const r = await api("/api/auth/register", { method: "POST", body: payload });
    setToken(r.token); setUser(r.user); return r.user;
  }, []);
  const signOut = useCallback(() => { setToken(null); setUser(null); }, []);

  return <AuthCtx.Provider value={{ user, setUser, ready, signIn, register, signOut }}>{children}</AuthCtx.Provider>;
}

export const useAuth = () => useContext(AuthCtx);
