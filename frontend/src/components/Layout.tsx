import { Outlet, useNavigate, NavLink } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

// 主布局 — 顶部导航栏 + 内容区域
export default function Layout() {
  const { logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login', { replace: true });
  };

  return (
    <div style={{ minHeight: '100vh', background: '#f5f5f5' }}>
      <nav style={styles.nav}>
        <div style={styles.navLeft}>
          <span style={styles.logo}>图片审核平台</span>
          <NavLink to="/" style={({ isActive }) => ({ ...styles.link, ...(isActive ? styles.activeLink : {}) })}>
            首页
          </NavLink>
          <NavLink to="/prompts" style={({ isActive }) => ({ ...styles.link, ...(isActive ? styles.activeLink : {}) })}>
            提示词模板
          </NavLink>
          <NavLink to="/tasks" style={({ isActive }) => ({ ...styles.link, ...(isActive ? styles.activeLink : {}) })}>
            任务管理
          </NavLink>
        </div>
        <button onClick={handleLogout} style={styles.logoutBtn}>退出登录</button>
      </nav>
      <main style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto' }}>
        <Outlet />
      </main>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  nav: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '0 24px',
    height: '48px',
    background: '#fff',
    borderBottom: '1px solid #e8e8e8',
  },
  navLeft: {
    display: 'flex',
    alignItems: 'center',
    gap: '24px',
  },
  logo: {
    fontWeight: 'bold',
    fontSize: '16px',
    color: '#1677ff',
    marginRight: '8px',
  },
  link: {
    textDecoration: 'none',
    color: '#666',
    fontSize: '14px',
    padding: '4px 0',
  },
  activeLink: {
    color: '#1677ff',
    fontWeight: 500,
  },
  logoutBtn: {
    background: 'none',
    border: '1px solid #d9d9d9',
    borderRadius: '4px',
    padding: '4px 12px',
    cursor: 'pointer',
    fontSize: '13px',
    color: '#666',
  },
};
