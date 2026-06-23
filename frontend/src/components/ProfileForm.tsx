import React, { useEffect, useState } from 'react';
import { profileAPI, mcpAPI } from '../services/api';
import { getFriendlyError } from '../services/error';
import { HealthAnalyzeResponse } from '../types';

interface Props {
  userId: string;
}

interface PreferencesData {
  dietary: string[];
  lifestyle: string[];
  cuisine: string[];
  free_text: string;
}

interface ProfileData {
  user_id: string;
  classification: string | null;
  preferences: PreferencesData | null;
  age: number | null;
  gender: string | null;
  height_cm: number | null;
  weight_kg: number | null;
  activity_level: string | null;
  health_goal: string | null;
}

const emptyPreferences: PreferencesData = {
  dietary: [],
  lifestyle: [],
  cuisine: [],
  free_text: '',
};

const emptyProfile: ProfileData = {
  user_id: '',
  classification: null,
  preferences: emptyPreferences,
  age: null,
  gender: null,
  height_cm: null,
  weight_kg: null,
  activity_level: 'medium',
  health_goal: 'maintain',
};

// 预设标签选项
const DIETARY_OPTIONS = ['辣', '清淡', '低碳水', '高蛋白', '素食', '海鲜', '甜食', '无特殊'];
const LIFESTYLE_OPTIONS = ['早起', '熬夜', '经常运动', '久坐', '时间紧张', '周末做饭'];
const CUISINE_OPTIONS = ['川菜', '粤菜', '日料', '西餐', '韩餐', '东南亚', '家常菜', '面食'];

function TagSelector({ label, options, selected, onChange }: {
  label: string;
  options: string[];
  selected: string[];
  onChange: (tags: string[]) => void;
}) {
  const toggle = (tag: string) => {
    if (selected.includes(tag)) {
      onChange(selected.filter(t => t !== tag));
    } else {
      onChange([...selected, tag]);
    }
  };

  return (
    <div>
      <label className="block font-medium mb-1">{label}</label>
      <div className="flex flex-wrap gap-2">
        {options.map(opt => (
          <button
            key={opt}
            type="button"
            onClick={() => toggle(opt)}
            className={`px-3 py-1 rounded-full text-sm border transition-colors ${
              selected.includes(opt)
                ? 'bg-indigo-600 text-white border-indigo-600'
                : 'bg-white text-gray-600 border-gray-300 hover:border-indigo-400'
            }`}
          >
            {opt}
          </button>
        ))}
      </div>
    </div>
  );
}

