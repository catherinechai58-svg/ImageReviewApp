import { useState, useEffect, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

export default function LoginPage() {
  const { login, forceChangePassword, authenticated } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  // 强制修改密码状态
  const [challenge, setChallenge] = useState<{ session: string; username: string } | null>(null);
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');

  useEffect(() => {
    if (authenticated) navigate('/', { replace: true });
  }, [authenticated, navigate]);

  const handleLogin = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    if (!username.trim() || !password) {
      setError('请输入用户名和密码');
      return;
    }
    setSubmitting(true);
    try {
      const result = await login(username.trim(), password);
      if ('challenge' in result && result.challenge === 'NEW_PASSWORD_REQUIRED') {
        setChallenge({ session: result.session, username: result.username });
      } else {
        navigate('/', { replace: true });
      }
    } catch (err: any) {
      const msg = err.response?.data?.error?.message || err.message || '登录失败';
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  const handleForceChange = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    if (!newPassword || !confirmPassword) {
      setError('请输入新密码');
      return;
    }
    if (newPassword !== confirmPassword) {
      setError('两次输入的密码不一致');
      return;
    }
    if (newPassword.length < 8) {
      setError('密码至少8位');
      return;
    }
    setSubmitting(true);
    try {
      await forceChangePassword(challenge!.username, newPassword, challenge!.session);
      navigate('/', { replace: true });
    } catch (err: any) {
      const msg = err.response?.data?.error?.message || err.message || '密码修改失败';
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  // 强制修改密码界面
  if (challenge) {
    return (
      <div style={styles.container}>
        <form onSubmit={handleForceChange} style={styles.form}>
          <h2 style={styles.title}>首次登录 — 修改密码</h2>
          <p style={{ fontSize: '14px', color: '#666', marginBottom: '16px' }}>
            您使用的是临时密码，请设置新密码后继续使用。
          </p>
          {error && <div style={styles.error}>{error}</div>}
          <div style={styles.field}>
            <label htmlFor="newPassword">新密码</label>
            <input
              id="newPassword" type="password" value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              style={styles.input} autoComplete="new-password" disabled={submitting}
              placeholder="至少8位，包含大小写字母和数字"
            />
          </div>
          <div style={styles.field}>
            <label htmlFor="confirmPassword">确认密码</label>
            <input
              id="confirmPassword" type="password" value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              style={styles.input} autoComplete="new-password" disabled={submitting}
            />
          </div>
          <button type="submit" style={styles.button} disabled={submitting}>
            {submitting ? '提交中...' : '确认修改'}
          </button>
        </form>
      </div>
    );
  }

  // 正常登录界面
  return (
    <div style={styles.container}>
      <form onSubmit={handleLogin} style={styles.form}>
        <h2 style={styles.title}>图片审核平台</h2>
        {error && <div style={styles.error}>{error}</div>}
        <div style={styles.field}>
          <label htmlFor="username">用户名</label>
          <input
            id="username" type="text" value={username}
            onChange={(e) => setUsername(e.target.value)}
            style={styles.input} autoComplete="username" disabled={submitting}
          />
        </div>
        <div style={styles.field}>
          <label htmlFor="password">密码</label>
          <input
            id="password" type="password" value={password}
            onChange={(e) => setPassword(e.target.value)}
            style={styles.input} autoComplete="current-password" disabled={submitting}
          />
        </div>
        <button type="submit" style={styles.button} disabled={submitting}>
          {submitting ? '登录中...' : '登录'}
        </button>
      </form>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    display: 'flex', justifyContent: 'center', alignItems: 'center',
    minHeight: '100vh', background: '#f5f5f5',
  },
  form: {
    background: '#fff', padding: '40px', borderRadius: '8px',
    boxShadow: '0 2px 8px rgba(0,0,0,0.1)', width: '360px',
  },
  title: { textAlign: 'center' as const, marginBottom: '24px', color: '#333' },
  error: {
    background: '#fff2f0', border: '1px solid #ffccc7', color: '#ff4d4f',
    padding: '8px 12px', borderRadius: '4px', marginBottom: '16px', fontSize: '14px',
  },
  field: { marginBottom: '16px', display: 'flex', flexDirection: 'column' as const, gap: '4px' },
  input: {
    padding: '8px 12px', border: '1px solid #d9d9d9', borderRadius: '4px',
    fontSize: '14px', outline: 'none',
  },
  button: {
    width: '100%', padding: '10px', background: '#1677ff', color: '#fff',
    border: 'none', borderRadius: '4px', fontSize: '16px', cursor: 'pointer', marginTop: '8px',
  },
};
