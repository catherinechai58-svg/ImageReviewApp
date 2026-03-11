import { useEffect, useState } from 'react';
import api from '../services/api';

interface Settings {
  task_max_workers: number;
  realtime_concurrency: number;
  youtube_api_key: string;
}

const defaultSettings: Settings = { task_max_workers: 3, realtime_concurrency: 5, youtube_api_key: '' };

export default function SettingsPage() {
  const [settings, setSettings] = useState<Settings>(defaultSettings);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    api.get('/settings').then((res) => {
      const d = res.data?.data;
      if (d) setSettings({ ...defaultSettings, ...d });
    }).catch(() => setError('加载设置失败'));
  }, []);

  const handleSave = async () => {
    setMsg(''); setError(''); setSaving(true);
    try {
      const res = await api.put('/settings', settings);
      const d = res.data?.data;
      if (d) setSettings({ ...defaultSettings, ...d });
      setMsg('保存成功');
    } catch (err: any) {
      setError(err.response?.data?.error?.message || '保存失败');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ maxWidth: '480px' }}>
      <h2 style={{ fontSize: '18px', marginBottom: '16px' }}>系统设置</h2>

      {error && <div style={styles.errorMsg}>{error}</div>}
      {msg && <div style={styles.successMsg}>{msg}</div>}

      <div style={styles.card}>
        <h3 style={styles.sectionTitle}>并发控制</h3>

        <div style={styles.field}>
          <label style={styles.label}>任务并发数</label>
          <input
            type="number" min={1} max={20} style={styles.inputSmall}
            value={settings.task_max_workers}
            onChange={(e) => setSettings((s) => ({ ...s, task_max_workers: Number(e.target.value) }))}
          />
          <div style={styles.hint}>同时执行的最大任务数（1~20），修改后立即生效</div>
        </div>

        <div style={styles.field}>
          <label style={styles.label}>实时推理并发数</label>
          <input
            type="number" min={1} max={50} style={styles.inputSmall}
            value={settings.realtime_concurrency}
            onChange={(e) => setSettings((s) => ({ ...s, realtime_concurrency: Number(e.target.value) }))}
          />
          <div style={styles.hint}>实时模式下同时调用 Bedrock API 的并发数（1~50），下次任务执行时生效</div>
        </div>

        <h3 style={{ ...styles.sectionTitle, marginTop: '24px' }}>YouTube API</h3>

        <div style={styles.field}>
          <label style={styles.label}>YouTube Data API Key</label>
          <input
            type="password" style={styles.input}
            value={settings.youtube_api_key}
            onChange={(e) => setSettings((s) => ({ ...s, youtube_api_key: e.target.value }))}
            placeholder="留空则使用 RSS Feed（每频道最多 15 条）"
          />
          <div style={styles.hint}>
            配置后可通过 YouTube API 获取频道全部视频，不受 15 条限制。
            <a href="https://console.cloud.google.com/apis/credentials" target="_blank" rel="noreferrer"
               style={{ color: '#1677ff', marginLeft: '4px' }}>获取 API Key</a>
          </div>
        </div>

        <button onClick={handleSave} disabled={saving} style={styles.primaryBtn}>
          {saving ? '保存中...' : '保存设置'}
        </button>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  card: { background: '#fff', borderRadius: '6px', padding: '20px', border: '1px solid #f0f0f0' },
  sectionTitle: { margin: '0 0 12px', fontSize: '14px', fontWeight: 600, color: '#333' },
  field: { marginBottom: '20px' },
  label: { display: 'block', marginBottom: '4px', fontSize: '14px', color: '#333', fontWeight: 500 },
  inputSmall: {
    width: '120px', padding: '6px 10px', border: '1px solid #d9d9d9', borderRadius: '4px',
    fontSize: '14px', boxSizing: 'border-box' as const,
  },
  input: {
    width: '100%', padding: '6px 10px', border: '1px solid #d9d9d9', borderRadius: '4px',
    fontSize: '14px', boxSizing: 'border-box' as const,
  },
  hint: { fontSize: '12px', color: '#999', marginTop: '4px' },
  primaryBtn: {
    background: '#1677ff', color: '#fff', border: 'none', borderRadius: '4px',
    padding: '6px 16px', cursor: 'pointer', fontSize: '14px',
  },
  errorMsg: {
    background: '#fff2f0', border: '1px solid #ffccc7', borderRadius: '4px',
    padding: '8px 12px', color: '#ff4d4f', marginBottom: '12px', fontSize: '13px',
  },
  successMsg: {
    background: '#f6ffed', border: '1px solid #b7eb8f', borderRadius: '4px',
    padding: '8px 12px', color: '#52c41a', marginBottom: '12px', fontSize: '13px',
  },
};
