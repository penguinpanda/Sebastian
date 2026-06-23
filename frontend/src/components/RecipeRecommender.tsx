import React, { useState } from 'react';
import { mcpAPI, mealAPI } from '../services/api';
import { DEFAULT_RECIPE_FORM } from '../data/defaultTestData';
import { RecipeRecommendResponse, RecipeIngredient } from '../types';
import ErrorState from './common/ErrorState';
import { getFriendlyError } from '../services/error';

interface Props {
  userId: string;
}

export default function RecipeRecommender({ userId }: Props) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [result, setResult] = useState<RecipeRecommendResponse | null>(null);
  const [error, setError] = useState('');
  const [form, setForm] = useState(DEFAULT_RECIPE_FORM);
  const [confirming, setConfirming] = useState(false);
  const [confirmResult, setConfirmResult] = useState('');
  const [confirmed, setConfirmed] = useState(false);

  // 食材可编辑副本
  const [editedIngredients, setEditedIngredients] = useState<RecipeIngredient[] | null>(null);
  const effectiveIngredients = editedIngredients ?? result?.ingredients ?? [];

  const adjustIngredient = (index: number, delta: number) => {
    const base = effectiveIngredients;
    if (index < 0 || index >= base.length) return;
    const next = [...base];
    const newAmount = Math.max(1, (next[index].amount || 0) + delta);
    next[index] = { ...next[index], amount: newAmount };
    setEditedIngredients(next);
  };

  const setIngredientAmount = (index: number, amount: number) => {
    const base = effectiveIngredients;
    if (index < 0 || index >= base.length) return;
    const next = [...base];
    next[index] = { ...next[index], amount: Math.max(1, amount || 1) };
    setEditedIngredients(next);
  };

  const equipment = ['pan', 'pot', 'oven', 'microwave', 'rice_cooker', 'blender'];
  const preferences = ['high-protein', 'low-fat', 'vegetarian', 'low-carb'];
  const isCaloriesValid = Number.isFinite(form.target_calories) && form.target_calories >= 200 && form.target_calories <= 2000;
  const isSubmitDisabled = isSubmitting || !isCaloriesValid;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setError('');
    setConfirmResult('');
    setConfirmed(false);

    if (!isCaloriesValid) {
      setError('目标热量必须在 200-2000 之间');
      setIsSubmitting(false);
      return;
    }

    try {
      const res = await mcpAPI.recipeRecommend({
        user_id: userId,
        input: {
          user_id: userId,
          ...form,
        },
      });
      setResult(res.data.result);
      setEditedIngredients(null);
    } catch (err: unknown) {
      setError(getFriendlyError(err, '菜谱推荐失败'));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleConfirmMeal = async () => {
    if (!result || confirming) return;
    setConfirming(true);
    setConfirmResult('');
    try {
      // 使用编辑后的食材
      const payload = editedIngredients
        ? { ...result, ingredients: editedIngredients }
        : result;
      const res = await mealAPI.confirm(payload, userId);
      const data = res.data as any;
      const deductedNames = (data.deducted || []).map((d: any) => `${d.name} ${d.amount}${d.unit}`).join('、');
      const missingNames = (data.missing || []).map((m: any) => `${m.name} ${m.amount}${m.unit}`).join('、');
      let msg = `✅ 已确认制作！`;
      if (deductedNames) msg += ` 已从库存扣除：${deductedNames}。`;
      if (missingNames) msg += ` ⚠️ 库存不足：${missingNames}。`;
      setConfirmResult(msg);
      setConfirmed(true);
    } catch (err: unknown) {
      setConfirmResult(`❌ ${getFriendlyError(err, '确认制作失败')}`);
    } finally {
      setConfirming(false);
    }
  };

  const toggleArrayField = (field: 'available_equipment' | 'dietary_preferences', value: string) => {
    setForm((prev) => ({
      ...prev,
      [field]: prev[field].includes(value)
        ? prev[field].filter((v) => v !== value)
        : [...prev[field], value],
    }));
  };

  return (
    <div className="space-y-6">
      {/* 输入表单 */}
      <div className="card">
        <h2 className="text-xl font-bold mb-4">🍽️ 菜谱推荐</h2>
        {error && <ErrorState message={error} className="mb-4" />}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block font-medium mb-2">用餐类型</label>
              <select
                value={form.meal_type}
                onChange={(e) => setForm({ ...form, meal_type: e.target.value as any })}
                className="input w-full"
              >
                <option value="breakfast">早餐</option>
                <option value="lunch">午餐</option>
                <option value="dinner">晚餐</option>
                <option value="snack">零食</option>
              </select>
            </div>

            <div>
              <label className="block font-medium mb-2">目标热量 (kcal)</label>
              <input
                type="number"
                value={form.target_calories}
                onChange={(e) => {
                  const next = parseInt(e.target.value, 10);
                  setForm({ ...form, target_calories: Number.isFinite(next) ? next : 0 });
                }}
                className="input w-full"
                min={200}
                max={2000}
              />
            </div>
          </div>

          <div>
            <label className="block font-medium mb-2">🔪 可用厨具</label>
            <div className="flex flex-wrap gap-2">
              {equipment.map((e) => (
                <button
                  key={e}
                  type="button"
                  onClick={() => toggleArrayField('available_equipment', e)}
                  className={`px-3 py-1 rounded text-sm transition-colors ${
                    form.available_equipment.includes(e)
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                  }`}
                >
                  {e}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block font-medium mb-2">🥗 饮食偏好</label>
            <div className="flex flex-wrap gap-2">
              {preferences.map((p) => (
                <button
                  key={p}
                  type="button"
                  onClick={() => toggleArrayField('dietary_preferences', p)}
                  className={`px-3 py-1 rounded text-sm transition-colors ${
                    form.dietary_preferences.includes(p)
                      ? 'bg-green-600 text-white'
                      : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                  }`}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>

          <button type="submit" className="btn btn-primary w-full" disabled={isSubmitDisabled}>
            {isSubmitting ? '推荐中...' : '获取推荐'}
          </button>
        </form>
      </div>

      {/* 推荐结果 */}
      {result && (
        <div className="card bg-green-50 border-2 border-green-200">
          <h2 className="text-2xl font-bold mb-4 text-green-800">{result.title}</h2>

          <div className="space-y-4">
            <div>
              <h3 className="font-semibold text-lg mb-2">📝 推荐理由</h3>
              <p className="text-gray-700">{result.rationale}</p>
            </div>

            <div>
              <h3 className="font-semibold text-lg mb-2">⚡ 预计热量: {result.estimated_calories} kcal</h3>
            </div>

            {result.steps.length > 0 && (
              <div>
                <h3 className="font-bold text-lg mb-2">👨‍🍳 烹饪步骤</h3>
                <ol className="list-decimal list-inside space-y-2 font-semibold text-gray-800">
                  {result.steps.map((step, i) => (
                    <li key={i}>{step}</li>
                  ))}
                </ol>
              </div>
            )}

            {result.ingredients && result.ingredients.length > 0 && (
              <div>
                <h3 className="font-semibold text-lg mb-3">🛒 所需食材</h3>

                {/* 食材行：中名称 | 右控件+数量+单位 */}
                <div className="space-y-2">
                  {effectiveIngredients.map((ing, i) => (
                    <div
                      key={i}
                      className="flex items-center gap-3 p-2 bg-white rounded-lg border border-gray-200"
                    >
                      {/* 中间：食材名称，居中 */}
                      <span className="flex-1 text-center font-medium text-gray-800">
                        {ing.name}
                      </span>
                      {/* 右侧：加减控件 + 可编辑数量 + 单位 */}
                      <div className="flex items-center gap-0.5 shrink-0">
                        <button
                          type="button"
                          onClick={() => adjustIngredient(i, -5)}
                          className="w-6 h-6 flex items-center justify-center rounded bg-gray-200 hover:bg-gray-300 text-xs font-bold"
                          title="减少 5"
                        >−5</button>
                        <button
                          type="button"
                          onClick={() => adjustIngredient(i, -1)}
                          className="w-6 h-6 flex items-center justify-center rounded bg-gray-200 hover:bg-gray-300 text-xs font-bold"
                          title="减少 1"
                        >−</button>
                        <input
                          type="number"
                          value={ing.amount}
                          onChange={(e) => {
                            const v = parseInt(e.target.value, 10);
                            if (Number.isFinite(v)) setIngredientAmount(i, v);
                          }}
                          className="w-16 text-center text-lg font-bold border border-gray-300 rounded px-1 py-0.5 focus:outline-none focus:ring-2 focus:ring-indigo-400"
                          min={1}
                        />
                        <button
                          type="button"
                          onClick={() => adjustIngredient(i, 1)}
                          className="w-6 h-6 flex items-center justify-center rounded bg-gray-200 hover:bg-gray-300 text-xs font-bold"
                          title="增加 1"
                        >+</button>
                        <button
                          type="button"
                          onClick={() => adjustIngredient(i, 5)}
                          className="w-6 h-6 flex items-center justify-center rounded bg-gray-200 hover:bg-gray-300 text-xs font-bold"
                          title="增加 5"
                        >+5</button>
                      </div>
                      {/* 单位 */}
                      <span className="text-sm text-gray-500 font-medium w-6 text-center shrink-0">{ing.unit}</span>
                    </div>
                  ))}
                </div>

                {/* 确认按钮 — 右下，放大 */}
                {!confirmed && (
                  <div className="flex justify-end mt-3">
                    <button
                      onClick={handleConfirmMeal}
                      disabled={confirming}
                      className="px-6 py-2 rounded-lg text-base font-bold bg-green-600 text-white hover:bg-green-700 disabled:opacity-50 transition-colors shadow-sm"
                    >
                      {confirming ? '处理中...' : '✅ 确认制作'}
                    </button>
                  </div>
                )}
              </div>
            )}

            {result.missing_ingredients.length > 0 && (
              <div>
                <h3 className="font-semibold text-lg mb-2 text-orange-700">❌ 缺少食材</h3>
                <ul className="list-disc list-inside text-orange-600">
                  {result.missing_ingredients.map((ing, i) => (
                    <li key={i}>{ing}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* 确认结果消息 */}
            {confirmResult && (
              <div className="pt-3 border-t">
                <p className={`text-sm ${confirmResult.startsWith('✅') ? 'text-green-700' : 'text-red-600'}`}>
                  {confirmResult}
                </p>
              </div>
            )}

            {result._audit?.trace_id && (
              <div className="pt-3 border-t">
                <p className="text-xs text-gray-500">
                  trace_id: <span className="font-mono">{result._audit.trace_id}</span>
                </p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
