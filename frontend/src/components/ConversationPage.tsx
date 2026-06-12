import React, { useMemo, useState } from 'react';
import { agentAPI, mcpAPI } from '../services/api';
import { RecipeRecommendResponse } from '../types';
import ErrorState from './common/ErrorState';
import { getFriendlyError } from '../services/error';

interface Props {
  userId: string;
}

type MealType = 'breakfast' | 'lunch' | 'dinner';

type ChatMessage = {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  recipe?: RecipeRecommendResponse;
};

const mealLabels: Record<MealType, string> = {
  breakfast: '早餐',
  lunch: '午餐',
  dinner: '晚餐',
};

function resolveMealTypeByTime(date = new Date()): MealType {
  const hour = date.getHours();
  if (hour >= 5 && hour < 11) {
    return 'breakfast';
  }
  if (hour >= 11 && hour < 16) {
    return 'lunch';
  }
  return 'dinner';
}

function buildRecipeMessage(recipe: RecipeRecommendResponse, mealType: MealType, prefix = '为你推荐') {
  return `${prefix}${mealLabels[mealType]}：${recipe.title}，约 ${recipe.estimated_calories} kcal。${recipe.rationale}`;
}

export default function ConversationPage({ userId }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      role: 'assistant',
      content: '你好，我是 Sebastian。你可以直接和我对话，也可以让我按当前时间推荐一餐。',
    },
  ]);
  const [input, setInput] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [isRecommending, setIsRecommending] = useState(false);
  const [hasRecommendedMeal, setHasRecommendedMeal] = useState(false);
  const [currentMealType, setCurrentMealType] = useState<MealType | null>(null);
  const [currentRecipe, setCurrentRecipe] = useState<RecipeRecommendResponse | null>(null);
  const [error, setError] = useState('');

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
        target_calories: params.mealType === 'breakfast' ? 450 : 650,
        available_equipment: ['pan', 'pot', 'rice_cooker'],
        dietary_preferences: params.userInstruction ? [params.userInstruction] : ['balanced'],
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

  const handleRecommendMeal = async () => {
    if (hasRecommendedMeal || isRecommending) {
      return;
    }

    setError('');
    setIsRecommending(true);
    const mealType = resolveMealTypeByTime();
    try {
      await requestMealRecommendation({ mealType });
      setHasRecommendedMeal(true);
    } catch (err: unknown) {
      setError(getFriendlyError(err, '餐品推荐失败'));
    } finally {
      setIsRecommending(false);
    }
  };

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || isSending) {
      return;
    }

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
      <div>
        <h2 className="text-2xl font-bold text-gray-800">对话</h2>
        <p className="text-sm text-gray-600 mt-1">
          当前推荐时段：{currentMealLabel}。推荐餐品每次打开页面只会主动推荐一次，后续可通过对话调整。
        </p>
      </div>

      {error && <ErrorState message={error} />}

      <div className="card">
        <div className="space-y-4 max-h-[520px] overflow-y-auto pr-2">
          {messages.map((message) => (
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
                  <div className="mt-3 pt-3 border-t border-white/40 space-y-2 text-sm">
                    {message.recipe.steps.length > 0 && (
                      <ol className="list-decimal list-inside space-y-1">
                        {message.recipe.steps.map((step, index) => (
                          <li key={index}>{step}</li>
                        ))}
                      </ol>
                    )}
                    {message.recipe.missing_ingredients.length > 0 && (
                      <p>缺少食材：{message.recipe.missing_ingredients.join('、')}</p>
                    )}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>

        <form onSubmit={handleSend} className="mt-6 space-y-3">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={currentRecipe ? '例如：不要鸡蛋、清淡一点、换成低碳水' : '输入你想和 Sebastian 说的话'}
            className="input w-full"
            rows={3}
          />
          <div className="flex flex-col sm:flex-row gap-3">
            <button type="submit" className="btn btn-primary flex-1" disabled={isSending || !input.trim()}>
              {isSending ? '对话中...' : '对话'}
            </button>
            <button
              type="button"
              onClick={handleRecommendMeal}
              className="btn btn-secondary flex-1"
              disabled={isRecommending || hasRecommendedMeal}
            >
              {isRecommending ? '推荐中...' : hasRecommendedMeal ? '已推荐餐品' : '推荐餐品'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

