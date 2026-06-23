import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { agentAPI, conversationAPI, mcpAPI, mealAPI } from '../services/api';
import { RecipeRecommendResponse } from '../types';
import { DEFAULT_RECIPE_FORM } from '../data/defaultTestData';
import ErrorState from './common/ErrorState';
import { getFriendlyError } from '../services/error';

interface Props {
  userId: string;
}

type MealType = 'breakfast' | 'lunch' | 'dinner' | 'snack';

type RecipeForm = {
  meal_type: MealType;
  target_calories: number;
  available_equipment: string[];
  dietary_preferences: string[];
};

type ChatMessage = {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  recipe?: RecipeRecommendResponse;
  mealId?: string;
  rolledBack?: boolean;
  confirmResult?: string;
};

type ConfirmState = {
  confirming: boolean;
  result: string;
  confirmed: boolean;
  mealId?: string;
  rollbacking?: boolean;
};

const mealLabels: Record<MealType, string> = {
  breakfast: '早餐',
  lunch: '午餐',
  dinner: '晚餐',
  snack: '零食',
};

const EQUIPMENT_OPTIONS = [
  { value: 'pan', label: '平底锅' },
  { value: 'pot', label: '汤锅' },
  { value: 'oven', label: '烤箱' },
  { value: 'microwave', label: '微波炉' },
  { value: 'rice_cooker', label: '电饭煲' },
  { value: 'blender', label: '搅拌机' },
];
const PREFERENCE_OPTIONS = [
  { value: 'high-protein', label: '高蛋白' },
  { value: 'low-fat', label: '低脂' },
  { value: 'vegetarian', label: '素食' },
  { value: 'low-carb', label: '低碳水' },
];

function resolveMealTypeByTime(date = new Date()): MealType {
  const hour = date.getHours();
  if (hour >= 5 && hour < 11) return 'breakfast';
  if (hour >= 11 && hour < 16) return 'lunch';
  return 'dinner';
}

function buildRecipeMessage(recipe: RecipeRecommendResponse, mealType: MealType, prefix = '为你推荐') {
  return `${prefix}${mealLabels[mealType]}：${recipe.title}，约 ${recipe.estimated_calories} kcal。${recipe.rationale}`;
}

function todayStr(): string {
  return new Date().toISOString().slice(0, 10);
}

const INITIAL_RECIPE_FORM: RecipeForm = {
  meal_type: resolveMealTypeByTime() === 'snack' ? 'dinner' : resolveMealTypeByTime(),
  target_calories: DEFAULT_RECIPE_FORM.target_calories,
  available_equipment: [...DEFAULT_RECIPE_FORM.available_equipment],
  dietary_preferences: [...DEFAULT_RECIPE_FORM.dietary_preferences],
};

