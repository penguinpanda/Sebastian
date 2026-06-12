import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import ConversationPage from '../ConversationPage';
import { agentAPI, mcpAPI } from '../../services/api';

vi.mock('../../services/api', () => ({
  agentAPI: {
    chat: vi.fn(),
  },
  mcpAPI: {
    recipeRecommend: vi.fn(),
  },
}));

const recipeResponse = {
  title: '鸡蛋蔬菜能量碗',
  rationale: '适合当前时段，营养均衡。',
  estimated_calories: 520,
  steps: ['准备食材', '少油烹饪'],
  missing_ingredients: [],
};

describe('ConversationPage', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(mcpAPI.recipeRecommend).mockResolvedValue({
      data: { result: recipeResponse },
    } as never);
  });

  it('recommends one meal based on current time only once', async () => {
    render(<ConversationPage userId="u-1" />);

    fireEvent.click(screen.getByRole('button', { name: '推荐餐品' }));

    await waitFor(() => {
      expect(screen.getByText(/为你推荐(早餐|午餐|晚餐)/)).toBeInTheDocument();
    });

    expect(mcpAPI.recipeRecommend).toHaveBeenCalledWith(
      expect.objectContaining({
        input: expect.objectContaining({
          meal_type: expect.stringMatching(/^(breakfast|lunch|dinner)$/),
        }),
      })
    );
    expect(screen.getByRole('button', { name: '已推荐餐品' })).toBeDisabled();
  });

  it('modifies the current recommendation from later conversation', async () => {
    render(<ConversationPage userId="u-1" />);

    fireEvent.click(screen.getByRole('button', { name: '推荐餐品' }));
    await waitFor(() => {
      expect(screen.getByText(/为你推荐(早餐|午餐|晚餐)/)).toBeInTheDocument();
    });

    fireEvent.change(screen.getByPlaceholderText('例如：不要鸡蛋、清淡一点、换成低碳水'), {
      target: { value: '不要鸡蛋，清淡一点' },
    });
    fireEvent.click(screen.getByRole('button', { name: '对话' }));

    await waitFor(() => {
      expect(screen.getByText(/已根据你的要求调整(早餐|午餐|晚餐)/)).toBeInTheDocument();
    });

    expect(mcpAPI.recipeRecommend).toHaveBeenLastCalledWith(
      expect.objectContaining({
        input: expect.objectContaining({
          meal_type: expect.stringMatching(/^(breakfast|lunch|dinner)$/),
          dietary_preferences: ['不要鸡蛋，清淡一点'],
        }),
      })
    );
  });

  it('uses normal chat when no meal has been recommended yet', async () => {
    vi.mocked(agentAPI.chat).mockResolvedValue({
      data: { reply: '可以，我来帮你看看库存。', task_id: 'task-1' },
    } as never);

    render(<ConversationPage userId="u-1" />);

    fireEvent.change(screen.getByPlaceholderText('输入你想和 Sebastian 说的话'), {
      target: { value: '看看我的库存' },
    });
    fireEvent.click(screen.getByRole('button', { name: '对话' }));

    await waitFor(() => {
      expect(screen.getByText('可以，我来帮你看看库存。')).toBeInTheDocument();
    });

    expect(agentAPI.chat).toHaveBeenCalledWith('看看我的库存', 'u-1');
  });
});
