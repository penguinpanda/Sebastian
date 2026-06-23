import React, { useEffect, useState } from 'react';
import { profileAPI } from '../services/api';
import { getFriendlyError } from '../services/error';

interface Props {
  userId: string;
}

interface ProfileData {
  user_id: string;
  age: number | null;
  gender: string | null;
  height_cm: number | null;
  weight_kg: number | null;
  activity_level: string | null;
  health_goal: string | null;
}

const emptyProfile: ProfileData = {
  user_id: '',
  age: null,
  gender: null,
  height_cm: null,
  weight_kg: null,
  activity_level: 'medium',
  health_goal: 'maintain',
};

export default function ProfileForm({ userId }: Props) {
  const [profile, setProfile] = useState<ProfileData>({ ...emptyProfile, user_id: userId });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');

  useEffect(() => {
    profileAPI.get(userId).then(res => {
      const data = res.data as any;
      if (data.user_id && data.age !== undefined) {
        setProfile({
          user_id: data.user_id,
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

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setMessage('');
    try {
      await profileAPI.save(profile);
      setMessage('✅ 健康档案已保存');
    } catch (err: unknown) {
      setMessage(`❌ ${getFriendlyError(err, '保存失败')}`);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <div className="card"><p className="text-gray-500">加载中...</p></div>;
  }

  return (
    <div className="card">
      <h2 className="text-xl font-bold mb-4">🩺 健康档案</h2>
      <p className="text-sm text-gray-500 mb-4">
        保存后，HealthAgent 将自动读取档案进行个性化分析，无需每次手动输入。
      </p>

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
    </div>
  );
}
