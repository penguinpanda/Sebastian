import React, { useState } from 'react';
import { mcpAPI } from '../services/api';
import { DEFAULT_HEALTH_FORM } from '../data/defaultTestData';
import { HealthAnalyzeResponse } from '../types';
import ErrorState from './common/ErrorState';
import { getFriendlyError } from '../services/error';

interface Props {
  userId: string;
}

export default function HealthAnalyzer({ userId }: Props) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [result, setResult] = useState<HealthAnalyzeResponse | null>(null);
  const [error, setError] = useState('');
  const [form, setForm] = useState(DEFAULT_HEALTH_FORM);

  const isBaseFormValid =
    Number.isFinite(form.height_cm) &&
    form.height_cm >= 50 &&
    form.height_cm <= 250 &&
    Number.isFinite(form.weight_kg) &&
    form.weight_kg >= 20 &&
    form.weight_kg <= 400;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setError('');

    if (!isBaseFormValid) {
      setError('请填写有效的身高和体重范围');
      setIsSubmitting(false);
      return;
    }

    try {
      const res = await mcpAPI.healthAnalyze({
        user_id: userId,
        input: {
          user_id: userId,
          ...form,
        },
      });
      setResult(res.data.result);
    } catch (err: unknown) {
      setError(getFriendlyError(err, '健康分析失败'));
    } finally {
      setIsSubmitting(false);
    }
  };

  const getBMIColor = (category: string) => {
    switch (category) {
      case 'underweight':
        return 'text-blue-600';
      case 'normal':
        return 'text-green-600';
      case 'overweight':
        return 'text-orange-600';
      case 'obese':
        return 'text-red-600';
      default:
        return 'text-gray-600';
    }
  };

  const getCategoryLabel = (category: string) => {
    const labels: Record<string, string> = {
      underweight: '体重过轻',
      normal: '正常体重',
      overweight: '超重',
      obese: '肥胖',
    };
    return labels[category] || category;
  };

  return (
    <div className="space-y-6">
      {/* 输入表单 */}
      <div className="card">
        <h2 className="text-xl font-bold mb-4">💪 健康分析</h2>
        {error && <ErrorState message={error} className="mb-4" />}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block font-medium mb-2">身高 (cm)</label>
              <input
                type="number"
                value={form.height_cm}
                onChange={(e) => {
                  const next = parseFloat(e.target.value);
                  setForm({ ...form, height_cm: Number.isFinite(next) ? next : 0 });
                }}
                className="input w-full"
                min={50}
                max={250}
              />
            </div>

            <div>
              <label className="block font-medium mb-2">体重 (kg)</label>
              <input
                type="number"
                value={form.weight_kg}
                onChange={(e) => {
                  const next = parseFloat(e.target.value);
                  setForm({ ...form, weight_kg: Number.isFinite(next) ? next : 0 });
                }}
                className="input w-full"
                min={20}
                max={400}
              />
            </div>

            <div>
              <label className="block font-medium mb-2">目标体重 (kg) - 可选</label>
              <input
                type="number"
                value={form.target_weight_kg}
                onChange={(e) => {
                  const next = parseFloat(e.target.value);
                  setForm({ ...form, target_weight_kg: Number.isFinite(next) ? next : 0 });
                }}
                className="input w-full"
                min={20}
                max={400}
              />
            </div>

            <div>
              <label className="block font-medium mb-2">今日摄入热量 (kcal) - 可选</label>
              <input
                type="number"
                value={form.daily_calories_taken}
                onChange={(e) => {
                  const next = parseInt(e.target.value, 10);
                  setForm({ ...form, daily_calories_taken: Number.isFinite(next) ? next : 0 });
                }}
                className="input w-full"
                min={0}
                max={10000}
              />
            </div>
          </div>

          <button type="submit" className="btn btn-primary w-full" disabled={isSubmitting || !isBaseFormValid}>
            {isSubmitting ? '分析中...' : '开始分析'}
          </button>
        </form>
      </div>

      {/* 分析结果 */}
      {result && (
        <div className="space-y-4">
          <div className={`card border-2 border-current ${getBMIColor(result.bmi_category)}`}>
            <h2 className="text-2xl font-bold mb-4">📊 分析结果</h2>

            <div className="grid grid-cols-2 gap-4">
              <div className="bg-white p-4 rounded">
                <p className="text-gray-600 mb-2">BMI 指数</p>
                <p className={`text-3xl font-bold ${getBMIColor(result.bmi_category)}`}>
                  {result.bmi}
                </p>
              </div>

              <div className="bg-white p-4 rounded">
                <p className="text-gray-600 mb-2">体重分类</p>
                <p className={`text-xl font-bold ${getBMIColor(result.bmi_category)}`}>
                  {getCategoryLabel(result.bmi_category)}
                </p>
              </div>

              <div className="bg-white p-4 rounded">
                <p className="text-gray-600 mb-2">每日推荐热量</p>
                <p className="text-3xl font-bold text-blue-600">
                  {result.suggested_daily_calories} kcal
                </p>
              </div>

              {form.daily_calories_taken > 0 && (
                <div className="bg-white p-4 rounded">
                  <p className="text-gray-600 mb-2">今日摄入</p>
                  <p className="text-3xl font-bold text-purple-600">
                    {form.daily_calories_taken} kcal
                  </p>
                  <p className="text-sm text-gray-500 mt-2">
                    {form.daily_calories_taken > result.suggested_daily_calories ? '已超' : '还需'}
                    {Math.abs(
                      form.daily_calories_taken - result.suggested_daily_calories
                    )} kcal
                  </p>
                </div>
              )}
            </div>
          </div>

          <div className="card bg-blue-50">
            <h3 className="font-semibold text-lg mb-2">💡 健康建议</h3>
            <p className="text-gray-700 whitespace-pre-line">{result.advice}</p>
            {result._audit?.trace_id && (
              <p className="text-xs text-gray-500 mt-3">
                trace_id: <span className="font-mono">{result._audit.trace_id}</span>
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
