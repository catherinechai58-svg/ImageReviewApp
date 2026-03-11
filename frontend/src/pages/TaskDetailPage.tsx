import { useEffect, useRef, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import api from '../services/api';

interface TaskDetail {
  task_id: string;
  name: string;
  description: string;
  channel_ids: string[];
  template_id: string;
  run_mode: string;
  model_id: string;
  status: string;
  total_images: number;
  success_count: number;
  failure_count: number;
  created_at: string;
  updated_at: string;
}

interface LogEntry {
  timestamp: string;
  operation_type: string;
  target: string;
  result: string;
  message: string;
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

const modeLabels: Record<string, string> = { batch: '批量模式', realtime: '实时模式' };

export default function TaskDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [task, setTask] = useState<TaskDetail | null>(null);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionLoading, setActionLoading] = useState('');
  const [templateName, setTemplateName] = useState('');

  const fetchTask = async () => {
    try {
      const res = await api.get(`/tasks/${id}`);
      const t = res.data.data;
      setTask(t);
      // 获取模板名称
      if (t.template_id) {
        try {
          const tplRes = await api.get(`/prompts/${t.template_id}`);
          setTemplateName(tplRes.data.data?.name || t.template_id);
        } catch {
          setTemplateName(t.template_id);
        }
      }
    } catch {
      setError('获取任务详情失败');
    }
  };

  const fetchLogs = async () => {
    try {
      const res = await api.get(`/tasks/${id}/logs`);
      setLogs(res.data.data || []);
    } catch { /* ignore */ }
  };

  const logsEndRef = useRef<HTMLDivElement>(null);
  const logsContainerRef = useRef<HTMLDivElement>(null);

  const isRunning = task ? ['queued', 'fetching', 'downloading', 'recognizing'].includes(task.status) : false;

  useEffect(() => {
    setLoading(true);
    Promise.all([fetchTask(), fetchLogs()]).finally(() => setLoading(false));
  }, [id]);

  // 运行中时每 5 秒自动刷新任务状态和日志
  useEffect(() => {
    if (!isRunning) return;
    const timer = setInterval(() => {
      fetchTask();
      fetchLogs();
    }, 5000);
    return () => clearInterval(timer);
  }, [isRunning, id]);

  // 日志更新时自动滚动到底部
  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  const handleExecute = async () => {
    setActionLoading('execute');
    setError('');
    try {
      await api.post(`/tasks/${id}/execute`);
      await fetchTask();
    } catch (err: any) {
      setError(err.response?.data?.error?.message || '执行任务失败');
    } finally {
      setActionLoading('');
    }
  };

  const handleRetry = async () => {
    setActionLoading('retry');
    setError('');
    try {
      await api.post(`/tasks/${id}/retry`);
      await fetchTask();
    } catch (err: any) {
      setError(err.response?.data?.error?.message || '重做失败');
    } finally {
      setActionLoading('');
    }
  };

  const handleRetryAll = async () => {
    if (!confirm('确定要强制重做全部图片吗？这将重新识别所有图片（包括已成功的）。')) return;
    setActionLoading('retryAll');
    setError('');
    try {
      await api.post(`/tasks/${id}/retry-all`);
      await fetchTask();
    } catch (err: any) {
      setError(err.response?.data?.error?.message || '强制重做失败');
    } finally {
      setActionLoading('');
    }
  };

  if (loading) return <div style={{ padding: '20px', color: '#999' }}>加载中...</div>;
  if (!task) return <div style={{ padding: '20px', color: '#ff4d4f' }}>任务不存在</div>;

  const sc = statusColors[task.status] || statusColors.pending;
  const canExecute = task.status === 'pending';
  const canRetry = ['completed', 'failed', 'partial_completed'].includes(task.status);
  const canEdit = ['pending', 'failed', 'partial_completed', 'completed'].includes(task.status);

  return (
    <div>
      {/* 页头 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '16px' }}>
        <button onClick={() => navigate('/tasks')} style={styles.linkBtn}>← 返回列表</button>
        <h2 style={{ margin: 0, fontSize: '18px' }}>{task.name}</h2>
        <span style={{ ...styles.badge, background: sc.bg, color: sc.color }}>
          {statusLabels[task.status] || task.status}
        </span>
      </div>

      {error && <div style={styles.errorMsg}>{error}</div>}

      {/* 操作按钮 */}
      <div style={{ display: 'flex', gap: '8px', marginBottom: '20px' }}>
        {canEdit && (
          <button onClick={() => navigate(`/tasks/${id}/edit`)} style={styles.defaultBtn}>
            编辑任务
          </button>
        )}
        {canExecute && (
          <button onClick={handleExecute} disabled={!!actionLoading} style={styles.primaryBtn}>
            {actionLoading === 'execute' ? '执行中...' : '执行任务'}
          </button>
        )}
        {canRetry && (
          <button onClick={handleRetry} disabled={!!actionLoading} style={styles.warningBtn}>
            {actionLoading === 'retry' ? '重做中...' : '重做失败图片'}
          </button>
        )}
        {canRetry && (
          <button onClick={handleRetryAll} disabled={!!actionLoading} style={styles.dangerBtn}>
            {actionLoading === 'retryAll' ? '重做中...' : '强制重做全部'}
          </button>
        )}
        {(task.total_images ?? 0) > 0 && (
          <button onClick={() => navigate(`/tasks/${id}/results`)} style={styles.primaryBtn}>
            查看结果
          </button>
        )}
      </div>

      {/* 配置信息 + 进度统计 */}
      <div style={{ display: 'flex', gap: '16px', marginBottom: '20px', flexWrap: 'wrap' }}>
        <div style={styles.card}>
          <h3 style={styles.cardTitle}>配置信息</h3>
          <div style={styles.infoRow}><span style={styles.infoLabel}>描述</span><span>{task.description || '-'}</span></div>
          <div style={styles.infoRow}><span style={styles.infoLabel}>运行模式</span><span>{modeLabels[task.run_mode] || task.run_mode}</span></div>
          <div style={styles.infoRow}><span style={styles.infoLabel}>推理模型</span><span style={{ fontSize: '12px', fontFamily: 'monospace' }}>{task.model_id || '-'}</span></div>
          <div style={styles.infoRow}>
            <span style={styles.infoLabel}>提示词模板</span>
            <span
              style={{ color: '#1677ff', cursor: 'pointer', fontSize: '13px' }}
              onClick={() => navigate(`/prompts/${task.template_id}/view`)}
            >
              {templateName || task.template_id}
            </span>
          </div>
          <div style={styles.infoRow}><span style={styles.infoLabel}>频道数</span><span>{task.channel_ids?.length || 0}</span></div>
          <div style={styles.infoRow}><span style={styles.infoLabel}>创建时间</span><span>{new Date(task.created_at).toLocaleString()}</span></div>
          <div style={styles.infoRow}><span style={styles.infoLabel}>更新时间</span><span>{new Date(task.updated_at).toLocaleString()}</span></div>
        </div>

        <div style={styles.card}>
          <h3 style={styles.cardTitle}>进度统计</h3>
          <div style={{ display: 'flex', gap: '24px', marginTop: '8px' }}>
            <div style={styles.statItem}>
              <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#333' }}>{task.total_images ?? 0}</div>
              <div style={{ fontSize: '12px', color: '#999' }}>总图片数</div>
            </div>
            <div style={styles.statItem}>
              <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#52c41a' }}>{task.success_count ?? 0}</div>
              <div style={{ fontSize: '12px', color: '#999' }}>成功</div>
            </div>
            <div style={styles.statItem}>
              <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#ff4d4f' }}>{task.failure_count ?? 0}</div>
              <div style={{ fontSize: '12px', color: '#999' }}>失败</div>
            </div>
          </div>
        </div>
      </div>

      {/* 频道列表 */}
      {task.channel_ids && task.channel_ids.length > 0 && (
        <div style={{ ...styles.card, marginBottom: '20px' }}>
          <h3 style={styles.cardTitle}>频道列表</h3>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginTop: '4px' }}>
            {task.channel_ids.map((ch, i) => (
              <span key={i} style={{ background: '#f5f5f5', padding: '2px 8px', borderRadius: '4px', fontSize: '12px', fontFamily: 'monospace' }}>{ch}</span>
            ))}
          </div>
        </div>
      )}

      {/* 日志面板 */}
      <div style={styles.card}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h3 style={styles.cardTitle}>运行日志</h3>
          <button onClick={fetchLogs} style={styles.linkBtn}>刷新</button>
        </div>
        {logs.length === 0 ? (
          <div style={{ color: '#999', fontSize: '13px', padding: '12px 0' }}>暂无日志</div>
        ) : (
          <div ref={logsContainerRef} style={{ maxHeight: '360px', overflowY: 'auto', marginTop: '8px' }}>
            <table style={styles.table}>
              <thead>
                <tr>
                  <th style={styles.th}>时间</th>
                  <th style={styles.th}>操作</th>
                  <th style={styles.th}>对象</th>
                  <th style={styles.th}>结果</th>
                  <th style={styles.th}>信息</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log, i) => (
                  <tr key={i}>
                    <td style={{ ...styles.td, fontSize: '12px', whiteSpace: 'nowrap' }}>{log.timestamp ? new Date(log.timestamp).toLocaleString() : '-'}</td>
                    <td style={styles.td}>{log.operation_type}</td>
                    <td style={{ ...styles.td, maxWidth: '160px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{log.target}</td>
                    <td style={styles.td}>
                      <span style={{ color: log.result === 'success' ? '#52c41a' : '#ff4d4f' }}>{log.result}</span>
                    </td>
                    <td style={{
                      ...styles.td, maxWidth: '240px', overflow: 'hidden',
                      textOverflow: 'ellipsis', whiteSpace: 'nowrap', cursor: 'default',
                      position: 'relative',
                    }} title={log.message || '-'}>
                      {log.message || '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div ref={logsEndRef} />
          </div>
        )}
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  primaryBtn: {
    background: '#1677ff', color: '#fff', border: 'none', borderRadius: '4px',
    padding: '6px 16px', cursor: 'pointer', fontSize: '14px',
  },
  warningBtn: {
    background: '#fa8c16', color: '#fff', border: 'none', borderRadius: '4px',
    padding: '6px 16px', cursor: 'pointer', fontSize: '14px',
  },
  defaultBtn: {
    background: '#fff', border: '1px solid #d9d9d9', borderRadius: '4px',
    padding: '6px 16px', cursor: 'pointer', fontSize: '14px',
  },
  dangerBtn: {
    background: '#ff4d4f', color: '#fff', border: 'none', borderRadius: '4px',
    padding: '6px 16px', cursor: 'pointer', fontSize: '14px',
  },
  errorMsg: {
    background: '#fff2f0', border: '1px solid #ffccc7', borderRadius: '4px',
    padding: '8px 12px', color: '#ff4d4f', marginBottom: '12px', fontSize: '13px',
  },
  badge: {
    display: 'inline-block', padding: '2px 8px', borderRadius: '4px', fontSize: '12px', fontWeight: 500,
  },
  linkBtn: {
    background: 'none', border: 'none', color: '#1677ff', cursor: 'pointer',
    fontSize: '13px', padding: '2px 6px',
  },
  card: {
    background: '#fff', borderRadius: '6px', padding: '16px', flex: '1 1 300px',
    border: '1px solid #f0f0f0',
  },
  cardTitle: { margin: '0 0 8px', fontSize: '14px', fontWeight: 500, color: '#333' },
  infoRow: {
    display: 'flex', justifyContent: 'space-between', padding: '4px 0',
    fontSize: '13px', borderBottom: '1px solid #fafafa',
  },
  infoLabel: { color: '#999', minWidth: '80px' },
  statItem: { textAlign: 'center' as const },
  table: { width: '100%', borderCollapse: 'collapse' as const },
  th: {
    textAlign: 'left' as const, padding: '6px 8px', borderBottom: '2px solid #f0f0f0',
    fontSize: '12px', color: '#666', fontWeight: 500,
  },
  td: { padding: '6px 8px', borderBottom: '1px solid #f0f0f0', fontSize: '13px' },
};
