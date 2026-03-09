import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import api from '../services/api';

const REVIEW_RULES_EXAMPLE = `- 如果 contains_child 为 true 或 is_child_targeted 为 true，则 review_result 必须为 "fail"
- 仅当 contains_child 为 false 且 is_child_targeted 为 false 时，review_result 才为 "pass"`;

interface FormData {
  name: string;
  description: string;
  user_prompt: string;
  review_rules: string;
  visibility: string;
}

const emptyForm: FormData = { name: '', description: '', user_prompt: '', review_rules: '', visibility: 'private' };

export default function PromptFormPage() {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const isEdit = Boolean(id);

  const [form, setForm] = useState<FormData>(emptyForm);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    api.get(`/prompts/${id}`)
      .then((res) => setForm({
        name: res.data.data.name || '',
        description: res.data.data.description || '',
        user_prompt: res.data.data.user_prompt || '',
        review_rules: res.data.data.review_rules || '',
        visibility: res.data.data.visibility || 'private',
      }))
      .catch(() => setError('加载模板失败'))
      .finally(() => setLoading(false));
  }, [id]);

  const handleChange = (field: keyof FormData, value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  const fillExample = () => {
    setForm((prev) => ({ ...prev, review_rules: REVIEW_RULES_EXAMPLE }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!form.name.trim()) { setError('名称不能为空'); return; }
    if (!form.user_prompt.trim()) { setError('用户提示词不能为空'); return; }
    if (!form.review_rules.trim()) { setError('审核判定规则不能为空'); return; }
    if (!form.review_rules.includes('review_result')) {
      setError('审核判定规则必须包含 review_result 的判定逻辑');
      return;
    }

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

        {/* 可见性 */}
        <div style={styles.field}>
          <label style={styles.label}>可见性</label>
          <div style={{ display: 'flex', gap: '16px' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer' }}>
              <input type="radio" name="visibility" value="private" checked={form.visibility === 'private'} onChange={() => handleChange('visibility', 'private')} />
              个人（仅自己可见）
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer' }}>
              <input type="radio" name="visibility" value="public" checked={form.visibility === 'public'} onChange={() => handleChange('visibility', 'public')} />
              公开（所有人可见）
            </label>
          </div>
        </div>

        {/* 用户提示词 */}
        <div style={styles.field}>
          <label style={styles.label}>用户提示词（分析要求） <span style={{ color: '#ff4d4f' }}>*</span></label>
          <textarea
            style={styles.textarea}
            rows={8}
            value={form.user_prompt}
            onChange={(e) => handleChange('user_prompt', e.target.value)}
            placeholder={'定义 JSON 输出结构，例如：\n{\n    "image_name": "{image_name}",\n    "contains_child": true or false,\n    "age_group": "infant" | "toddler" | "kids" | "teen" | "none" | "unknown",\n    "is_child_targeted": true or false,\n    "confidence": 0.0 to 1.0\n}'}
          />
        </div>

        {/* 审核判定规则 */}
        <div style={styles.field}>
          <label style={styles.label}>
            审核判定规则 <span style={{ color: '#ff4d4f' }}>*</span>
            <span style={{ fontSize: '12px', color: '#999', marginLeft: '8px' }}>
              （必须包含 review_result 的判定逻辑）
            </span>
          </label>
          <textarea
            style={styles.textarea}
            rows={4}
            value={form.review_rules}
            onChange={(e) => handleChange('review_rules', e.target.value)}
            placeholder="定义 review_result 的判定规则，例如：如果 contains_child 为 true，则 review_result 为 fail..."
          />
          <div style={{ marginTop: '6px', display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
            <button type="button" onClick={fillExample} style={styles.smallBtn}>填入样例</button>
            <div style={styles.exampleBox}>
              <div style={{ fontSize: '12px', color: '#666', marginBottom: '4px' }}>样例规则：</div>
              <pre style={{ margin: 0, fontSize: '12px', color: '#333', whiteSpace: 'pre-wrap' }}>{REVIEW_RULES_EXAMPLE}</pre>
            </div>
          </div>
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
  exampleBox: {
    flex: 1, padding: '8px 12px', background: '#f6ffed', border: '1px solid #b7eb8f', borderRadius: '4px',
  },
  smallBtn: {
    background: '#fff', border: '1px solid #1677ff', borderRadius: '4px', color: '#1677ff',
    padding: '4px 10px', cursor: 'pointer', fontSize: '12px', whiteSpace: 'nowrap',
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
