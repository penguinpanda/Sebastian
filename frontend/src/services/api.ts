import axios from 'axios';
import {
  MCPInvokeRequest,
  MCPInvokeResponse,
  MCPRecipeRecommendInput,
  MCPHealthAnalyzeInput,
  MCPSearchAnswerInput,
  HealthAnalyzeResponse,
  RecipeRecommendResponse,
  SearchAnswerResponse,
  A2ASendTaskRequest,
  A2ASendTaskResponse,
  A2ATask,
} from '../types';
import { mapApiErrorMessage } from './error';

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) || 'http://127.0.0.1:8000/api';

// 统一的 Axios 实例：所有前端模块都通过这里共享 baseURL、超时和错误格式化。
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    // 后端可能返回 detail 或 error_message，这里统一映射成 UI 可直接展示的 friendlyMessage。
    const status: number | undefined = error?.response?.status;
    const detail: string | undefined = error?.response?.data?.detail || error?.response?.data?.error_message;
    const errorCode: string | undefined = error?.response?.data?.error_code;

    error.friendlyMessage = mapApiErrorMessage({
      status,
      errorCode,
      detail,
      fallback: error?.message || '请求失败，请稍后重试',
    });

    return Promise.reject(error);
  }
);

// 库存 API：对应后端 /api/inventory 路由。
export const inventoryAPI = {
  list: (user_id?: string, item_type?: string) =>
    apiClient.get('/inventory', { params: { ...(user_id ? { user_id } : {}), ...(item_type ? { item_type } : {}) } }),
  create: (data: any) =>
    apiClient.post('/inventory', data, { headers: { 'Content-Type': 'application/json' } }),
  get: (id: string) => apiClient.get(`/inventory/${id}`),
  remove: (id: string) => apiClient.delete(`/inventory/${id}`),
  adjust: (id: string, delta: number, note?: string) =>
    apiClient.patch(`/inventory/${id}/adjust`, { delta, note }),
  summary: (days: number = 7, user_id?: string, item_type?: string) =>
    apiClient.get('/inventory/summary', { params: { days, ...(user_id ? { user_id } : {}), ...(item_type ? { item_type } : {}) } }),
  expiring: (days: number = 7, user_id?: string, item_type?: string) =>
    apiClient.get('/inventory/alerts/expiring', { params: { days, ...(user_id ? { user_id } : {}), ...(item_type ? { item_type } : {}) } }),
};

// Agent API：A2A 协议替代旧的 /agent/chat 和 /agent/tasks/{id}。
export const agentAPI = {
  chat: (message: string, user_id?: string, context_id?: string) =>
    apiClient.post<A2ASendTaskResponse>('/a2a/tasks', {
      message,
      user_id,
      ...(context_id ? { context_id } : {}),
    }),
  taskStatus: (task_id: string) => apiClient.get<A2ATask>(`/a2a/tasks/${task_id}`),
  queueStats: () => apiClient.get('/a2a/tasks').then(() => ({ data: { queue_size: 0 } })), // A2A 无队列统计，返回 0 兼容
};

// Agent Tool API：面向菜谱、健康、搜索三类专用 Agent。
export const agentToolsAPI = {
  recipeRecommend: (data: any) => apiClient.post('/agents/recipe/recommend', data),
  recipeRecommendFromInventory: (data: any) =>
    apiClient.post('/agents/recipe/recommend-from-inventory', data),
  healthAnalyze: (data: any) => apiClient.post('/agents/health/analyze', data),
  searchAnswer: (data: any) => apiClient.post('/agents/search/answer', data),
};

// 记忆 API：保存用户长期记忆，并按 lexical/vector/hybrid 模式检索。
export const memoryAPI = {
  save: (data: any) => apiClient.post('/search/memory', data),
  list: (user_id: string, limit: number = 50) =>
    apiClient.get('/search/memory/list', { params: { user_id, limit } }),
  remove: (memory_id: string, user_id: string) =>
    apiClient.delete(`/search/memory/${memory_id}`, { params: { user_id } }),
  search: (user_id: string, query: string, top_k: number = 5, retrieval_mode: string = 'hybrid') =>
    apiClient.get('/search/memory', { params: { user_id, query, top_k, retrieval_mode } }),
};

// Health API
export const healthAPI = {
  check: () => apiClient.get('/health'),
  dependencies: () => apiClient.get('/health/dependencies'),
};

// Meal API：确认制作菜谱 + 查询饮食历史 + 回退
export const mealAPI = {
  confirm: (recipe: any, user_id: string) =>
    apiClient.post('/meals/confirm', { user_id, recipe }),
  rollback: (meal_id: string) =>
    apiClient.post(`/meals/${meal_id}/rollback`),
  history: (user_id: string, days: number = 7) =>
    apiClient.get('/meals/history', { params: { user_id, days } }),
};

// Conversation API：持久化对话历史
export const conversationAPI = {
  save: (user_id: string, date: string, messages: any[]) =>
    apiClient.post('/conversations/save', { user_id, date, messages }),
  load: (user_id: string, date: string) =>
    apiClient.get('/conversations', { params: { user_id, date } }),
  dates: (user_id: string) =>
    apiClient.get('/conversations/dates', { params: { user_id } }),
};

