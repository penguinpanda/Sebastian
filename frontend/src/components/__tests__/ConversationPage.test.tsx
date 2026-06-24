import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import ConversationPage from '../ConversationPage';
import { agentAPI, mcpAPI, mealAPI, conversationAPI } from '../../services/api';

vi.mock('../../services/api', () => ({
  agentAPI: { chat: vi.fn() },
  mcpAPI: { recipeRecommend: vi.fn(), recipeRecommendFromInventory: vi.fn() },
  mealAPI: { confirm: vi.fn() },
  conversationAPI: {
    dates: vi.fn(),
    load: vi.fn(),
    save: vi.fn(),
  },
}));

const recipeResponse = {
  title: '鸡蛋蔬菜能量碗',
  rationale: '适合当前时段，营养均衡。',
  estimated_calories: 520,
  steps: ['准备食材', '少油烹饪'],
  ingredients: [
    { name: '鸡蛋', amount: 2, unit: '个' },
    { name: '西兰花', amount: 100, unit: 'g' },
  ],
  required_equipment: ['平底锅', '刀'],
  feasible: true,
  missing_equipment: [],
  missing_ingredients: ['牛油果'],
};

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(mcpAPI.recipeRecommend).mockResolvedValue({
    data: { result: recipeResponse },
  } as never);
  vi.mocked(mcpAPI.recipeRecommendFromInventory).mockResolvedValue({
    data: { result: recipeResponse },
  } as never);
  vi.mocked(conversationAPI.dates).mockResolvedValue({
    data: { dates: [] },
  } as never);
  vi.mocked(conversationAPI.load).mockResolvedValue({
    data: { messages: null },
  } as never);
  vi.mocked(agentAPI.chat).mockResolvedValue({
    data: { reply: '可以，我来帮你看看库存。', task_id: 'task-1' },
  } as never);
  vi.mocked(mealAPI.confirm).mockResolvedValue({
    data: { deducted: [], missing: [] },
  } as never);
});

// ─── 分组 A：表单渲染与交互 ──────────────────────────────────

describe('ConversationPage — 表单渲染与交互', () => {
  it('A1. 渲染菜谱推荐表单各字段', () => {
    render(<ConversationPage userId="u-1" />);

    expect(screen.getByText('🍽️ 菜谱推荐')).toBeInTheDocument();
    expect(screen.getByRole('combobox')).toBeInTheDocument(); // 用餐类型下拉
    expect(screen.getByRole('spinbutton')).toBeInTheDocument(); // 目标热量 input[number]

    // 6 个厨具按钮（中文标签）
    ['平底锅', '汤锅', '烤箱', '微波炉', '电饭煲', '搅拌机'].forEach((eq) => {
      expect(screen.getByRole('button', { name: eq })).toBeInTheDocument();
    });

    // 4 个饮食偏好按钮（中文标签）
    ['高蛋白', '低脂', '素食', '低碳水'].forEach((p) => {
      expect(screen.getByRole('button', { name: p })).toBeInTheDocument();
    });

    // 「获取推荐」按钮
    expect(screen.getByRole('button', { name: '获取推荐' })).toBeInTheDocument();
  });

  it('A2. 厨具按钮切换选中/取消', () => {
    render(<ConversationPage userId="u-1" />);

    const ovenBtn = screen.getByRole('button', { name: '烤箱' });
    expect(ovenBtn.className).toContain('bg-gray-200');

    fireEvent.click(ovenBtn);
    expect(ovenBtn.className).toContain('bg-blue-600');

    fireEvent.click(ovenBtn);
    expect(ovenBtn.className).toContain('bg-gray-200');
  });

  it('A3. 饮食偏好按钮切换选中/取消', () => {
    render(<ConversationPage userId="u-1" />);

    const vegBtn = screen.getByRole('button', { name: '素食' });
    expect(vegBtn.className).toContain('bg-gray-200');

    fireEvent.click(vegBtn);
    expect(vegBtn.className).toContain('bg-green-600');

    fireEvent.click(vegBtn);
    expect(vegBtn.className).toContain('bg-gray-200');
  });

  it('A4. 热量校验：< 200 禁用', () => {
    render(<ConversationPage userId="u-1" />);
    const submitBtn = screen.getByRole('button', { name: '获取推荐' });
    const calInput = screen.getByRole('spinbutton');

    fireEvent.change(calInput, { target: { value: '100' } });
    expect(submitBtn).toBeDisabled();
  });

  it('A4b. 热量校验：> 2000 禁用', () => {
    render(<ConversationPage userId="u-1" />);
    const calInput = screen.getByRole('spinbutton');

    fireEvent.change(calInput, { target: { value: '2500' } });
    expect(screen.getByRole('button', { name: '获取推荐' })).toBeDisabled();
  });

  it('A4c. 热量校验：有效值可用', () => {
    render(<ConversationPage userId="u-1" />);
    const calInput = screen.getByRole('spinbutton');

    fireEvent.change(calInput, { target: { value: '600' } });
    expect(screen.getByRole('button', { name: '获取推荐' })).not.toBeDisabled();
  });

  it('A5. 表单提交传递正确参数', async () => {
    render(<ConversationPage userId="u-1" />);

    // 切换用餐类型
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'lunch' } });
    // 设置热量
    fireEvent.change(screen.getByRole('spinbutton'), { target: { value: '700' } });
    // 选中 烤箱
    fireEvent.click(screen.getByRole('button', { name: '烤箱' }));
    // 选中 素食
    fireEvent.click(screen.getByRole('button', { name: '素食' }));

    fireEvent.click(screen.getByRole('button', { name: '获取推荐' }));

    await waitFor(() => {
      expect(mcpAPI.recipeRecommend).toHaveBeenCalledWith(
        expect.objectContaining({
          input: expect.objectContaining({
            meal_type: 'lunch',
            target_calories: 700,
            available_equipment: expect.arrayContaining(['pan', 'pot', 'rice_cooker', 'oven']),
            dietary_preferences: expect.arrayContaining(['high-protein', 'vegetarian']),
          }),
        })
      );
    });
  });
});

