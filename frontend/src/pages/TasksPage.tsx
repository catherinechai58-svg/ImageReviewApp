import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../services/api';

// 任务类型定义
interface Task {
  task_id: string;
  name: string;
  status: string;
  created_at: string;
  updated_at: string;
}

// 状态颜色映射
const statusColors: Record<string, { bg: string; color: string }> = {
  pending: { bg: '#f0f0f0', color: '#666' },
  fetching: { bg: '#e6f4ff', color: '#1677ff' },
  downloading: { bg: '#e6f4ff', color: '#1677ff' },
  recognizing: { bg: '#e6f4ff', color: '#1677ff' },
  completed: { bg: '#f6ffed', color: '#52c41a' },
  failed: { bg: '#fff2f0', color: '#ff4d4f' },
  partial_completed: { bg: '#fff7e6', color: '#fa8c16' },
};

// 状态中文标签
const statusLabels: Record<string, string> = {
  pending: '待执行',
  fetching: '获取封面中',
  downloading: '下载图片中',
  recognizing: '识别中',
  completed: '已完成',
  failed: '失败',
  partial_completed: '部分完成',
};

export default function TasksPage() {
  const navigate = useNavigate();
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchTasks = async () => {
    try {
      setLoading(true);
      const res = await api.get('/tasks');
      setTasks(res.data.data || []);
      setError('');
    } catch {
      setError('获取任务列表失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchTasks(); }, []);

  if (loading) return <div style={{ padding: '20px', color: '#999' }}>加载中...</div>;

  return (
    <div>
      {/* 页头 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
        <h2 style={{ margin: 0, fontSize: '18px' }}>任务管理</h2>
        <button onClick={() => navigate('/tasks/new')} style={styles.primaryBtn}>创建任务</button>
      </div>

      {error && <div style={styles.errorMsg}>{error}</div>}

      {tasks.length === 0 ? (
        <div style={{ color: '#999', textAlign: 'center', padding: '40px' }}>暂无任务，点击"创建任务"开始</div>
      ) : (
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.th}>名称</th>
              <th style={styles.th}>状态</th>
              <th style={styles.th}>创建时间</th>
              <th style={styles.th}>更新时间</th>
              <th style={{ ...styles.th, width: '80px' }}>操作</th>
            </tr>
          </thead>
          <tbody>
            {tasks.map((t) => {
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
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
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
  badge: {
    display: 'inline-block', padding: '2px 8px', borderRadius: '4px', fontSize: '12px', fontWeight: 500,
  },
  linkBtn: {
    background: 'none', border: 'none', color: '#1677ff', cursor: 'pointer',
    fontSize: '13px', padding: '2px 6px',
  },
};
