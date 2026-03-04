import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react';
import { login as authLogin, logout as authLogout, isAuthenticated, refreshSession, type AuthTokens } from '../services/auth';

interface AuthContextType {
  authenticated: boolean;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [authenticated, setAuthenticated] = useState(false);
  const [loading, setLoading] = useState(true);

  // 初始化时检查认证状态
  useEffect(() => {
    const init = async () => {
      try {
        if (isAuthenticated()) {
          setAuthenticated(true);
        } else {
          // 尝试刷新 token
          const tokens = await refreshSession();
          setAuthenticated(!!tokens);
        }
      } catch {
        // Cognito 配置无效或网络错误，视为未认证
        setAuthenticated(false);
      }
      setLoading(false);
    };
    init();
  }, []);

  // 自动刷新 token（每 10 分钟检查一次）
  useEffect(() => {
    if (!authenticated) return;
    const interval = setInterval(async () => {
      const tokens = await refreshSession();
      if (!tokens) {
        setAuthenticated(false);
      }
    }, 10 * 60 * 1000);
    return () => clearInterval(interval);
  }, [authenticated]);

  const login = useCallback(async (username: string, password: string) => {
    await authLogin(username, password);
    setAuthenticated(true);
  }, []);

  const logout = useCallback(() => {
    authLogout();
    setAuthenticated(false);
  }, []);

  return (
    <AuthContext.Provider value={{ authenticated, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth 必须在 AuthProvider 内使用');
  return ctx;
}