// ─── 分组 B：菜谱推荐结果展示 ──────────────────────────────

describe('ConversationPage — 菜谱推荐结果展示', () => {
  it('B1. 推荐结果作为 assistant 消息展示', async () => {
    render(<ConversationPage userId="u-1" />);

    fireEvent.click(screen.getByRole('button', { name: '获取推荐' }));

    await waitFor(() => {
      expect(screen.getByText(/为你推荐(早餐|午餐|晚餐|零食)/)).toBeInTheDocument();
    });
    expect(screen.getByText(/鸡蛋蔬菜能量碗/)).toBeInTheDocument();
  });

  it('B2. 菜谱消息包含步骤和食材', async () => {
    render(<ConversationPage userId="u-1" />);

    fireEvent.click(screen.getByRole('button', { name: '获取推荐' }));

    await waitFor(() => {
      expect(screen.getByText('准备食材')).toBeInTheDocument();
      expect(screen.getByText('少油烹饪')).toBeInTheDocument();
    });
    expect(screen.getByText(/鸡蛋 — 2 个/)).toBeInTheDocument();
    expect(screen.getByText(/西兰花 — 100 g/)).toBeInTheDocument();
  });

  it('B3. 推荐失败时显示错误', async () => {
    vi.mocked(mcpAPI.recipeRecommend).mockRejectedValue(new Error('fail'));
    render(<ConversationPage userId="u-1" />);

    fireEvent.click(screen.getByRole('button', { name: '获取推荐' }));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
  });
});

// ─── 分组 C：对话流 ────────────────────────────────────────

