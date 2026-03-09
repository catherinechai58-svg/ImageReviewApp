import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../services/api';

interface Task {
  task_id: string;
  name: string;
  template_id: string;
  status: string;
  created_at: string;
  updated_at: string;
}

const statusColors: Record<string, { bg: string; color: string }> = {
  pending: { bg: '#f0f0f0', color: '#666' },
  queued: { bg: '#f9f0ff', color: '#722ed1' },
  fetching: { bg: '#e6f4ff', color: '#1677ff' },
  downloading: { bg: '#e6f4ff', color: '#1677ff' },
  recognizing: { bg: '#e6f4ff', color: '#1677ff' },
  completed: { bg: '#f6ffed', color: '#52c41a' },
  failed: { bg: '#fff2f0', color: '#ff4d4f' },
  partial_completed: { bg: '#fff7e6', color: '#fa8c16' },
};

const statusLabels: Record<string, string> = {
  pending: '待执行', queued: '排队中', fetching: '获取封面中', downloading: '下载图片中',
  recognizing: '识别中', completed: '已完成', failed: '失败', partial_completed: '部分完成',
};

const EXECUTE_ALLOWED = new Set(['pending', 'failed', 'partial_completed']);
const DELETE_ALLOWED = new Set(['pending', 'completed', 'failed', 'partial_completed']);

export default function TasksPage() {
  const navigate = useNavigate();
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionLoading, setActionLoading] = useState('');
  const [deleteTarget, setDeleteTarget] = useState<Task | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [templateNames, setTemplateNames] = useState<Record<string, string>>({});

  const fetchTasks = async () => {
    try {
      setLoading(true);
      const res = await api.get('/tasks');
      const list: Task[] = res.data.data || [];
      setTasks(list);
      setError('');

      // 获取所有关联模板名称
      const tplIds = [...new Set(list.map(t => t.template_id).filter(Boolean))];
      const names: Record<string, string> = {};
      await Promise.all(tplIds.map(async (id) => {
        try {
          const r = await api.get(`/prompts/${id}`);
          names[id] = r.data.data?.name || id;
        } catch {
          names[id] = id;
        }
      }));
      setTemplateNames(names);
    } catch {
      setError('获取任务列表失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchTasks(); }, []);

  const handleExecute = async (taskId: string) => {
    setActionLoading(taskId);
    setError('');
    try {
      await api.post(`/tasks/${taskId}/execute`);
      await fetchTasks();
    } catch (err: any) {
      setError(err.response?.data?.error?.message || '执行任务失败');
    } finally {
      setActionLoading('');
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await api.delete(`/tasks/${deleteTarget.task_id}`);
      setDeleteTarget(null);
      fetchTasks();
    } catch (err: any) {
      setError(err.response?.data?.error?.message || '删除失败');
      setDeleteTarget(null);
    } finally {
      setDeleting(false);
    }
  };

  // 按 template_id 分组
  const grouped: Record<string, Task[]> = {};
  for (const t of tasks) {
    const key = t.template_id || '_none';
    if (!grouped[key]) grouped[key] = [];
    grouped[key].push(t);
  }
  const groupKeys = Object.keys(grouped);

  if (loading) return <div style={{ padding: '20px', color: '#999' }}>加载中...</div>;

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
        <h2 style={{ margin: 0, fontSize: '18px' }}>任务管理</h2>
        <button onClick={() => navigate('/tasks/new')} style={styles.primaryBtn}>创建任务</button>
      </div>

      {error && <div style={styles.errorMsg}>{error}</div>}

      {tasks.length === 0 ? (
        <div style={{ color: '#999', textAlign: 'center', padding: '40px' }}>暂无任务，点击"创建任务"开始</div>
      ) : (
        groupKeys.map((tplId) => (
          <div key={tplId} style={{ marginBottom: '24px' }}>
            <div style={styles.groupHeader}>
              <span style={{ fontSize: '14px', fontWeight: 500, color: '#333' }}>
                {tplId === '_none' ? '未关联模板' : `模板：${templateNames[tplId] || tplId}`}
              </span>
              <span style={{ fontSize: '12px', color: '#999' }}>{grouped[tplId].length} 个任务</span>
            </div>
            <table style={styles.table}>
              <thead>
                <tr>
                  <th style={styles.th}>名称</th>
                  <th style={styles.th}>状态</th>
                  <th style={styles.th}>创建时间</th>
                  <th style={styles.th}>更新时间</th>
                  <th style={{ ...styles.th, width: '200px' }}>操作</th>
                </tr>
              </thead>
              <tbody>
                {grouped[tplId].map((t) => {
                  const sc = statusColors[t.status] || statusColors.pending;
                  return (
                    <tr key={t.task_id}>
                      <td style={styles.td}>{t.name}</td>
                      <td style={styles.td}>
                        <span style={{ ...styles.badge, background: sc.bg, color: sc.color }}>
                          {statusLabels[t.status] || t.status}
                        </span>
                      </td>
                      <td style={styles.td}>{t.created_at ? new Date(t.created_at).toLocaleString() : '-'}</td>
                      <td style={styles.td}>{t.updated_at ? new Date(t.updated_at).toLocaleString() : '-'}</td>
                      <td style={styles.td}>
                        <button onClick={() => navigate(`/tasks/${t.task_id}`)} style={styles.linkBtn}>详情</button>
                        {EXECUTE_ALLOWED.has(t.status) && (
                          <button
                            onClick={() => handleExecute(t.task_id)}
                            disabled={!!actionLoading}
                            style={{ ...styles.linkBtn, color: '#52c41a' }}
                          >
                            {actionLoading === t.task_id ? '执行中...' : '执行'}
                          </button>
                        )}
                        {DELETE_ALLOWED.has(t.status) && (
                          <button onClick={() => setDeleteTarget(t)} style={{ ...styles.linkBtn, color: '#ff4d4f' }}>删除</button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ))
      )}

      {deleteTarget && (
        <div style={styles.overlay}>
          <div style={styles.dialog}>
            <h3 style={{ margin: '0 0 12px' }}>确认删除</h3>
            <p>确定要删除任务「{deleteTarget.name}」吗？关联的结果和日志也会被删除，此操作不可恢复。</p>
            <div style={{ textAlign: 'right', display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
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
  groupHeader: {
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    padding: '8px 12px', background: '#fafafa', borderRadius: '4px 4px 0 0',
    border: '1px solid #f0f0f0', borderBottom: 'none',
  },
  table: { width: '100%', borderCollapse: 'collapse', background: '#fff', borderRadius: '0 0 4px 4px' },
  th: {
    textAlign: 'left', padding: '10px 12px', borderBottom: '2px solid #f0f0f0',
    fontSize: '13px', color: '#666', fontWeight: 500,
  },
  td: { padding: '10px 12px', borderBottom: '1px solid #f0f0f0', fontSize: '14px' },
  badge: {
    display: 'inline-block', padding: '2px 8px', borderRadius: '4px', fontSize: '12px', fontWeight: 500,
  },
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
