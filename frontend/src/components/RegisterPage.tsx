import React, { useState } from 'react';
import { profileAPI } from '../services/api';
import { getFriendlyError } from '../services/error';
import { RegisterFormData, RegisterPreferencesData } from '../types';
import { DEFAULT_REGISTER_FORM } from '../data/defaultTestData';

// ========== Props ==========

interface Props {
  onRegisterComplete: (userId: string) => void;
}

// ========== 预设标签选项 ==========

const DIETARY_OPTIONS = ['辣', '清淡', '低碳水', '高蛋白', '素食', '海鲜', '甜食', '无特殊'];
const LIFESTYLE_OPTIONS = ['早起', '熬夜', '经常运动', '久坐', '时间紧张', '周末做饭'];
const CUISINE_OPTIONS = ['川菜', '粤菜', '日料', '西餐', '韩餐', '东南亚', '家常菜', '面食'];

// ========== 子组件：标签选择器 ==========

function TagSelector({
  label,
  options,
  selected,
  onChange,
}: {
  label: string;
  options: string[];
  selected: string[];
  onChange: (tags: string[]) => void;
}) {
  const toggle = (tag: string) => {
    if (selected.includes(tag)) {
      onChange(selected.filter((t) => t !== tag));
    } else {
      onChange([...selected, tag]);
    }
  };

  return (
    <div>
      <label className="block font-medium mb-1 text-gray-700">{label}</label>
      <div className="flex flex-wrap gap-2">
        {options.map((opt) => (
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

// ========== 步骤指示器 ==========

function StepIndicator({ currentStep }: { currentStep: number }) {
  const labels = ['账户信息', '居住情况', '个人偏好', '健康档案'];
  return (
    <div className="flex items-center justify-center mb-8">
      {labels.map((label, i) => (
        <React.Fragment key={i}>
          <div className="flex items-center">
            <div
              className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold transition-colors ${
                i <= currentStep
                  ? 'bg-indigo-600 text-white'
                  : 'bg-gray-200 text-gray-500'
              }`}
            >
              {i < currentStep ? '✓' : i + 1}
            </div>
            <span
              className={`ml-2 text-sm font-medium hidden sm:inline ${
                i <= currentStep ? 'text-indigo-600' : 'text-gray-400'
              }`}
            >
              {label}
            </span>
          </div>
          {i < labels.length - 1 && (
            <div
              className={`w-8 sm:w-12 h-0.5 mx-2 transition-colors ${
                i < currentStep ? 'bg-indigo-600' : 'bg-gray-200'
              }`}
            />
          )}
        </React.Fragment>
      ))}
    </div>
  );
}

// ========== 步骤 1：账户信息 ==========

function StepAccount({
  form,
  updateField,
  errors,
}: {
  form: RegisterFormData;
  updateField: (field: string, value: string) => void;
  errors: Record<string, string>;
}) {
  return (
    <div className="space-y-4">
      <h2 className="text-xl font-bold text-gray-800">📧 创建账户</h2>
      <p className="text-sm text-gray-500">请输入邮箱和密码注册（测试环境已预填默认值）</p>

      <div>
        <label className="block font-medium mb-1 text-gray-700">邮箱地址</label>
        <input
          type="email"
          value={form.email}
          onChange={(e) => updateField('email', e.target.value)}
          className={`input w-full ${errors.email ? 'border-red-400 ring-2 ring-red-200' : ''}`}
          placeholder="请输入邮箱"
          autoComplete="email"
        />
        {errors.email && <p className="text-red-500 text-sm mt-1">{errors.email}</p>}
      </div>

      <div>
        <label className="block font-medium mb-1 text-gray-700">密码</label>
        <input
          type="password"
          value={form.password}
          onChange={(e) => updateField('password', e.target.value)}
          className={`input w-full ${errors.password ? 'border-red-400 ring-2 ring-red-200' : ''}`}
          placeholder="请输入密码（至少6位）"
          autoComplete="new-password"
        />
        {errors.password && <p className="text-red-500 text-sm mt-1">{errors.password}</p>}
      </div>

      <div>
        <label className="block font-medium mb-1 text-gray-700">确认密码</label>
        <input
          type="password"
          value={form.confirmPassword}
          onChange={(e) => updateField('confirmPassword', e.target.value)}
          className={`input w-full ${errors.confirmPassword ? 'border-red-400 ring-2 ring-red-200' : ''}`}
          placeholder="请再次输入密码"
          autoComplete="new-password"
        />
        {errors.confirmPassword && (
          <p className="text-red-500 text-sm mt-1">{errors.confirmPassword}</p>
        )}
      </div>
    </div>
  );
}

// ========== 步骤 2：居住情况（仅单身可选） ==========

function StepClassification({
  classification,
  onChange,
  error,
}: {
  classification: string;
  onChange: (value: 'single_male' | 'single_female') => void;
  error: string;
}) {
  return (
    <div className="space-y-4">
      <h2 className="text-xl font-bold text-gray-800">🏠 居住情况</h2>
      <p className="text-sm text-gray-500">请选择你的居住类型，系统将据此提供个性化推荐</p>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-4">
        {/* 单身男性 */}
        <button
          type="button"
          onClick={() => onChange('single_male')}
          className={`p-6 rounded-xl border-2 text-center transition-all ${
            classification === 'single_male'
              ? 'border-indigo-600 bg-indigo-50 shadow-md scale-105'
              : 'border-gray-200 hover:border-indigo-300 bg-white'
          }`}
        >
          <span className="text-3xl">🧑</span>
          <p className="font-semibold mt-2 text-lg">单身男性</p>
          <p className="text-xs text-gray-400 mt-1">一人食 · 独立烹饪</p>
        </button>

        {/* 单身女性 */}
        <button
          type="button"
          onClick={() => onChange('single_female')}
          className={`p-6 rounded-xl border-2 text-center transition-all ${
            classification === 'single_female'
              ? 'border-pink-500 bg-pink-50 shadow-md scale-105'
              : 'border-gray-200 hover:border-pink-300 bg-white'
          }`}
        >
          <span className="text-3xl">👩</span>
          <p className="font-semibold mt-2 text-lg">单身女性</p>
          <p className="text-xs text-gray-400 mt-1">一人食 · 独立烹饪</p>
        </button>

        {/* 多人家庭 — 禁用 */}
        <button
          type="button"
          disabled
          className="p-6 rounded-xl border-2 border-gray-200 bg-gray-100 text-center opacity-50 cursor-not-allowed"
          title="即将推出"
        >
          <span className="text-3xl">👨‍👩‍👧</span>
          <p className="font-semibold mt-2 text-lg text-gray-400">多人家庭</p>
          <p className="text-xs text-gray-400 mt-1">🚧 即将推出</p>
        </button>
      </div>

      {error && <p className="text-red-500 text-sm">{error}</p>}
    </div>
  );
}

// ========== 步骤 3：个人偏好 ==========

function StepPreferences({
  preferences,
  updatePreferences,
}: {
  preferences: RegisterPreferencesData;
  updatePreferences: (field: keyof RegisterPreferencesData, value: string[] | string) => void;
}) {
  return (
    <div className="space-y-4">
      <h2 className="text-xl font-bold text-gray-800">🎯 个人偏好</h2>
      <p className="text-sm text-gray-500">
        选择你的口味和生活习惯，AI 将据此推荐最适合你的菜谱
      </p>

      <div className="p-4 bg-gray-50 rounded-xl space-y-4">
        <TagSelector
          label="饮食偏好"
          options={DIETARY_OPTIONS}
          selected={preferences.dietary}
          onChange={(tags) => updatePreferences('dietary', tags)}
        />
        <TagSelector
          label="生活方式"
          options={LIFESTYLE_OPTIONS}
          selected={preferences.lifestyle}
          onChange={(tags) => updatePreferences('lifestyle', tags)}
        />
        <TagSelector
          label="偏好菜系"
          options={CUISINE_OPTIONS}
          selected={preferences.cuisine}
          onChange={(tags) => updatePreferences('cuisine', tags)}
        />

        <div>
          <label className="block font-medium mb-1 text-gray-700">补充说明</label>
          <textarea
            value={preferences.free_text}
            onChange={(e) => updatePreferences('free_text', e.target.value)}
            className="input w-full min-h-[60px]"
            placeholder="其他偏好，如过敏食材、忌口等…（可选）"
            maxLength={2000}
            rows={2}
          />
        </div>
      </div>
    </div>
  );
}

// ========== 步骤 4：健康档案 ==========

function StepHealth({
  form,
  updateField,
}: {
  form: RegisterFormData;
  updateField: (field: string, value: string | number | null) => void;
}) {
  return (
    <div className="space-y-4">
      <h2 className="text-xl font-bold text-gray-800">🩺 健康档案</h2>
      <p className="text-sm text-gray-500">这些信息将用于 BMI 计算和个性化饮食建议</p>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block font-medium mb-1 text-gray-700">年龄</label>
          <input
            type="number"
            value={form.age ?? ''}
            onChange={(e) =>
              updateField('age', e.target.value ? parseInt(e.target.value) : null)
            }
            className="input w-full"
            min={1}
            max={120}
            placeholder="25"
          />
        </div>
        <div>
          <label className="block font-medium mb-1 text-gray-700">性别</label>
          <select
            value={form.gender}
            onChange={(e) => updateField('gender', e.target.value)}
            className="input w-full"
          >
            <option value="">请选择</option>
            <option value="male">男</option>
            <option value="female">女</option>
            <option value="other">其他</option>
          </select>
        </div>
        <div>
          <label className="block font-medium mb-1 text-gray-700">身高 (cm)</label>
          <input
            type="number"
            value={form.height_cm ?? ''}
            onChange={(e) =>
              updateField('height_cm', e.target.value ? parseFloat(e.target.value) : null)
            }
            className="input w-full"
            min={50}
            max={250}
            placeholder="175"
          />
        </div>
        <div>
          <label className="block font-medium mb-1 text-gray-700">体重 (kg)</label>
          <input
            type="number"
            value={form.weight_kg ?? ''}
            onChange={(e) =>
              updateField('weight_kg', e.target.value ? parseFloat(e.target.value) : null)
            }
            className="input w-full"
            min={20}
            max={400}
            placeholder="70"
          />
        </div>
        <div>
          <label className="block font-medium mb-1 text-gray-700">活动水平</label>
          <select
            value={form.activity_level}
            onChange={(e) => updateField('activity_level', e.target.value)}
            className="input w-full"
          >
            <option value="low">低（久坐）</option>
            <option value="medium">中（日常活动）</option>
            <option value="high">高（经常运动）</option>
          </select>
        </div>
        <div>
          <label className="block font-medium mb-1 text-gray-700">健康目标</label>
          <select
            value={form.health_goal}
            onChange={(e) => updateField('health_goal', e.target.value)}
            className="input w-full"
          >
            <option value="lose_weight">减重</option>
            <option value="maintain">维持</option>
            <option value="gain_muscle">增肌</option>
          </select>
        </div>
      </div>
    </div>
  );
}

// ========== 主组件 ==========

const TOTAL_STEPS = 4;

export default function RegisterPage({ onRegisterComplete }: Props) {
  const [currentStep, setCurrentStep] = useState(0);
  const [form, setForm] = useState<RegisterFormData>({ ...DEFAULT_REGISTER_FORM });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState('');

  // 通用字段更新
  const updateField = (field: string, value: unknown) => {
    setForm((prev) => ({ ...prev, [field]: value }));
    // 清除对应字段错误
    if (errors[field]) {
      setErrors((prev) => {
        const next = { ...prev };
        delete next[field];
        return next;
      });
    }
  };

  // 偏好更新
  const updatePreferences = (field: keyof RegisterPreferencesData, value: string[] | string) => {
    setForm((prev) => ({
      ...prev,
      preferences: { ...prev.preferences, [field]: value },
    }));
  };

  // ========== 步骤校验 ==========

  const validateStep = (step: number): boolean => {
    const newErrors: Record<string, string> = {};

    switch (step) {
      case 0: {
        const emailRe = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!form.email.trim()) {
          newErrors.email = '请输入邮箱地址';
        } else if (!emailRe.test(form.email.trim())) {
          newErrors.email = '邮箱格式不正确';
        }
        if (!form.password) {
          newErrors.password = '请输入密码';
        } else if (form.password.length < 6) {
          newErrors.password = '密码至少需要6位';
        }
        if (form.password !== form.confirmPassword) {
          newErrors.confirmPassword = '两次输入的密码不一致';
        }
        break;
      }
      case 1: {
        if (!form.classification) {
          // 使用通用错误展示
          break;
        }
        break;
      }
      default:
        break;
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  // ========== 导航 ==========

  const goNext = () => {
    if (validateStep(currentStep)) {
      setCurrentStep((s) => Math.min(s + 1, TOTAL_STEPS - 1));
    }
  };

  const goPrev = () => {
    setCurrentStep((s) => Math.max(s - 1, 0));
  };

  // ========== 提交注册 ==========

  const handleSubmit = async () => {
    if (!form.classification) {
      setErrors({ classification: '请选择单身男性或单身女性' });
      return;
    }

    setIsSubmitting(true);
    setSubmitError('');

    try {
      const userId = form.email.trim();

      // 调用后端 profile API（upsert 语义）
      await profileAPI.save({
        user_id: userId,
        classification: form.classification,
        preferences: {
          dietary: form.preferences.dietary,
          lifestyle: form.preferences.lifestyle,
          cuisine: form.preferences.cuisine,
          free_text: form.preferences.free_text,
        },
        age: form.age,
        gender: form.gender || null,
        height_cm: form.height_cm,
        weight_kg: form.weight_kg,
        activity_level: form.activity_level,
        health_goal: form.health_goal,
      });

      onRegisterComplete(userId);
    } catch (err: unknown) {
      setSubmitError(getFriendlyError(err, '注册失败，请稍后重试'));
    } finally {
      setIsSubmitting(false);
    }
  };

  // ========== 当前步骤内容 ==========

  const renderStep = () => {
    switch (currentStep) {
      case 0:
        return <StepAccount form={form} updateField={updateField} errors={errors} />;
      case 1:
        return (
          <StepClassification
            classification={form.classification}
            onChange={(value) => {
              updateField('classification', value);
              setErrors({});
            }}
            error={errors.classification || ''}
          />
        );
      case 2:
        return (
          <StepPreferences
            preferences={form.preferences}
            updatePreferences={updatePreferences}
          />
        );
      case 3:
        return <StepHealth form={form} updateField={updateField} />;
      default:
        return null;
    }
  };

  // ========== 渲染 ==========

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center px-4 py-8">
      <div className="w-full max-w-lg">
        {/* Logo 区域 */}
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-800">🤖 Sebastian</h1>
          <p className="text-gray-500 mt-2">个人生活与厨房 AI 助手</p>
        </div>

        {/* 注册卡片 */}
        <div className="card">
          <StepIndicator currentStep={currentStep} />

          {renderStep()}

          {/* 步骤 2 特殊错误（未选择分类） */}
          {currentStep === 1 && errors.classification && (
            <p className="text-red-500 text-sm mt-3">{errors.classification}</p>
          )}

          {/* 提交错误 */}
          {submitError && (
            <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg">
              <p className="text-red-600 text-sm">{submitError}</p>
            </div>
          )}

          {/* 导航按钮 */}
          <div className="mt-8 flex justify-between">
            <button
              type="button"
              onClick={goPrev}
              disabled={currentStep === 0}
              className="btn btn-secondary"
            >
              ← 上一步
            </button>

            {currentStep < TOTAL_STEPS - 1 ? (
              <button type="button" onClick={goNext} className="btn btn-primary">
                下一步 →
              </button>
            ) : (
              <button
                type="button"
                onClick={handleSubmit}
                disabled={isSubmitting}
                className="btn btn-primary"
              >
                {isSubmitting ? '注册中...' : '✅ 完成注册'}
              </button>
            )}
          </div>
        </div>

        {/* 提示 */}
        <p className="text-center text-gray-400 text-sm mt-6">
          测试环境：邮箱即为用户 ID，密码暂不校验
        </p>
      </div>
    </div>
  );
}