describe('ConversationPage — 对话流', () => {
  it('C1. 普通对话调用 agentAPI.chat', async () => {
    render(<ConversationPage userId="u-1" />);

    fireEvent.change(
      screen.getByPlaceholderText('输入你想和 Sebastian 说的话'),
      { target: { value: '看看我的库存' } }
    );
    fireEvent.click(screen.getByRole('button', { name: '对话' }));

    await waitFor(() => {
      expect(screen.getByText('可以，我来帮你看看库存。')).toBeInTheDocument();
    });
    expect(agentAPI.chat).toHaveBeenCalledWith('看看我的库存', 'u-1');
  });

  it('C2. 基于已有菜谱的对话调整', async () => {
    render(<ConversationPage userId="u-1" />);

    // 先获取推荐
    fireEvent.click(screen.getByRole('button', { name: '获取推荐' }));
    await waitFor(() => {
      expect(screen.getByText(/为你推荐/)).toBeInTheDocument();
    });

    // 再发送调整指令
    fireEvent.change(
      screen.getByPlaceholderText('例如：不要鸡蛋、清淡一点、换成低碳水'),
      { target: { value: '不要鸡蛋，清淡一点' } }
    );
    fireEvent.click(screen.getByRole('button', { name: '对话' }));

    await waitFor(() => {
      expect(screen.getByText(/已根据你的要求调整/)).toBeInTheDocument();
    });

    expect(mcpAPI.recipeRecommend).toHaveBeenLastCalledWith(
      expect.objectContaining({
        input: expect.objectContaining({
          dietary_preferences: ['不要鸡蛋，清淡一点'],
        }),
      })
    );
  });
});

// ─── 分组 D：确认制作 ──────────────────────────────────────

describe('ConversationPage — 确认制作', () => {
  it('D1. 菜谱消息卡片中有「确认制作」按钮', async () => {
    render(<ConversationPage userId="u-1" />);

    fireEvent.click(screen.getByRole('button', { name: '获取推荐' }));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: '✅ 确认制作' })).toBeInTheDocument();
    });
  });

  it('D2. 点击确认制作调用 mealAPI.confirm', async () => {
    render(<ConversationPage userId="u-1" />);

    fireEvent.click(screen.getByRole('button', { name: '获取推荐' }));
    await waitFor(() => {
      expect(screen.getByRole('button', { name: '✅ 确认制作' })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: '✅ 确认制作' }));

    await waitFor(() => {
      expect(mealAPI.confirm).toHaveBeenCalledWith(recipeResponse, 'u-1');
    });
  });

  it('D3. 确认制作成功后显示反馈', async () => {
    vi.mocked(mealAPI.confirm).mockResolvedValue({
      data: {
        deducted: [{ name: '鸡蛋', amount: 2, unit: '个' }],
        missing: [{ name: '牛油果', amount: 1, unit: '个' }],
      },
    } as never);

    render(<ConversationPage userId="u-1" />);
    fireEvent.click(screen.getByRole('button', { name: '获取推荐' }));
    await waitFor(() => {
      expect(screen.getByRole('button', { name: '✅ 确认制作' })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: '✅ 确认制作' }));

    await waitFor(() => {
      expect(screen.getByText(/已从库存扣除：鸡蛋 2个/)).toBeInTheDocument();
      expect(screen.getByText(/库存不足：牛油果 1个/)).toBeInTheDocument();
    });
  });

  it('D4. 确认制作失败时显示错误', async () => {
    vi.mocked(mealAPI.confirm).mockRejectedValue(new Error('fail'));

    render(<ConversationPage userId="u-1" />);
    fireEvent.click(screen.getByRole('button', { name: '获取推荐' }));
    await waitFor(() => {
      expect(screen.getByRole('button', { name: '✅ 确认制作' })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: '✅ 确认制作' }));

    await waitFor(() => {
      expect(screen.getByText(/^❌/)).toBeInTheDocument();
    });
  });

  it('D5. 多条菜谱消息独立确认', async () => {
    render(<ConversationPage userId="u-1" />);

    // 第一次推荐
    fireEvent.click(screen.getByRole('button', { name: '获取推荐' }));
    await waitFor(() => {
      expect(screen.getByRole('button', { name: '✅ 确认制作' })).toBeInTheDocument();
    });

    // 确认第一条
    fireEvent.click(screen.getByRole('button', { name: '✅ 确认制作' }));
    await waitFor(() => {
      expect(screen.getByText(/已确认制作/)).toBeInTheDocument();
    });

    // 第二次推荐（调整）
    fireEvent.change(
      screen.getByPlaceholderText('例如：不要鸡蛋、清淡一点、换成低碳水'),
      { target: { value: '换成低碳水' } }
    );
    fireEvent.click(screen.getByRole('button', { name: '对话' }));

    await waitFor(() => {
      const confirmBtns = screen.getAllByRole('button', { name: '✅ 确认制作' });
      expect(confirmBtns.length).toBe(1); // 只有新消息的确认按钮
    });
  });
});