export default function ConversationPage({ userId }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      role: 'assistant',
      content: '你好，我是 Sebastian。你可以直接和我对话，也可以按上方表单配置推荐一餐。',
    },
  ]);
  const [input, setInput] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [isRecommending, setIsRecommending] = useState(false);
  const [isInventoryOnlyLoading, setIsInventoryOnlyLoading] = useState(false);
  const [inventoryOnlyError, setInventoryOnlyError] = useState('');
  const [currentMealType, setCurrentMealType] = useState<MealType | null>(null);
  const [currentRecipe, setCurrentRecipe] = useState<RecipeRecommendResponse | null>(null);
  const [error, setError] = useState('');
  const [conversationLoaded, setConversationLoaded] = useState(false);
  const [historyDates, setHistoryDates] = useState<string[]>([]);
  const [selectedDate, setSelectedDate] = useState(todayStr());
  const [recipeForm, setRecipeForm] = useState<RecipeForm>(INITIAL_RECIPE_FORM);
  const [confirmStates, setConfirmStates] = useState<Record<string, ConfirmState>>({});
  const [recipeEdits, setRecipeEdits] = useState<Record<string, RecipeRecommendResponse>>({});
  const [rollbackStates, setRollbackStates] = useState<Record<string, boolean>>({});
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const isCaloriesValid =
    Number.isFinite(recipeForm.target_calories) &&
    recipeForm.target_calories >= 200 &&
    recipeForm.target_calories <= 2000;

  // 加载对话日期列表
  useEffect(() => {
    conversationAPI.dates(userId).then(res => {
      setHistoryDates(res.data.dates || []);
    }).catch(() => {});
  }, [userId]);

  // 加载当日对话
  useEffect(() => {
    const date = selectedDate;
    conversationAPI.load(userId, date).then(res => {
      const data = res.data as any;
      if (data.messages && data.messages.length > 0) {
        setMessages(data.messages);
        // 从已保存消息恢复确认状态
        const restored: Record<string, ConfirmState> = {};
        for (const m of data.messages) {
          if (m.mealId && !m.rolledBack) {
            restored[m.id] = { confirming: false, result: m.confirmResult || '', confirmed: true, mealId: m.mealId };
          } else if (m.rolledBack) {
            restored[m.id] = { confirming: false, result: m.confirmResult || '↩️ 已回退', confirmed: false };
          }
        }
        setConfirmStates(restored);
      } else if (date === todayStr()) {
        setMessages([{
          id: 'welcome',
          role: 'assistant',
          content: '你好，我是 Sebastian。你可以直接和我对话，也可以按上方表单配置推荐一餐。',
        }]);
      } else {
        setMessages([]);
      }
      setConversationLoaded(true);
    }).catch(() => {
      setConversationLoaded(true);
    });
  }, [userId, selectedDate]);

  // 当日对话自动保存（去抖 2s）
  const saveConversation = useCallback(() => {
    if (selectedDate !== todayStr() || messages.length <= 1) return;
    conversationAPI.save(userId, todayStr(), messages).catch(() => {});
  }, [userId, messages, selectedDate]);

  useEffect(() => {
    if (!conversationLoaded) return;
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    saveTimerRef.current = setTimeout(saveConversation, 2000);
    return () => {
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    };
  }, [messages, conversationLoaded, saveConversation]);

  const currentMealLabel = useMemo(() => {
    return currentMealType ? mealLabels[currentMealType] : mealLabels[resolveMealTypeByTime()];
  }, [currentMealType]);

  const appendMessage = (message: Omit<ChatMessage, 'id'>) => {
    setMessages((prev) => [
      ...prev,
      {
        ...message,
        id: `${Date.now()}-${prev.length}`,
      },
    ]);
  };

  const requestMealRecommendation = async (params: {
    mealType: MealType;
    userInstruction?: string;
    prefix?: string;
  }) => {
    const res = await mcpAPI.recipeRecommend({
      user_id: userId,
      input: {
        user_id: userId,
        meal_type: params.mealType,
        target_calories: recipeForm.target_calories,
        available_equipment: recipeForm.available_equipment,
        dietary_preferences: params.userInstruction
          ? [params.userInstruction]
          : recipeForm.dietary_preferences.length > 0
            ? recipeForm.dietary_preferences
            : ['balanced'],
      },
    });

    const recipe = res.data.result;
    setCurrentMealType(params.mealType);
    setCurrentRecipe(recipe);
    appendMessage({
      role: 'assistant',
      content: buildRecipeMessage(recipe, params.mealType, params.prefix),
      recipe,
    });
  };

  const handleRecipeSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isCaloriesValid || isRecommending) return;

    setError('');
    setIsRecommending(true);
    try {
      await requestMealRecommendation({ mealType: recipeForm.meal_type });
    } catch (err: unknown) {
      setError(getFriendlyError(err, '餐品推荐失败'));
    } finally {
      setIsRecommending(false);
    }
  };

  const handleInventoryOnlyRecipe = async () => {
    if (!isCaloriesValid || isInventoryOnlyLoading) return;

    setInventoryOnlyError('');
    setError('');
    setIsInventoryOnlyLoading(true);
    try {
      const res = await mcpAPI.recipeRecommendFromInventory({
        user_id: userId,
        input: {
          user_id: userId,
          meal_type: recipeForm.meal_type,
          target_calories: recipeForm.target_calories,
          available_equipment: recipeForm.available_equipment,
          dietary_preferences:
            recipeForm.dietary_preferences.length > 0
              ? recipeForm.dietary_preferences
              : ['balanced'],
        },
      });

      const recipe = res.data.result;
      setCurrentMealType(recipeForm.meal_type);
      setCurrentRecipe(recipe);
      appendMessage({
        role: 'assistant',
        content: buildRecipeMessage(recipe, recipeForm.meal_type, '仅使用库存材料为你推荐'),
        recipe,
      });
    } catch (err: unknown) {
      setInventoryOnlyError(getFriendlyError(err, '库存材料菜谱生成失败'));
    } finally {
      setIsInventoryOnlyLoading(false);
    }
  };

  const toggleRecipeField = (field: 'available_equipment' | 'dietary_preferences', value: string) => {
    setRecipeForm((prev) => ({
      ...prev,
      [field]: prev[field].includes(value)
        ? prev[field].filter((v) => v !== value)
        : [...prev[field], value],
    }));
  };

  const getEffectiveRecipe = (messageId: string, original: RecipeRecommendResponse): RecipeRecommendResponse => {
    return recipeEdits[messageId] || original;
  };

  const adjustIngredient = (messageId: string, recipe: RecipeRecommendResponse, index: number, delta: number) => {
    const current = getEffectiveRecipe(messageId, recipe);
    const ings = [...current.ingredients];
    if (index < 0 || index >= ings.length) return;
    const newAmount = Math.max(1, (ings[index].amount || 0) + delta);
    ings[index] = { ...ings[index], amount: newAmount };
    setRecipeEdits(prev => ({
      ...prev,
      [messageId]: { ...current, ingredients: ings },
    }));
  };

  const handleConfirmMeal = async (messageId: string, originalRecipe: RecipeRecommendResponse) => {
    const msg = messages.find(m => m.id === messageId);
    if (!msg || msg.mealId || msg.rolledBack) return;
    if (confirmStates[messageId]?.confirming) return;

    const recipe = getEffectiveRecipe(messageId, originalRecipe);

    setConfirmStates((prev) => ({
      ...prev,
      [messageId]: { confirming: true, result: '', confirmed: false },
    }));

    try {
      const res = await mealAPI.confirm(recipe, userId);
      const data = res.data as any;
      const deductedNames = (data.deducted || [])
        .map((d: any) => `${d.name} ${d.amount}${d.unit}`)
        .join('、');
      const missingNames = (data.missing || [])
        .map((m: any) => `${m.name} ${m.amount}${m.unit}`)
        .join('、');
      let msg_text = '✅ 已确认制作！';
      if (deductedNames) msg_text += ` 已从库存扣除：${deductedNames}。`;
      if (missingNames) msg_text += ` ⚠️ 库存不足：${missingNames}。`;

      // 持久化到消息对象（随对话保存恢复）
      setMessages(prev => prev.map(m =>
        m.id === messageId
          ? { ...m, mealId: data.meal_id, confirmResult: msg_text, rolledBack: false }
          : m
      ));
      setConfirmStates((prev) => ({
        ...prev,
        [messageId]: { confirming: false, result: msg_text, confirmed: true, mealId: data.meal_id },
      }));
    } catch (err: unknown) {
      setConfirmStates((prev) => ({
        ...prev,
        [messageId]: {
          confirming: false,
          result: `❌ ${getFriendlyError(err, '确认制作失败')}`,
          confirmed: false,
        },
      }));
    }
  };

  const handleRollbackMeal = async (messageId: string) => {
    const msg = messages.find(m => m.id === messageId);
    if (!msg?.mealId || msg.rolledBack) return;
    if (rollbackStates[messageId]) return;

    setRollbackStates(prev => ({ ...prev, [messageId]: true }));

    try {
      await mealAPI.rollback(msg.mealId);
      const resultText = '↩️ 已回退，库存已恢复。';
      // 持久化到消息对象
      setMessages(prev => prev.map(m =>
        m.id === messageId
          ? { ...m, rolledBack: true, confirmResult: resultText, mealId: undefined }
          : m
      ));
      setConfirmStates(prev => ({
        ...prev,
        [messageId]: { confirming: false, result: resultText, confirmed: false },
      }));
    } catch (err: unknown) {
      setConfirmStates(prev => ({
        ...prev,
        [messageId]: {
          ...prev[messageId],
          result: `${prev[messageId]?.result || ''} ❌ 回退失败：${getFriendlyError(err, '')}`,
        },
      }));
    } finally {
      setRollbackStates(prev => ({ ...prev, [messageId]: false }));
    }
  };

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || isSending) return;

    appendMessage({ role: 'user', content: trimmed });
    setInput('');
    setError('');
    setIsSending(true);

    try {
      if (currentRecipe && currentMealType) {
        await requestMealRecommendation({
          mealType: currentMealType,
          userInstruction: trimmed,
          prefix: '已根据你的要求调整',
        });
      } else {
        const res = await agentAPI.chat(trimmed, userId);
        appendMessage({ role: 'assistant', content: res.data.reply });
      }
    } catch (err: unknown) {
      setError(getFriendlyError(err, '对话请求失败'));
    } finally {
      setIsSending(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* 标题 */}
      <div>
        <h2 className="text-2xl font-bold text-gray-800">对话</h2>
        <p className="text-sm text-gray-600 mt-1">
          当前推荐时段：{currentMealLabel}。通过上方表单配置偏好后获取推荐，后续可通过对话调整。
        </p>
      </div>

      {/* 菜谱推荐表单 */}
      <div className="card">
        <h3 className="text-lg font-semibold mb-4">🍽️ 菜谱推荐</h3>
        {error && <ErrorState message={error} className="mb-4" />}

        <form onSubmit={handleRecipeSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block font-medium mb-2 text-sm">用餐类型</label>
              <select
                value={recipeForm.meal_type}
                onChange={(e) => setRecipeForm({ ...recipeForm, meal_type: e.target.value as MealType })}
                className="input w-full"
              >
                <option value="breakfast">早餐</option>
                <option value="lunch">午餐</option>
                <option value="dinner">晚餐</option>
                <option value="snack">零食</option>
              </select>
            </div>
            <div>
              <label className="block font-medium mb-2 text-sm">目标热量 (kcal)</label>
              <input
                type="number"
                value={recipeForm.target_calories || ''}
                onChange={(e) => {
                  const next = parseInt(e.target.value, 10);
                  setRecipeForm({ ...recipeForm, target_calories: Number.isFinite(next) ? next : 0 });
                }}
                className="input w-full"
                min={200}
                max={2000}
              />
            </div>
          </div>

          <div>
            <label className="block font-medium mb-2 text-sm">🔪 可用厨具</label>
            <div className="flex flex-wrap gap-2">
              {EQUIPMENT_OPTIONS.map((eq) => (
                <button
                  key={eq.value}
                  type="button"
                  onClick={() => toggleRecipeField('available_equipment', eq.value)}
                  className={`px-3 py-1 rounded text-sm transition-colors ${
                    recipeForm.available_equipment.includes(eq.value)
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                  }`}
                >
                  {eq.label}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block font-medium mb-2 text-sm">🥗 饮食偏好</label>
            <div className="flex flex-wrap gap-2">
              {PREFERENCE_OPTIONS.map((p) => (
                <button
                  key={p.value}
                  type="button"
                  onClick={() => toggleRecipeField('dietary_preferences', p.value)}
                  className={`px-3 py-1 rounded text-sm transition-colors ${
                    recipeForm.dietary_preferences.includes(p.value)
                      ? 'bg-green-600 text-white'
                      : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                  }`}
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>

          <button
            type="submit"
            className="btn btn-primary w-full"
            disabled={!isCaloriesValid || isRecommending}
          >
            {isRecommending ? '推荐中...' : '获取推荐'}
          </button>

          <button
            type="button"
            onClick={handleInventoryOnlyRecipe}
            className="btn w-full mt-2 border-2 border-green-500 bg-white text-green-700 hover:bg-green-50 transition-colors"
            disabled={!isCaloriesValid || isInventoryOnlyLoading}
          >
            {isInventoryOnlyLoading ? '库存菜谱生成中...' : '仅使用库存材料生成菜谱'}
          </button>
          {inventoryOnlyError && <ErrorState message={inventoryOnlyError} className="mt-2" />}
        </form>
      </div>

      {/* 对话历史日期选择 */}
      {historyDates.length > 0 && (
        <div className="flex flex-wrap gap-2 items-center">
          <span className="text-sm text-gray-500">历史对话：</span>
          <button
            onClick={() => setSelectedDate(todayStr())}
            className={`px-3 py-1 rounded text-sm transition-colors ${
              selectedDate === todayStr() ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
            }`}
          >
            今天
          </button>
          {historyDates.filter(d => d !== todayStr()).slice(0, 10).map(d => (
            <button
              key={d}
              onClick={() => setSelectedDate(d)}
              className={`px-3 py-1 rounded text-sm transition-colors ${
                selectedDate === d ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
              }`}
            >
              {d.slice(5)}
            </button>
          ))}
        </div>
      )}

      {/* 对话消息列表 */}
      <div className="card">
        <div className="space-y-4 max-h-[520px] overflow-y-auto pr-2">
          {messages.map((message) => {
            const cs = confirmStates[message.id];
            return (
              <div
                key={message.id}
                className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[85%] rounded p-4 ${
                    message.role === 'user'
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-100 text-gray-800'
                  }`}
                >
                  <p className="whitespace-pre-wrap">{message.content}</p>
                  {message.recipe && (
                    <div className={`mt-3 pt-3 border-t space-y-2 text-sm ${
                      message.role === 'user' ? 'border-white/40' : 'border-gray-300'
                    }`}>
                      {message.recipe.steps.length > 0 && (
                        <div>
                          <h4 className="font-semibold mb-1">👨‍🍳 烹饪步骤</h4>
                          <ol className="list-decimal list-inside space-y-1">
                            {message.recipe.steps.map((step, index) => (
                              <li key={index}>{step}</li>
                            ))}
                          </ol>
                        </div>
                      )}
                      {message.recipe.ingredients && message.recipe.ingredients.length > 0 && (
                        <div>
                          <h4 className="font-semibold mb-1">🛒 所需食材</h4>
                          <ul className="space-y-1">
                            {(() => {
                              const eff = getEffectiveRecipe(message.id, message.recipe);
                              return eff.ingredients.map((ing, i) => (
                                <li key={i} className="flex items-center gap-2">
                                  <span className="flex-1">{ing.name} — {ing.amount} {ing.unit}</span>
                                  <button
                                    type="button"
                                    onClick={() => adjustIngredient(message.id, message.recipe!, i, -5)}
                                    className="w-6 h-6 flex items-center justify-center rounded bg-gray-200 hover:bg-gray-300 text-xs font-bold"
                                    title="减少"
                                  >−</button>
                                  <button
                                    type="button"
                                    onClick={() => adjustIngredient(message.id, message.recipe!, i, -1)}
                                    className="w-5 h-5 flex items-center justify-center rounded bg-gray-200 hover:bg-gray-300 text-xs"
                                  >-</button>
                                  <button
                                    type="button"
                                    onClick={() => adjustIngredient(message.id, message.recipe!, i, 1)}
                                    className="w-5 h-5 flex items-center justify-center rounded bg-gray-200 hover:bg-gray-300 text-xs"
                                  >+</button>
                                  <button
                                    type="button"
                                    onClick={() => adjustIngredient(message.id, message.recipe!, i, 5)}
                                    className="w-6 h-6 flex items-center justify-center rounded bg-gray-200 hover:bg-gray-300 text-xs font-bold"
                                    title="增加"
                                  >+</button>
                                </li>
                              ));
                            })()}
                          </ul>
                        </div>
                      )}
                      {message.recipe.missing_ingredients.length > 0 && (
                        <p className="text-orange-600">
                          ❌ 缺少食材：{message.recipe.missing_ingredients.join('、')}
                        </p>
                      )}
                      {/* 确认制作 + 回退 */}
                      <div className="pt-2">
                        {!message.mealId && !message.rolledBack ? (
                          <button
                            onClick={() => handleConfirmMeal(message.id, message.recipe!)}
                            disabled={cs?.confirming}
                            className="px-3 py-1.5 rounded text-sm font-medium bg-green-600 text-white hover:bg-green-700 disabled:opacity-50 transition-colors"
                          >
                            {cs?.confirming ? '处理中...' : '✅ 确认制作'}
                          </button>
                        ) : !message.rolledBack && message.mealId ? (
                          <button
                            onClick={() => handleRollbackMeal(message.id)}
                            disabled={rollbackStates[message.id]}
                            className="px-3 py-1.5 rounded text-sm font-medium bg-orange-500 text-white hover:bg-orange-600 disabled:opacity-50 transition-colors"
                          >
                            {rollbackStates[message.id] ? '回退中...' : '↩️ 回退'}
                          </button>
                        ) : null}
                        {(cs?.result || message.confirmResult) && (
                          <p className={`mt-1 text-xs ${
                            (cs?.result || message.confirmResult || '').includes('✅') ? 'text-green-700'
                            : (cs?.result || message.confirmResult || '').includes('↩️') ? 'text-blue-700'
                            : 'text-red-600'
                          }`}>
                            {cs?.result || message.confirmResult}
                          </p>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* 对话输入 */}
        <form onSubmit={handleSend} className="mt-6 space-y-3">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={currentRecipe ? '例如：不要鸡蛋、清淡一点、换成低碳水' : '输入你想和 Sebastian 说的话'}
            className="input w-full"
            rows={3}
          />
          <button
            type="submit"
            className="btn btn-primary w-full"
            disabled={isSending || !input.trim()}
          >
            {isSending ? '对话中...' : '对话'}
          </button>
        </form>
      </div>
    </div>
  );
}

