import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import api from '../services/api';
import { getCurrentUsername } from '../services/auth';

interface PromptTemplate {
  template_id: string;
  name: string;
  description: string;
  visibility: string;
  created_by: string;
  created_at: string;
}

interface TaskRef {
  task_id: string;
  name: string;
}

export default function PromptsPage() {
  const navigate = useNavigate();
  const { loading: authLoading } = useAuth();
  const [templates, setTemplates] = useState<PromptTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [deleteTarget, setDeleteTarget] = useState<PromptTemplate | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [conflictTasks, setConflictTasks] = useState<TaskRef[]>([]);

  const currentUser = getCurrentUsername();

  const fetchTemplates = async () => {
    try {
      setLoading(true);
      const res = await api.get('/prompts');
      setTemplates(res.data.data || []);
      setError('');
    } catch {
      setError('获取模板列表失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!authLoading) fetchTemplates();
  }, [authLoading]);

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    setConflictTasks([]);
    try {
      await api.delete(`/prompts/${deleteTarget.template_id}`);
      setDeleteTarget(null);
      fetchTemplates();
    } catch (err: any) {
      if (err.response?.status === 409) {
        setConflictTasks(err.response.data?.error?.details || []);
      } else {
        setError(err.response?.data?.error?.message || '删除失败');
        setDeleteTarget(null);
      }
    } finally {
      setDeleting(false);
    }
  };

  const closeDialog = () => { setDeleteTarget(null); setConflictTasks([]); };

  if (loading) return <div style={{ padding: '20px', color: '#999' }}>加载中...</div>;

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
        <h2 style={{ margin: 0, fontSize: '18px' }}>提示词模板</h2>
        <button onClick={() => navigate('/prompts/new')} style={styles.primaryBtn}>创建模板</button>
      </div>

      {error && <div style={styles.errorMsg}>{error}</div>}

      {templates.length === 0 ? (
        <div style={{ color: '#999', textAlign: 'center', padding: '40px' }}>暂无模板，点击"创建模板"开始</div>
      ) : (
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.th}>名称</th>
              <th style={styles.th}>描述</th>
              <th style={styles.th}>可见性</th>
              <th style={styles.th}>创建者</th>
              <th style={styles.th}>创建时间</th>
              <th style={{ ...styles.th, width: '180px' }}>操作</th>
            </tr>
          </thead>
          <tbody>
            {templates.map((t) => {
              const isOwner = t.created_by === currentUser;
              return (
                <tr key={t.template_id}>
                  <td style={styles.td}>{t.name}</td>
                  <td style={styles.td}>{t.description || '-'}</td>
                  <td style={styles.td}>
                    <span style={{
                      display: 'inline-block', padding: '2px 8px', borderRadius: '4px', fontSize: '12px',
                      background: t.visibility === 'public' ? '#e6f4ff' : '#f5f5f5',
                      color: t.visibility === 'public' ? '#1677ff' : '#666',
                    }}>
                      {t.visibility === 'public' ? '公开' : '个人'}
                    </span>
                  </td>
                  <td style={styles.td}>{t.created_by || '-'}</td>
                  <td style={styles.td}>{t.created_at ? new Date(t.created_at).toLocaleString() : '-'}</td>
                  <td style={styles.td}>
                    <button onClick={() => navigate(`/prompts/${t.template_id}/view`)} style={styles.linkBtn}>查看</button>
                    {isOwner && (
                      <>
                        <button onClick={() => navigate(`/prompts/${t.template_id}/edit`)} style={styles.linkBtn}>编辑</button>
                        <button onClick={() => setDeleteTarget(t)} style={{ ...styles.linkBtn, color: '#ff4d4f' }}>删除</button>
                      </>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}

      {deleteTarget && (
        <div style={styles.overlay}>
          <div style={styles.dialog}>
            {conflictTasks.length > 0 ? (
              <>
                <h3 style={{ margin: '0 0 12px' }}>无法删除</h3>
                <p>模板「{deleteTarget.name}」正在被以下任务引用：</p>
                <ul style={{ margin: '8px 0', paddingLeft: '20px' }}>
                  {conflictTasks.map((t) => <li key={t.task_id}>{t.name || t.task_id}</li>)}
                </ul>
                <div style={{ textAlign: 'right' }}>
                  <button onClick={closeDialog} style={styles.defaultBtn}>关闭</button>
                </div>
              </>
            ) : (
              <>
                <h3 style={{ margin: '0 0 12px' }}>确认删除</h3>
                <p>确定要删除模板「{deleteTarget.name}」吗？此操作不可恢复。</p>
                <div style={{ textAlign: 'right', display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
                  <button onClick={closeDialog} style={styles.defaultBtn}>取消</button>
                  <button onClick={handleDelete} disabled={deleting} style={styles.dangerBtn}>
                    {deleting ? '删除中...' : '确认删除'}
                  </button>
                </div>
              </>
            )}
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
  defaultBtn: {
    background: '#fff', border: '1px solid #d9d9d9', borderRadius: '4px',
    padding: '6px 16px', cursor: 'pointer', fontSize: '14px',
  },
  dangerBtn: {
    background: '#ff4d4f', color: '#fff', border: 'none', borderRadius: '4px',
    padding: '6px 16px', cursor: 'pointer', fontSize: '14px',
  },
};
