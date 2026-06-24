export interface Inventory {
  id: string;
  item_type: 'ingredient' | 'equipment';
  name: string;
  quantity: number;
  unit: string;
  expire_date: string;
  note?: string;
  created_at: string;
  updated_at: string;
}

export interface ExpiringInventory {
  id: string;
  item_type: string;
  name: string;
  quantity: number;
  unit: string;
  expire_date: string;
  days_left: number;
}

export interface RecipeIngredient {
  name: string;
  amount: number;
  unit: string;
}

export interface RecipeRecommendResponse {
  title: string;
  rationale: string;
  estimated_calories: number;
  ingredients: RecipeIngredient[];
  steps: string[];
  required_equipment: string[];
  feasible: boolean;
  missing_equipment: string[];
  missing_ingredients: string[];
  _audit?: MCPAudit;
}

export interface HealthAnalyzeResponse {
  bmi: number;
  bmi_category: string;
  suggested_daily_calories: number;
  advice: string;
  _audit?: MCPAudit;
}

export interface SearchAnswerResponse {
  summary: string;
  evidence: string[];
  retrieval_mode: string;
  _audit?: MCPAudit;
}

export interface MemoryHit {
  memory_id: string;
  user_id: string;
  memory_type: string;
  content: string;
  tags: string[];
  importance: number;
  score: number;
  lexical_score: number;
  vector_score: number;
  retrieval_source: 'lexical' | 'vector' | 'hybrid';
  updated_at?: string | null;
}

export interface MCPAudit {
  trace_id: string;
  user_id: string | null;
  action: string;
  tool_name: string;
  timestamp: string;
}

export interface MCPInvokeRequest<TInput extends object> {
  name: string;
  input: TInput;
  idempotency_key?: string;
  trace_id?: string;
  user_id?: string;
  action?: string;
}

export interface MCPInvokeResponse<TResult extends object> {
  trace_id: string;
  tool_name: string;
  result: TResult & { _audit?: MCPAudit };
  latency_ms: number;
  status: 'ok' | 'error';
  error_code?: 'RETRYABLE_ERROR' | 'VALIDATION_ERROR' | 'BUSINESS_ERROR' | 'FATAL_ERROR' | null;
  error_message?: string | null;
  from_cache: boolean;
}

export interface MCPRecipeRecommendInput {
  user_id: string;
  meal_type?: 'breakfast' | 'lunch' | 'dinner' | 'snack';
  target_calories?: number;
  available_equipment?: string[];
  dietary_preferences?: string[];
}

export interface MCPHealthAnalyzeInput {
  user_id: string;
  height_cm: number;
  weight_kg: number;
  target_weight_kg?: number;
  daily_calories_taken?: number;
}


export interface MCPSearchAnswerInput {
  user_id: string;
  query: string;
}

// ========== 注册表单 ==========

export interface RegisterPreferencesData {
  dietary: string[];
  lifestyle: string[];
  cuisine: string[];
  free_text: string;
}

export interface RegisterFormData {
  email: string;
  password: string;
  confirmPassword: string;
  classification: 'single_male' | 'single_female' | '';
  preferences: RegisterPreferencesData;
  age: number | null;
  gender: string;
  height_cm: number | null;
  weight_kg: number | null;
  activity_level: string;
  health_goal: string;
}
