import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../services/api';

interface PromptOption {
  template_id: string;
  name: string;
}

interface ModelOption {
  id: string;
  name: string;
}

interface FormData {
  name: string;
  description: string;
  channels: string;
  template_id: string;
  run_mode: string;
  model_id: string;
}

const emptyForm: FormData = { name: '', description: '', channels: '', template_id: '', run_mode: 'batch', model_id: '' };

export default function TaskFormPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState<FormData>(emptyForm);
  const [prompts, setPrompts] = useState<PromptOption[]>([]);
  const [models, setModels] = useState<ModelOption[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    api.get('/prompts').then((res) => setPrompts(res.data.data || [])).catch(() => {});
    api.get('/models').then((res) => {
      const list = res.data.data || [];
      setModels(list);
      if (list.length > 0) setForm((prev) => ({ ...prev, model_id: prev.model_id || list[0].id }));
    }).catch(() => {});
  }, []);

  const handleChange = (field: keyof FormData, value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!form.name.trim()) { setError('任务名称不能为空'); return; }
    if (!form.channels.trim()) { setError('请输入至少一个频道 ID 或 URL'); return; }
    if (!form.template_id) { setError('请选择提示词模板'); return; }
    if (!form.model_id) { setError('请选择推理模型'); return; }

    const channelIds = form.channels
      .split(/[\n,]+/)
      .map((s) => s.trim())
      .filter(Boolean);

    setSaving(true);
    try {
      await api.post('/tasks', {
        name: form.name.trim(),
        description: form.description.trim(),
        channel_ids: channelIds,
        template_id: form.template_id,
        run_mode: form.run_mode,
        model_id: form.model_id,
      });
      navigate('/tasks');
    } catch (err: any) {
      const msg = err.response?.data?.error?.message || '创建任务失败';
      setError(msg);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ maxWidth: '640px' }}>
      <h2 style={{ fontSize: '18px', marginBottom: '16px' }}>创建任务</h2>

      {error && <div style={styles.errorMsg}>{error}</div>}

      <form onSubmit={handleSubmit}>
        {/* 任务名称 */}
        <div style={styles.field}>
          <label style={styles.label}>任务名称 <span style={{ color: '#ff4d4f' }}>*</span></label>
          <input
            style={styles.input}
            value={form.name}
            onChange={(e) => handleChange('name', e.target.value)}
            placeholder="输入任务名称"
          />
        </div>

        {/* 描述 */}
        <div style={styles.field}>
          <label style={styles.label}>描述</label>
          <input
            style={styles.input}
            value={form.description}
            onChange={(e) => handleChange('description', e.target.value)}
            placeholder="输入任务描述（可选）"
          />
        </div>

        {/* 频道 ID / URL */}
        <div style={styles.field}>
          <label style={styles.label}>频道 ID / URL <span style={{ color: '#ff4d4f' }}>*</span></label>
          <textarea
            style={styles.textarea}
            rows={4}
            value={form.channels}
            onChange={(e) => handleChange('channels', e.target.value)}
            placeholder={'每行一个频道 ID 或 URL，例如：\nUCxxxxx\nhttps://www.youtube.com/channel/UCyyyyy'}
          />
          <div style={{ fontSize: '12px', color: '#999', marginTop: '4px' }}>支持频道 ID 或频道 URL，多个用换行或逗号分隔</div>
        </div>

        {/* 提示词模板选择 */}
        <div style={styles.field}>
          <label style={styles.label}>提示词模板 <span style={{ color: '#ff4d4f' }}>*</span></label>
          <select
            style={styles.input}
            value={form.template_id}
            onChange={(e) => handleChange('template_id', e.target.value)}
          >
            <option value="">请选择模板</option>
            {prompts.map((p) => (
              <option key={p.template_id} value={p.template_id}>{p.name}</option>
            ))}
          </select>
        </div>

        {/* 推理模型选择 */}
        <div style={styles.field}>
          <label style={styles.label}>推理模型 <span style={{ color: '#ff4d4f' }}>*</span></label>
          <select
            style={styles.input}
            value={form.model_id}
            onChange={(e) => handleChange('model_id', e.target.value)}
          >
            {models.map((m) => (
              <option key={m.id} value={m.id}>{m.name}</option>
            ))}
          </select>
        </div>

        {/* 运行模式 */}
        <div style={styles.field}>
          <label style={styles.label}>运行模式 <span style={{ color: '#ff4d4f' }}>*</span></label>
          <div style={{ display: 'flex', gap: '16px' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer' }}>
              <input type="radio" name="run_mode" value="batch" checked={form.run_mode === 'batch'} onChange={() => handleChange('run_mode', 'batch')} />
              批量模式 (Batch)
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer' }}>
              <input type="radio" name="run_mode" value="realtime" checked={form.run_mode === 'realtime'} onChange={() => handleChange('run_mode', 'realtime')} />
              实时模式 (Realtime)
            </label>
          </div>
        </div>

        {/* 按钮 */}
        <div style={{ display: 'flex', gap: '8px', marginTop: '16px' }}>
          <button type="submit" disabled={saving} style={styles.primaryBtn}>
            {saving ? '创建中...' : '创建任务'}
          </button>
          <button type="button" onClick={() => navigate('/tasks')} style={styles.defaultBtn}>取消</button>
        </div>
      </form>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  errorMsg: {
    background: '#fff2f0', border: '1px solid #ffccc7', borderRadius: '4px',
    padding: '8px 12px', color: '#ff4d4f', marginBottom: '12px', fontSize: '13px',
  },
  field: { marginBottom: '16px' },
  label: { display: 'block', marginBottom: '4px', fontSize: '14px', color: '#333' },
  input: {
    width: '100%', padding: '6px 10px', border: '1px solid #d9d9d9', borderRadius: '4px',
    fontSize: '14px', boxSizing: 'border-box' as const,
  },
  textarea: {
    width: '100%', padding: '6px 10px', border: '1px solid #d9d9d9', borderRadius: '4px',
    fontSize: '14px', fontFamily: 'monospace', resize: 'vertical' as const, boxSizing: 'border-box' as const,
  },
  primaryBtn: {
    background: '#1677ff', color: '#fff', border: 'none', borderRadius: '4px',
    padding: '6px 16px', cursor: 'pointer', fontSize: '14px',
  },
  defaultBtn: {
    background: '#fff', border: '1px solid #d9d9d9', borderRadius: '4px',
    padding: '6px 16px', cursor: 'pointer', fontSize: '14px',
  },
};