export default function ProfileForm({ userId }: Props) {
  const [profile, setProfile] = useState<ProfileData>({ ...emptyProfile, user_id: userId });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');

  // 健康分析状态
  const [healthResult, setHealthResult] = useState<HealthAnalyzeResponse | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analyzeError, setAnalyzeError] = useState('');

  useEffect(() => {
    profileAPI.get(userId).then(res => {
      const data = res.data as any;
      if (data.user_id && data.age !== undefined) {
        setProfile({
          user_id: data.user_id,
          classification: data.classification ?? null,
          preferences: data.preferences ?? { ...emptyPreferences },
          age: data.age ?? null,
          gender: data.gender ?? null,
          height_cm: data.height_cm ?? null,
          weight_kg: data.weight_kg ?? null,
          activity_level: data.activity_level ?? 'medium',
          health_goal: data.health_goal ?? 'maintain',
        });
      }
    }).catch(() => {}).finally(() => setLoading(false));
  }, [userId]);

  const updatePreferences = (field: keyof PreferencesData, value: string[] | string) => {
    setProfile(prev => ({
      ...prev,
      preferences: {
        dietary: prev.preferences?.dietary ?? [],
        lifestyle: prev.preferences?.lifestyle ?? [],
        cuisine: prev.preferences?.cuisine ?? [],
        free_text: prev.preferences?.free_text ?? '',
        ...prev.preferences,
        [field]: value,
      },
    }));
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setMessage('');
    try {
      await profileAPI.save(profile);
      setMessage('✅ 档案已保存');
    } catch (err: unknown) {
      setMessage(`❌ ${getFriendlyError(err, '保存失败')}`);
    } finally {
      setSaving(false);
    }
  };

  // 健康分析
  const handleHealthAnalyze = async () => {
    if (!profile.height_cm || !profile.weight_kg) {
      setAnalyzeError('请先在健康档案中填写身高和体重');
      return;
    }
    setIsAnalyzing(true);
    setAnalyzeError('');
    setHealthResult(null);
    try {
      const res = await mcpAPI.healthAnalyze({
        user_id: userId,
        input: {
          user_id: userId,
          height_cm: profile.height_cm,
          weight_kg: profile.weight_kg,
        },
      });
      setHealthResult(res.data.result);
    } catch (err: unknown) {
      setAnalyzeError(getFriendlyError(err, '健康分析失败'));
    } finally {
      setIsAnalyzing(false);
    }
  };

  const getBMIColor = (category: string) => {
    switch (category) {
      case 'underweight': return 'text-blue-600';
      case 'normal': return 'text-green-600';
      case 'overweight': return 'text-orange-600';
      case 'obese': return 'text-red-600';
      default: return 'text-gray-600';
    }
  };

  const getCategoryLabel = (category: string) => {
    const labels: Record<string, string> = {
      underweight: '体重过轻', normal: '正常体重', overweight: '超重', obese: '肥胖',
    };
    return labels[category] || category;
  };

  if (loading) {
    return <div className="card"><p className="text-gray-500">加载中...</p></div>;
  }

  return (
    <div className="card space-y-6">
      <div>
        <h2 className="text-xl font-bold mb-1">👤 注册信息</h2>
        <p className="text-sm text-gray-500 mb-4">
          设置你的用户分类和个人偏好，Agent 将据此提供个性化建议。
        </p>

        {/* 用户分类 */}
        <div className="mb-6">
          <label className="block font-medium mb-2">用户分类</label>
          <div className="grid grid-cols-2 gap-3">
            <button
              type="button"
              onClick={() => setProfile({ ...profile, classification: 'single_male' })}
              className={`p-4 rounded-xl border-2 text-center transition-all ${
                profile.classification === 'single_male'
                  ? 'border-indigo-600 bg-indigo-50 shadow-sm'
                  : 'border-gray-200 hover:border-indigo-300 bg-white'
              }`}
            >
              <span className="text-2xl">🧑</span>
              <p className="font-semibold mt-1">单身男性</p>
            </button>
            <button
              type="button"
              onClick={() => setProfile({ ...profile, classification: 'single_female' })}
              className={`p-4 rounded-xl border-2 text-center transition-all ${
                profile.classification === 'single_female'
                  ? 'border-pink-500 bg-pink-50 shadow-sm'
                  : 'border-gray-200 hover:border-pink-300 bg-white'
              }`}
            >
              <span className="text-2xl">👩</span>
              <p className="font-semibold mt-1">单身女性</p>
            </button>
          </div>
        </div>

        {/* 个人偏好 */}
        <div className="mb-6 p-4 bg-gray-50 rounded-xl space-y-4">
          <h3 className="font-semibold text-lg">🎯 个人偏好</h3>

          <TagSelector
            label="饮食偏好"
            options={DIETARY_OPTIONS}
            selected={profile.preferences?.dietary ?? []}
            onChange={tags => updatePreferences('dietary', tags)}
          />
          <TagSelector
            label="生活方式"
            options={LIFESTYLE_OPTIONS}
            selected={profile.preferences?.lifestyle ?? []}
            onChange={tags => updatePreferences('lifestyle', tags)}
          />
          <TagSelector
            label="偏好菜系"
            options={CUISINE_OPTIONS}
            selected={profile.preferences?.cuisine ?? []}
            onChange={tags => updatePreferences('cuisine', tags)}
          />

          <div>
            <label className="block font-medium mb-1">补充说明</label>
            <textarea
              value={profile.preferences?.free_text ?? ''}
              onChange={e => updatePreferences('free_text', e.target.value)}
              className="input w-full min-h-[60px]"
              placeholder="其他偏好，如过敏食材、忌口等…"
              maxLength={2000}
              rows={2}
            />
          </div>
        </div>
      </div>

      <hr className="border-gray-200" />

      <div>
        <h2 className="text-xl font-bold mb-4">🩺 健康档案</h2>
        <p className="text-sm text-gray-500 mb-4">
          保存后，HealthAgent 将自动读取档案进行个性化分析，无需每次手动输入。
        </p>
      </div>

      {message && (
        <p className={`mb-4 text-sm ${message.startsWith('✅') ? 'text-green-700' : 'text-red-600'}`}>
          {message}
        </p>
      )}

      <form onSubmit={handleSave} className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block font-medium mb-1">年龄</label>
            <input
              type="number"
              value={profile.age ?? ''}
              onChange={e => setProfile({ ...profile, age: e.target.value ? parseInt(e.target.value) : null })}
              className="input w-full"
              min={1}
              max={120}
              placeholder="25"
            />
          </div>
          <div>
            <label className="block font-medium mb-1">性别</label>
            <select
              value={profile.gender ?? ''}
              onChange={e => setProfile({ ...profile, gender: e.target.value || null })}
              className="input w-full"
            >
              <option value="">请选择</option>
              <option value="male">男</option>
              <option value="female">女</option>
              <option value="other">其他</option>
            </select>
          </div>
          <div>
            <label className="block font-medium mb-1">身高 (cm)</label>
            <input
              type="number"
              value={profile.height_cm ?? ''}
              onChange={e => setProfile({ ...profile, height_cm: e.target.value ? parseFloat(e.target.value) : null })}
              className="input w-full"
              min={50}
              max={250}
              placeholder="175"
            />
          </div>
          <div>
            <label className="block font-medium mb-1">体重 (kg)</label>
            <input
              type="number"
              value={profile.weight_kg ?? ''}
              onChange={e => setProfile({ ...profile, weight_kg: e.target.value ? parseFloat(e.target.value) : null })}
              className="input w-full"
              min={20}
              max={400}
              placeholder="70"
            />
          </div>
          <div>
            <label className="block font-medium mb-1">活动水平</label>
            <select
              value={profile.activity_level ?? 'medium'}
              onChange={e => setProfile({ ...profile, activity_level: e.target.value })}
              className="input w-full"
            >
              <option value="low">低（久坐）</option>
              <option value="medium">中（日常活动）</option>
              <option value="high">高（经常运动）</option>
            </select>
          </div>
          <div>
            <label className="block font-medium mb-1">健康目标</label>
            <select
              value={profile.health_goal ?? 'maintain'}
              onChange={e => setProfile({ ...profile, health_goal: e.target.value })}
              className="input w-full"
            >
              <option value="lose_weight">减重</option>
              <option value="maintain">维持</option>
              <option value="gain_muscle">增肌</option>
            </select>
          </div>
        </div>

        <button type="submit" className="btn btn-primary w-full" disabled={saving}>
          {saving ? '保存中...' : '保存档案'}
        </button>
      </form>

      {/* 健康分析 */}
      <hr className="border-gray-200" />

      <div>
        <h2 className="text-xl font-bold mb-1">💪 健康分析</h2>
        <p className="text-sm text-gray-500 mb-4">
          基于档案中的身高体重数据，调用 AI 进行 BMI 计算和个性化健康建议。
        </p>

        {analyzeError && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg">
            <p className="text-red-600 text-sm">{analyzeError}</p>
          </div>
        )}

        <button
          type="button"
          onClick={handleHealthAnalyze}
          disabled={isAnalyzing || !profile.height_cm || !profile.weight_kg}
          className="btn btn-primary w-full mb-4"
        >
          {isAnalyzing ? '分析中...' : '🔍 开始健康分析'}
        </button>

        {!profile.height_cm && !profile.weight_kg && (
          <p className="text-sm text-gray-400 text-center">请先在上方填写身高和体重</p>
        )}

        {/* 分析结果 */}
        {healthResult && (
          <div className="space-y-4">
            <div className={`p-4 rounded-xl border-2 ${getBMIColor(healthResult.bmi_category)} bg-white`}>
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-gray-50 p-3 rounded-lg">
                  <p className="text-gray-500 text-sm mb-1">BMI 指数</p>
                  <p className={`text-2xl font-bold ${getBMIColor(healthResult.bmi_category)}`}>
                    {healthResult.bmi}
                  </p>
                </div>
                <div className="bg-gray-50 p-3 rounded-lg">
                  <p className="text-gray-500 text-sm mb-1">体重分类</p>
                  <p className={`text-xl font-bold ${getBMIColor(healthResult.bmi_category)}`}>
                    {getCategoryLabel(healthResult.bmi_category)}
                  </p>
                </div>
                <div className="bg-gray-50 p-3 rounded-lg col-span-2">
                  <p className="text-gray-500 text-sm mb-1">每日推荐热量</p>
                  <p className="text-2xl font-bold text-indigo-600">
                    {healthResult.suggested_daily_calories} kcal
                  </p>
                </div>
              </div>
            </div>

            <div className="p-4 bg-blue-50 rounded-xl">
              <h3 className="font-semibold text-lg mb-2">💡 AI 健康建议</h3>
              <p className="text-gray-700 whitespace-pre-line">{healthResult.advice}</p>
              {healthResult._audit?.trace_id && (
                <p className="text-xs text-gray-400 mt-3">
                  trace: <span className="font-mono">{healthResult._audit.trace_id}</span>
                </p>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
