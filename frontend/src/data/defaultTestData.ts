export const DEFAULT_TEST_USER_ID = 'user-001';

export const DEFAULT_INVENTORY_ITEM = {
  name: '鸡蛋',
  quantity: 12,
  unit: '个',
  expire_date: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
  note: '测试数据：用于验证新增、列表刷新和临期提醒',
};

export const DEFAULT_HEALTH_FORM = {
  height_cm: 175,
  weight_kg: 68,
  target_weight_kg: 65,
  daily_calories_taken: 1900,
};

export const DEFAULT_EQUIPMENT_FORM = {
  owned: '平底锅,砂锅,刀,砧板,微波炉',
  required: '平底锅,烤箱,高压锅',
};

export const DEFAULT_RECIPE_FORM = {
  meal_type: 'dinner' as const,
  target_calories: 600,
  available_equipment: ['pan', 'pot', 'rice_cooker'],
  dietary_preferences: ['high-protein'],
};

// ========== 注册表单默认值 ==========

export const DEFAULT_REGISTER_FORM = {
  email: 'test@example.com',
  password: 'test123456',
  confirmPassword: 'test123456',
  classification: '' as const,
  preferences: {
    dietary: [] as string[],
    lifestyle: [] as string[],
    cuisine: [] as string[],
    free_text: '',
  },
  age: 25,
  gender: 'male',
  height_cm: 175,
  weight_kg: 70,
  activity_level: 'medium',
  health_goal: 'maintain',
};