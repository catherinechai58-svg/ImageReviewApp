import { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import api from '../services/api';

// 识别结果条目
interface ResultItem {
  task_id: string;
  image_name: string;
  video_id: string;
  channel_id: string;
  channel_name: string;
  s3_key: string;
  status: string;
  result_json: Record<string, any> | null;
  review_result: string;
  error_message: string;
  created_at: string;
}

export default function ResultsPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [results, setResults] = useState<ResultItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState('');
  const [lastKey, setLastKey] = useState<string | null>(null);

  // 过滤条件
  const [filterReview, setFilterReview] = useState('');
  const [filterStatus, setFilterStatus] = useState('');

  // 展开的 result_json 行
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());

  // 加载结果
  const fetchResults = useCallback(async (append = false) => {
    try {
      append ? setLoadingMore(true) : setLoading(true);
      const params: Record<string, string> = { page_size: '20' };
      if (append && lastKey) params.last_evaluated_key = lastKey;
      if (filterReview) params.review_result = filterReview;
      if (filterStatus) params.status = filterStatus;

      const res = await api.get(`/tasks/${id}/results`, { params });
      const data = res.data.data || [];
      const newLastKey = res.data.last_evaluated_key || null;

      setResults(prev => append ? [...prev, ...data] : data);
      setLastKey(newLastKey);
      setError('');
    } catch {
      setError('获取结果失败');
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }, [id, lastKey, filterReview, filterStatus]);

  // 初始加载 & 过滤变化时重新加载
  useEffect(() => {
    setResults([]);
    setLastKey(null);
    fetchResults(false);
  }, [id, filterReview, filterStatus]);

  // 下载结果文件
  const handleDownload = async () => {
    try {
      const res = await api.get(`/tasks/${id}/results/download`);
      const url = res.data.data?.url || res.data.url;
      if (url) window.open(url, '_blank');
      else setError('未获取到下载链接');
    } catch {
      setError('获取下载链接失败');
    }
  };

  // 切换展开/收起 result_json
  const toggleExpand = (key: string) => {
    setExpandedRows(prev => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });
  };

  // YouTube 缩略图 URL
  const thumbUrl = (videoId: string) =>
    `https://i.ytimg.com/vi/${videoId}/default.jpg`;

  if (loading) return <div style={{ padding: '20px', color: '#999' }}>加载中...</div>;

  return (
    <div>
      {/* 页头 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '16px' }}>
        <button onClick={() => navigate(`/tasks/${id}`)} style={styles.linkBtn}>← 返回任务详情</button>
        <h2 style={{ margin: 0, fontSize: '18px' }}>识别结果</h2>
        <button onClick={handleDownload} style={styles.primaryBtn}>下载结果</button>
      </div>

      {error && <div style={styles.errorMsg}>{error}</div>}

      {/* 过滤面板 */}
      <div style={{ display: 'flex', gap: '12px', marginBottom: '16px', alignItems: 'center' }}>
        <label style={styles.filterLabel}>
          审核结论：
          <select value={filterReview} onChange={e => setFilterReview(e.target.value)} style={styles.select}>
            <option value="">全部</option>
            <option value="pass">pass</option>
            <option value="fail">fail</option>
          </select>
        </label>
        <label style={styles.filterLabel}>
          识别状态：
          <select value={filterStatus} onChange={e => setFilterStatus(e.target.value)} style={styles.select}>
            <option value="">全部</option>
            <option value="success">success</option>
            <option value="failed">failed</option>
          </select>
        </label>
      </div>

      {/* 结果表格 */}
      {results.length === 0 ? (
        <div style={{ color: '#999', textAlign: 'center', padding: '40px' }}>暂无结果</div>
      ) : (
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.th}>缩略图</th>
              <th style={styles.th}>video_id</th>
              <th style={styles.th}>频道名称</th>
              <th style={styles.th}>状态</th>
              <th style={styles.th}>审核结论</th>
              <th style={styles.th}>识别结果</th>
            </tr>
          </thead>
          <tbody>
            {results.map((r) => {
              const rowKey = `${r.task_id}-${r.image_name}`;
              const expanded = expandedRows.has(rowKey);
              return (
                <tr key={rowKey}>
                  <td style={styles.td}>
                    <img
                      src={thumbUrl(r.video_id)}
                      alt={r.video_id}
                      style={{ width: '60px', height: '45px', objectFit: 'cover', borderRadius: '2px' }}
                      onError={e => { (e.target as HTMLImageElement).style.display = 'none'; }}
                    />
                  </td>
                  <td style={{ ...styles.td, fontFamily: 'monospace', fontSize: '12px' }}>{r.video_id}</td>
                  <td style={styles.td}>{r.channel_name || '-'}</td>
                  <td style={styles.td}>
                    <span style={{
                      ...styles.badge,
                      background: r.status === 'success' ? '#f6ffed' : '#fff2f0',
                      color: r.status === 'success' ? '#52c41a' : '#ff4d4f',
                    }}>
                      {r.status}
                    </span>
                  </td>
                  <td style={styles.td}>
                    {r.review_result ? (
                      <span style={{
                        ...styles.badge,
                        background: r.review_result === 'pass' ? '#f6ffed' : '#fff2f0',
                        color: r.review_result === 'pass' ? '#52c41a' : '#ff4d4f',
                      }}>
                        {r.review_result}
                      </span>
                    ) : '-'}
                  </td>
                  <td style={{ ...styles.td, maxWidth: '300px' }}>
                    {r.result_json ? (
                      <div>
                        <button onClick={() => toggleExpand(rowKey)} style={styles.linkBtn}>
                          {expanded ? '收起' : '展开'}
                        </button>
                        {expanded && (
                          <pre style={styles.jsonPre}>
                            {JSON.stringify(r.result_json, null, 2)}
                          </pre>
                        )}
                      </div>
                    ) : (
                      <span style={{ color: '#999', fontSize: '12px' }}>{r.error_message || '-'}</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}

      {/* 加载更多 */}
      {lastKey && (
        <div style={{ textAlign: 'center', padding: '16px' }}>
          <button onClick={() => fetchResults(true)} disabled={loadingMore} style={styles.primaryBtn}>
            {loadingMore ? '加载中...' : '加载更多'}
          </button>
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
  linkBtn: {
    background: 'none', border: 'none', color: '#1677ff', cursor: 'pointer',
    fontSize: '13px', padding: '2px 6px',
  },
  filterLabel: { fontSize: '13px', color: '#333', display: 'flex', alignItems: 'center', gap: '4px' },
  select: {
    padding: '4px 8px', borderRadius: '4px', border: '1px solid #d9d9d9',
    fontSize: '13px', outline: 'none',
  },
  table: { width: '100%', borderCollapse: 'collapse', background: '#fff', borderRadius: '4px' },
  th: {
    textAlign: 'left', padding: '10px 12px', borderBottom: '2px solid #f0f0f0',
    fontSize: '13px', color: '#666', fontWeight: 500,
  },
  td: { padding: '10px 12px', borderBottom: '1px solid #f0f0f0', fontSize: '14px', verticalAlign: 'top' },
  badge: {
    display: 'inline-block', padding: '2px 8px', borderRadius: '4px', fontSize: '12px', fontWeight: 500,
  },
  jsonPre: {
    background: '#fafafa', border: '1px solid #f0f0f0', borderRadius: '4px',
    padding: '8px', fontSize: '11px', maxHeight: '200px', overflow: 'auto',
    whiteSpace: 'pre-wrap', wordBreak: 'break-all', marginTop: '4px',
  },
};
