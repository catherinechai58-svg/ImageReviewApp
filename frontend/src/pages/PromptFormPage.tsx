import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import api from '../services/api';

// 表单数据
interface FormData {
  name: string;
  description: string;
  system_prompt: string;
  user_prompt: string;
}

const emptyForm: FormData = { name: '', description: '', system_prompt: '', user_prompt: '' };

export default function PromptFormPage() {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const isEdit = Boolean(id);

  const [form, setForm] = useState<FormData>(emptyForm);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  // 编辑模式：加载现有模板
  useEffect(() => {
    if (!id) return;
    setLoading(true);
    api.get(`/prompts/${id}`)
      .then((res) => setForm({
        name: res.data.data.name || '',
        description: res.data.data.description || '',
        system_prompt: res.data.data.system_prompt || '',
        user_prompt: res.data.data.user_prompt || '',
      }))
      .catch(() => setError('加载模板失败'))
      .finally(() => setLoading(false));
  }, [id]);

  const handleChange = (field: keyof FormData, value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    // 前端基本校验
    if (!form.name.trim()) { setError('名称不能为空'); return; }
    if (!form.system_prompt.trim()) { setError('系统提示词不能为空'); return; }
    if (!form.user_prompt.trim()) { setError('用户提示词不能为空'); return; }

    setSaving(true);
    try {
      if (isEdit) {
        await api.put(`/prompts/${id}`, form);
      } else {
        await api.post('/prompts', form);
      }
      navigate('/prompts');
    } catch (err: any) {
      const msg = err.response?.data?.error?.message || '保存失败';
      setError(msg);
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div style={{ padding: '20px', color: '#999' }}>加载中...</div>;

  return (
    <div style={{ maxWidth: '640px' }}>
      <h2 style={{ fontSize: '18px', marginBottom: '16px' }}>{isEdit ? '编辑模板' : '创建模板'}</h2>

      {error && <div style={styles.errorMsg}>{error}</div>}

      <form onSubmit={handleSubmit}>
        {/* 名称 */}
        <div style={styles.field}>
          <label style={styles.label}>名称 <span style={{ color: '#ff4d4f' }}>*</span></label>
          <input
            style={styles.input}
            value={form.name}
            onChange={(e) => handleChange('name', e.target.value)}
            placeholder="输入模板名称"
          />
        </div>

        {/* 描述 */}
        <div style={styles.field}>
          <label style={styles.label}>描述</label>
          <input
            style={styles.input}
            value={form.description}
            onChange={(e) => handleChange('description', e.target.value)}
            placeholder="输入模板描述（可选）"
          />
        </div>

        {/* 系统提示词 */}
        <div style={styles.field}>
          <label style={styles.label}>系统提示词 <span style={{ color: '#ff4d4f' }}>*</span></label>
          <textarea
            style={styles.textarea}
            rows={6}
            value={form.system_prompt}
            onChange={(e) => handleChange('system_prompt', e.target.value)}
            placeholder="定义模型角色和行为，例如：你是一个图片内容审核专家..."
          />
        </div>

        {/* 用户提示词 */}
        <div style={styles.field}>
          <label style={styles.label}>用户提示词 <span style={{ color: '#ff4d4f' }}>*</span></label>
          <textarea
            style={styles.textarea}
            rows={6}
            value={form.user_prompt}
            onChange={(e) => handleChange('user_prompt', e.target.value)}
            placeholder="定义具体分析指令，例如：分析这张图片是否包含儿童..."
          />
        </div>

        {/* 按钮 */}
        <div style={{ display: 'flex', gap: '8px', marginTop: '16px' }}>
          <button type="submit" disabled={saving} style={styles.primaryBtn}>
            {saving ? '保存中...' : '保存'}
          </button>
          <button type="button" onClick={() => navigate('/prompts')} style={styles.defaultBtn}>取消</button>
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
    fontSize: '14px', boxSizing: 'border-box',
  },
  textarea: {
    width: '100%', padding: '6px 10px', border: '1px solid #d9d9d9', borderRadius: '4px',
    fontSize: '14px', fontFamily: 'monospace', resize: 'vertical', boxSizing: 'border-box',
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
