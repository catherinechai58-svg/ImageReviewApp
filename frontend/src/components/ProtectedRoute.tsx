import { Navigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

// 路由守卫 — 未登录重定向到登录页
export default function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { authenticated, loading } = useAuth();

  if (loading) {
    return <div style={{ padding: 40, textAlign: 'center' }}>加载中...</div>;
  }

  if (!authenticated) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}
