import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../services/api';

// 模板类型定义
interface PromptTemplate {
  template_id: string;
  name: string;
  description: string;
  created_at: string;
}

// 删除冲突时返回的关联任务
interface TaskRef {
  task_id: string;
  name: string;
}

export default function PromptsPage() {
  const navigate = useNavigate();
  const [templates, setTemplates] = useState<PromptTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // 删除确认对话框状态
  const [deleteTarget, setDeleteTarget] = useState<PromptTemplate | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [conflictTasks, setConflictTasks] = useState<TaskRef[]>([]);

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

  useEffect(() => { fetchTemplates(); }, []);

  // 删除模板
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
        // 被引用，展示关联任务
        const details = err.response.data?.error?.details || [];
        setConflictTasks(details);
      } else {
        setError('删除失败');
        setDeleteTarget(null);
      }
    } finally {
      setDeleting(false);
    }
  };

  const closeDialog = () => {
    setDeleteTarget(null);
    setConflictTasks([]);
  };

  if (loading) return <div style={{ padding: '20px', color: '#999' }}>加载中...</div>;

  return (
    <div>
      {/* 页头 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
        <h2 style={{ margin: 0, fontSize: '18px' }}>提示词模板</h2>
        <button onClick={() => navigate('/prompts/new')} style={styles.primaryBtn}>创建模板</button>
      </div>

      {error && <div style={styles.errorMsg}>{error}</div>}

      {/* 模板列表 */}
      {templates.length === 0 ? (
        <div style={{ color: '#999', textAlign: 'center', padding: '40px' }}>暂无模板，点击"创建模板"开始</div>
      ) : (
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.th}>名称</th>
              <th style={styles.th}>描述</th>
              <th style={styles.th}>创建时间</th>
              <th style={{ ...styles.th, width: '140px' }}>操作</th>
            </tr>
          </thead>
          <tbody>
            {templates.map((t) => (
              <tr key={t.template_id}>
                <td style={styles.td}>{t.name}</td>
                <td style={styles.td}>{t.description || '-'}</td>
                <td style={styles.td}>{t.created_at ? new Date(t.created_at).toLocaleString() : '-'}</td>
                <td style={styles.td}>
                  <button onClick={() => navigate(`/prompts/${t.template_id}/edit`)} style={styles.linkBtn}>编辑</button>
                  <button onClick={() => setDeleteTarget(t)} style={{ ...styles.linkBtn, color: '#ff4d4f' }}>删除</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {/* 删除确认对话框 */}
      {deleteTarget && (
        <div style={styles.overlay}>
          <div style={styles.dialog}>
            {conflictTasks.length > 0 ? (
              <>
                <h3 style={{ margin: '0 0 12px' }}>无法删除</h3>
                <p>模板「{deleteTarget.name}」正在被以下任务引用：</p>
                <ul style={{ margin: '8px 0', paddingLeft: '20px' }}>
                  {conflictTasks.map((t) => (
                    <li key={t.task_id}>{t.name || t.task_id}</li>
                  ))}
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
  table: {
    width: '100%', borderCollapse: 'collapse', background: '#fff', borderRadius: '4px',
  },
  th: {
    textAlign: 'left', padding: '10px 12px', borderBottom: '2px solid #f0f0f0',
    fontSize: '13px', color: '#666', fontWeight: 500,
  },
  td: {
    padding: '10px 12px', borderBottom: '1px solid #f0f0f0', fontSize: '14px',
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
