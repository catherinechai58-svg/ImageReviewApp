import { useEffect, useState } from 'react';
import api from '../services/api';

interface User {
  username: string;
  status: string;
  role: string;
  created_at: string;
}

const statusLabels: Record<string, string> = {
  CONFIRMED: '正常',
  FORCE_CHANGE_PASSWORD: '待修改密码',
  DISABLED: '已禁用',
};

export default function UsersPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // 创建用户
  const [showCreate, setShowCreate] = useState(false);
  const [newUsername, setNewUsername] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [newRole, setNewRole] = useState('user');
  const [creating, setCreating] = useState(false);

  // 重置密码
  const [resetTarget, setResetTarget] = useState<string | null>(null);
  const [resetPassword, setResetPassword] = useState('');
  const [resetting, setResetting] = useState(false);

  // 删除确认
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  const fetchUsers = async () => {
    try {
      setLoading(true);
      const res = await api.get('/users');
      setUsers(res.data.data || []);
      setError('');
    } catch (err: any) {
      setError(err.response?.data?.error?.message || '获取用户列表失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchUsers(); }, []);

  const handleCreate = async () => {
    setError('');
    if (!newUsername.trim()) { setError('用户名不能为空'); return; }
    if (!newPassword) { setError('临时密码不能为空'); return; }
    setCreating(true);
    try {
      await api.post('/users', { username: newUsername.trim(), temporary_password: newPassword, role: newRole });
      setShowCreate(false);
      setNewUsername(''); setNewPassword(''); setNewRole('user');
      fetchUsers();
    } catch (err: any) {
      setError(err.response?.data?.error?.message || '创建用户失败');
    } finally {
      setCreating(false);
    }
  };

  const handleReset = async () => {
    if (!resetTarget || !resetPassword) { setError('临时密码不能为空'); return; }
    setResetting(true);
    setError('');
    try {
      await api.put(`/users/${resetTarget}/reset-password`, { temporary_password: resetPassword });
      setResetTarget(null); setResetPassword('');
      fetchUsers();
    } catch (err: any) {
      setError(err.response?.data?.error?.message || '重置密码失败');
    } finally {
      setResetting(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    setError('');
    try {
      await api.delete(`/users/${deleteTarget}`);
      setDeleteTarget(null);
      fetchUsers();
    } catch (err: any) {
      setError(err.response?.data?.error?.message || '删除用户失败');
    } finally {
      setDeleting(false);
    }
  };

  if (loading) return <div style={{ padding: '20px', color: '#999' }}>加载中...</div>;

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
        <h2 style={{ margin: 0, fontSize: '18px' }}>用户管理</h2>
        <button onClick={() => setShowCreate(true)} style={styles.primaryBtn}>创建用户</button>
      </div>

      {error && <div style={styles.errorMsg}>{error}</div>}

      <table style={styles.table}>
        <thead>
          <tr>
            <th style={styles.th}>用户名</th>
            <th style={styles.th}>角色</th>
            <th style={styles.th}>状态</th>
            <th style={styles.th}>创建时间</th>
            <th style={{ ...styles.th, width: '180px' }}>操作</th>
          </tr>
        </thead>
        <tbody>
          {users.map((u) => (
            <tr key={u.username}>
              <td style={styles.td}>{u.username}</td>
              <td style={styles.td}>
                <span style={{
                  display: 'inline-block', padding: '2px 8px', borderRadius: '4px', fontSize: '12px',
                  background: u.role === 'admin' ? '#fff7e6' : '#f5f5f5',
                  color: u.role === 'admin' ? '#fa8c16' : '#666',
                }}>
                  {u.role === 'admin' ? '管理员' : '普通用户'}
                </span>
              </td>
              <td style={styles.td}>
                <span style={{
                  color: u.status === 'CONFIRMED' ? '#52c41a' : '#fa8c16',
                  fontSize: '13px',
                }}>
                  {statusLabels[u.status] || u.status}
                </span>
              </td>
              <td style={styles.td}>{u.created_at ? new Date(u.created_at).toLocaleString() : '-'}</td>
              <td style={styles.td}>
                <button onClick={() => { setResetTarget(u.username); setResetPassword(''); }} style={styles.linkBtn}>重置密码</button>
                <button onClick={() => setDeleteTarget(u.username)} style={{ ...styles.linkBtn, color: '#ff4d4f' }}>删除</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* 创建用户弹窗 */}
      {showCreate && (
        <div style={styles.overlay}>
          <div style={styles.dialog}>
            <h3 style={{ margin: '0 0 16px' }}>创建用户</h3>
            <div style={styles.field}>
              <label style={styles.label}>用户名</label>
              <input style={styles.input} value={newUsername} onChange={(e) => setNewUsername(e.target.value)} placeholder="输入用户名" />
            </div>
            <div style={styles.field}>
              <label style={styles.label}>临时密码</label>
              <input style={styles.input} type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} placeholder="用户首次登录后需修改" />
            </div>
            <div style={styles.field}>
              <label style={styles.label}>角色</label>
              <select style={styles.input} value={newRole} onChange={(e) => setNewRole(e.target.value)}>
                <option value="user">普通用户</option>
                <option value="admin">管理员</option>
              </select>
            </div>
            <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
              <button onClick={() => setShowCreate(false)} style={styles.defaultBtn}>取消</button>
              <button onClick={handleCreate} disabled={creating} style={styles.primaryBtn}>
                {creating ? '创建中...' : '创建'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 重置密码弹窗 */}
      {resetTarget && (
        <div style={styles.overlay}>
          <div style={styles.dialog}>
            <h3 style={{ margin: '0 0 16px' }}>重置密码 — {resetTarget}</h3>
            <div style={styles.field}>
              <label style={styles.label}>新临时密码</label>
              <input style={styles.input} type="password" value={resetPassword} onChange={(e) => setResetPassword(e.target.value)} placeholder="用户下次登录需修改" />
            </div>
            <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
              <button onClick={() => setResetTarget(null)} style={styles.defaultBtn}>取消</button>
              <button onClick={handleReset} disabled={resetting} style={styles.primaryBtn}>
                {resetting ? '重置中...' : '确认重置'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 删除确认弹窗 */}
      {deleteTarget && (
        <div style={styles.overlay}>
          <div style={styles.dialog}>
            <h3 style={{ margin: '0 0 12px' }}>确认删除</h3>
            <p>确定要删除用户「{deleteTarget}」吗？此操作不可恢复。</p>
            <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
              <button onClick={() => setDeleteTarget(null)} style={styles.defaultBtn}>取消</button>
              <button onClick={handleDelete} disabled={deleting} style={styles.dangerBtn}>
                {deleting ? '删除中...' : '确认删除'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  primaryBtn: {
    background: '#1677ff', color: '#fff', border: 'none', borderRadius: '4px',
    padding: '6px 16px', cursor: 'pointer', fontSize: '14px',
  },
  errorMsg: {
    background: '#fff2f0', border: '1px solid #ffccc7', borderRadius: '4px',
    padding: '8px 12px', color: '#ff4d4f', marginBottom: '12px', fontSize: '13px',
  },
  table: { width: '100%', borderCollapse: 'collapse', background: '#fff', borderRadius: '4px' },
  th: {
    textAlign: 'left', padding: '10px 12px', borderBottom: '2px solid #f0f0f0',
    fontSize: '13px', color: '#666', fontWeight: 500,
  },
  td: { padding: '10px 12px', borderBottom: '1px solid #f0f0f0', fontSize: '14px' },
  linkBtn: {
    background: 'none', border: 'none', color: '#1677ff', cursor: 'pointer',
    fontSize: '13px', padding: '2px 6px',
  },
  overlay: {
    position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
    background: 'rgba(0,0,0,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center',
    zIndex: 1000,
  },
  dialog: {
    background: '#fff', borderRadius: '8px', padding: '24px', minWidth: '360px', maxWidth: '480px',
  },
  field: { marginBottom: '12px' },
  label: { display: 'block', marginBottom: '4px', fontSize: '14px', color: '#333' },
  input: {
    width: '100%', padding: '6px 10px', border: '1px solid #d9d9d9', borderRadius: '4px',
    fontSize: '14px', boxSizing: 'border-box',
  },
  defaultBtn: {
    background: '#fff', border: '1px solid #d9d9d9', borderRadius: '4px',
    padding: '6px 16px', cursor: 'pointer', fontSize: '14px',
  },
  dangerBtn: {
    background: '#ff4d4f', color: '#fff', border: 'none', borderRadius: '4px',
    padding: '6px 16px', cursor: 'pointer', fontSize: '14px',
  },
};
