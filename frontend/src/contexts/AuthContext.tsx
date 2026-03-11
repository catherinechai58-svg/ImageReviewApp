import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react';
import {
  login as authLogin,
  forceChangePassword as authForceChange,
  logout as authLogout,
  isAuthenticated,
  refreshSession,
  type AuthTokens,
  type ChallengeResult,
} from '../services/auth';

interface AuthContextType {
  authenticated: boolean;
  loading: boolean;
  login: (username: string, password: string) => Promise<AuthTokens | ChallengeResult>;
  forceChangePassword: (username: string, newPassword: string, session: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [authenticated, setAuthenticated] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setAuthenticated(isAuthenticated());
    setLoading(false);
  }, []);

  useEffect(() => {
    if (!authenticated) return;
    const interval = setInterval(async () => {
      const tokens = await refreshSession();
      if (!tokens) setAuthenticated(false);
    }, 10 * 60 * 1000);
    return () => clearInterval(interval);
  }, [authenticated]);

  const login = useCallback(async (username: string, password: string) => {
    const result = await authLogin(username, password);
    if ('challenge' in result) return result;
    setAuthenticated(true);
    return result;
  }, []);

  const forceChangePassword = useCallback(async (username: string, newPassword: string, session: string) => {
    await authForceChange(username, newPassword, session);
    setAuthenticated(true);
  }, []);

  const logout = useCallback(() => {
    authLogout();
    setAuthenticated(false);
  }, []);

  return (
    <AuthContext.Provider value={{ authenticated, loading, login, forceChangePassword, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth 必须在 AuthProvider 内使用');
  return ctx;
}
