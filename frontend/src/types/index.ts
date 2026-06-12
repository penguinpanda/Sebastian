export interface Inventory {
  id: string;
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
  name: string;
  quantity: number;
  unit: string;
  expire_date: string;
  days_left: number;
}

export interface RecipeRecommendResponse {
  title: string;
  rationale: string;
  estimated_calories: number;
  steps: string[];
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

export interface EquipmentCheckResponse {
  feasible: boolean;
  missing_equipment: string[];
  suggestion: string;
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

export interface MCPEquipmentCheckInput {
  equipment_owned?: string[];
  required_equipment?: string[];
}

export interface MCPSearchAnswerInput {
  user_id: string;
  query: string;
}