// ─── 分组 E：移除自动推荐 ────────────────────────────────

describe('ConversationPage — 移除自动推荐', () => {
  it('E1. 打开页面不自动调用推荐', () => {
    render(<ConversationPage userId="u-1" />);
    expect(mcpAPI.recipeRecommend).not.toHaveBeenCalled();
  });

  it('E2. 「推荐餐品」/「已推荐餐品」按钮不存在', () => {
    render(<ConversationPage userId="u-1" />);

    expect(screen.queryByRole('button', { name: '推荐餐品' })).toBeNull();
    expect(screen.queryByRole('button', { name: '已推荐餐品' })).toBeNull();
  });
});

// ─── 分组 F：仅使用库存材料生成菜谱 ─────────────────────────

describe('ConversationPage — 仅使用库存材料生成菜谱', () => {
  it('F1. 按钮渲染', () => {
    render(<ConversationPage userId="u-1" />);

    expect(
      screen.getByRole('button', { name: '仅使用库存材料生成菜谱' })
    ).toBeInTheDocument();
  });

  it('F2. 点击按钮调用 recipeRecommendFromInventory', async () => {
    render(<ConversationPage userId="u-1" />);

    fireEvent.click(
      screen.getByRole('button', { name: '仅使用库存材料生成菜谱' })
    );

    await waitFor(() => {
      expect(mcpAPI.recipeRecommendFromInventory).toHaveBeenCalledWith(
        expect.objectContaining({
          input: expect.objectContaining({
            meal_type: 'dinner',
            target_calories: 600,
          }),
        })
      );
    });
  });

  it('F3. 生成中按钮显示 loading 文案', async () => {
    vi.mocked(mcpAPI.recipeRecommendFromInventory).mockImplementation(
      () => new Promise(() => {}) // 永不 resolve，保持 loading
    );

    render(<ConversationPage userId="u-1" />);

    fireEvent.click(
      screen.getByRole('button', { name: '仅使用库存材料生成菜谱' })
    );

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: '库存菜谱生成中...' })
      ).toBeInTheDocument();
    });

    // 清理：恢复 mock
    vi.mocked(mcpAPI.recipeRecommendFromInventory).mockResolvedValue({
      data: { result: recipeResponse },
    } as never);
  });

  it('F4. 成功时将菜谱作为 assistant 消息展示', async () => {
    render(<ConversationPage userId="u-1" />);

    fireEvent.click(
      screen.getByRole('button', { name: '仅使用库存材料生成菜谱' })
    );

    await waitFor(() => {
      expect(screen.getByText(/仅使用库存材料为你推荐/)).toBeInTheDocument();
    });
    expect(screen.getByText(/鸡蛋蔬菜能量碗/)).toBeInTheDocument();
  });

  it('F5. 失败时显示错误信息', async () => {
    vi.mocked(mcpAPI.recipeRecommendFromInventory).mockRejectedValue(
      new Error('库存为空')
    );

    render(<ConversationPage userId="u-1" />);

    fireEvent.click(
      screen.getByRole('button', { name: '仅使用库存材料生成菜谱' })
    );

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
  });

  it('F6. 热量无效时按钮禁用', () => {
    render(<ConversationPage userId="u-1" />);

    const calInput = screen.getByRole('spinbutton');
    fireEvent.change(calInput, { target: { value: '100' } });

    expect(
      screen.getByRole('button', { name: '仅使用库存材料生成菜谱' })
    ).toBeDisabled();
  });

  it('F7. loading 期间按钮禁用', async () => {
    vi.mocked(mcpAPI.recipeRecommendFromInventory).mockImplementation(
      () => new Promise(() => {})
    );

    render(<ConversationPage userId="u-1" />);

    fireEvent.click(
      screen.getByRole('button', { name: '仅使用库存材料生成菜谱' })
    );

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: '库存菜谱生成中...' })
      ).toBeDisabled();
    });

    vi.mocked(mcpAPI.recipeRecommendFromInventory).mockResolvedValue({
      data: { result: recipeResponse },
    } as never);
  });
});
