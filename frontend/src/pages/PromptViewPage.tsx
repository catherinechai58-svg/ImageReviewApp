import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import api from '../services/api';

interface PromptDetail {
  template_id: string;
  name: string;
  description: string;
  user_prompt: string;
  review_rules: string;
  visibility: string;
  created_by: string;
  created_at: string;
  updated_at: string;
  version: number;
}

export default function PromptViewPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [data, setData] = useState<PromptDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    api.get(`/prompts/${id}`)
      .then((res) => setData(res.data.data))
      .catch(() => setError('加载模板失败'))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <div style={{ padding: '20px', color: '#999' }}>加载中...</div>;
  if (error) return <div style={{ padding: '20px', color: '#ff4d4f' }}>{error}</div>;
  if (!data) return <div style={{ padding: '20px', color: '#ff4d4f' }}>模板不存在</div>;

  return (
    <div style={{ maxWidth: '700px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '16px' }}>
        <button onClick={() => navigate('/prompts')} style={styles.linkBtn}>← 返回列表</button>
        <h2 style={{ margin: 0, fontSize: '18px' }}>{data.name}</h2>
        <span style={{
          display: 'inline-block', padding: '2px 8px', borderRadius: '4px', fontSize: '12px',
          background: data.visibility === 'public' ? '#e6f4ff' : '#f5f5f5',
          color: data.visibility === 'public' ? '#1677ff' : '#666',
        }}>
          {data.visibility === 'public' ? '公开' : '个人'}
        </span>
      </div>

      <div style={styles.card}>
        <div style={styles.row}><span style={styles.label}>描述</span><span>{data.description || '-'}</span></div>
        <div style={styles.row}><span style={styles.label}>创建者</span><span>{data.created_by || '-'}</span></div>
        <div style={styles.row}><span style={styles.label}>版本</span><span>v{data.version}</span></div>
        <div style={styles.row}><span style={styles.label}>创建时间</span><span>{new Date(data.created_at).toLocaleString()}</span></div>
        <div style={styles.row}><span style={styles.label}>更新时间</span><span>{new Date(data.updated_at).toLocaleString()}</span></div>
      </div>

      <div style={{ ...styles.card, marginTop: '16px' }}>
        <h3 style={styles.sectionTitle}>用户提示词</h3>
        <pre style={styles.codeBlock}>{data.user_prompt || '-'}</pre>
      </div>

      <div style={{ ...styles.card, marginTop: '16px' }}>
        <h3 style={styles.sectionTitle}>审核判定规则</h3>
        <pre style={styles.codeBlock}>{data.review_rules || '-'}</pre>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  linkBtn: {
    background: 'none', border: 'none', color: '#1677ff', cursor: 'pointer',
    fontSize: '13px', padding: '2px 6px',
  },
  card: {
    background: '#fff', borderRadius: '6px', padding: '16px',
    border: '1px solid #f0f0f0',
  },
  row: {
    display: 'flex', justifyContent: 'space-between', padding: '6px 0',
    fontSize: '13px', borderBottom: '1px solid #fafafa',
  },
  label: { color: '#999', minWidth: '80px' },
  sectionTitle: { margin: '0 0 8px', fontSize: '14px', fontWeight: 500, color: '#333' },
  codeBlock: {
    background: '#f5f5f5', padding: '12px', borderRadius: '4px', fontSize: '13px',
    fontFamily: 'monospace', whiteSpace: 'pre-wrap', wordBreak: 'break-all',
    margin: 0, lineHeight: '1.6',
  },
};