// Profile API：用户健康档案
export const profileAPI = {
  save: (data: any) => apiClient.post('/profile', data),
  get: (user_id: string) => apiClient.get('/profile', { params: { user_id } }),
};

// Recipe 菜谱库 API
export const recipeAPI = {
  list: (user_id: string, query?: string, sort?: string, limit?: number) =>
    apiClient.get('/recipes', { params: { user_id, query, sort, limit } }),
  top: (user_id: string, limit?: number) =>
    apiClient.get('/recipes/top', { params: { user_id, limit } }),
};

// ── A2A API（新协议，替代 MCP invoke） ────────────────────────────

/** 统一的 A2A Task 发送（替代 MCP invoke）。 */
const sendA2ATask = (skill_id: string, message: string, user_id: string, extra: Record<string, any> = {}) =>
  apiClient.post<A2ASendTaskResponse>('/a2a/tasks', {
    message,
    user_id,
    skill_id,
    ...extra,
  });

export const a2aAPI = {
  /** 创建 A2A 任务 */
  sendTask: (params: A2ASendTaskRequest) =>
    apiClient.post<A2ASendTaskResponse>('/a2a/tasks', params),
  /** 查询任务状态 */
  getTask: (task_id: string) => apiClient.get<A2ATask>(`/a2a/tasks/${task_id}`),
  /** 取消任务 */
  cancelTask: (task_id: string) => apiClient.post(`/a2a/tasks/${task_id}/cancel`),
  /** 菜谱推荐 */
  recipeRecommend: (params: { input: MCPRecipeRecommendInput; user_id: string }) =>
    sendA2ATask('recipe.recommend', '推荐菜谱', params.user_id, params.input),
  /** 基于库存的菜谱推荐 */
  recipeRecommendFromInventory: (params: { input: MCPRecipeRecommendInput; user_id: string }) =>
    sendA2ATask('recipe.recommend-from-inventory', '基于库存推荐菜谱', params.user_id, params.input),
  /** 健康分析 */
  healthAnalyze: (params: { input: MCPHealthAnalyzeInput; user_id: string }) =>
    sendA2ATask('health.analyze', '健康分析', params.user_id, params.input),
  /** 搜索回答 */
  searchAnswer: (params: { input: MCPSearchAnswerInput; user_id: string }) =>
    sendA2ATask('search.answer', params.input.query, params.user_id),
};

// ── MCP API（向后兼容，内部委托到 A2A） ─────────────────────

const invokeMCPTool = <TInput extends object, TResult extends object>(
  payload: MCPInvokeRequest<TInput>
) => {
  // MCP → A2A 转换：name → skill_id, input 合并到 metadata
  return apiClient.post<MCPInvokeResponse<TResult>>('/a2a/tasks', {
    message: `MCP ${payload.name}`,
    user_id: payload.user_id,
    skill_id: payload.name,
    ...(payload.input as Record<string, any>),
  }).then(response => {
    // 将 A2A 响应包装为 MCP 格式以保持兼容
    const a2aData = response.data as any;
    return {
      ...response,
      data: {
        trace_id: payload.trace_id || '',
        tool_name: payload.name,
        result: { ...(a2aData.direct_reply ? { summary: a2aData.direct_reply } : {}) },
        latency_ms: 0,
        status: 'ok' as const,
        from_cache: false,
      } as MCPInvokeResponse<TResult>,
    };
  });
};

export const mcpAPI = {
  recipeRecommend: (params: {
    input: MCPRecipeRecommendInput;
    user_id: string;
    action?: string;
    idempotency_key?: string;
    trace_id?: string;
  }) =>
    invokeMCPTool<MCPRecipeRecommendInput, RecipeRecommendResponse>({
      name: 'recipe.recommend',
      input: params.input,
      user_id: params.user_id,
      action: params.action ?? 'invoke',
      idempotency_key: params.idempotency_key,
      trace_id: params.trace_id,
    }),

  healthAnalyze: (params: {
    input: MCPHealthAnalyzeInput;
    user_id: string;
    action?: string;
    idempotency_key?: string;
    trace_id?: string;
  }) =>
    invokeMCPTool<MCPHealthAnalyzeInput, HealthAnalyzeResponse>({
      name: 'health.analyze',
      input: params.input,
      user_id: params.user_id,
      action: params.action ?? 'invoke',
      idempotency_key: params.idempotency_key,
      trace_id: params.trace_id,
    }),

  searchAnswer: (params: {
    input: MCPSearchAnswerInput;
    user_id: string;
    action?: string;
    idempotency_key?: string;
    trace_id?: string;
  }) =>
    invokeMCPTool<MCPSearchAnswerInput, SearchAnswerResponse>({
      name: 'search.answer',
      input: params.input,
      user_id: params.user_id,
      action: params.action ?? 'invoke',
      idempotency_key: params.idempotency_key,
      trace_id: params.trace_id,
    }),

  recipeRecommendFromInventory: (params: {
    input: MCPRecipeRecommendInput;
    user_id: string;
    action?: string;
    idempotency_key?: string;
    trace_id?: string;
  }) =>
    invokeMCPTool<MCPRecipeRecommendInput, RecipeRecommendResponse>({
      name: 'recipe.recommend-from-inventory',
      input: params.input,
      user_id: params.user_id,
      action: params.action ?? 'invoke',
      idempotency_key: params.idempotency_key,
      trace_id: params.trace_id,
    }),
};
