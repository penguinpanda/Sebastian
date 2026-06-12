import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import MemorySearch from '../MemorySearch';
import { mcpAPI, memoryAPI } from '../../services/api';

vi.mock('../../services/api', () => ({
  mcpAPI: {
    searchAnswer: vi.fn(),
  },
  memoryAPI: {
    save: vi.fn(),
    list: vi.fn(),
    remove: vi.fn(),
  },
}));

describe('MemorySearch', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(memoryAPI.list).mockResolvedValue({ data: [] } as never);
    vi.mocked(memoryAPI.remove).mockResolvedValue({ data: { deleted: true } } as never);
    vi.spyOn(window, 'confirm').mockReturnValue(true);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('shows save success message', async () => {
    vi.mocked(memoryAPI.save).mockResolvedValue({ data: { status: 'ok' } } as never);

    render(<MemorySearch userId="u-1" />);

    fireEvent.change(screen.getByPlaceholderText('例：我不吃花生，对海鲜过敏'), {
      target: { value: '我不吃花生' },
    });
    fireEvent.click(screen.getByRole('button', { name: '保存记忆' }));

    await waitFor(() => {
      expect(screen.getByText('记忆已保存')).toBeInTheDocument();
    });
  });

  it('shows saved memories from newest to oldest', async () => {
    vi.mocked(memoryAPI.list).mockResolvedValue({
      data: [
        {
          memory_id: 'm-new',
          user_id: 'u-1',
          memory_type: 'profile',
          content: '最新记忆',
          tags: ['new'],
          importance: 0.8,
          score: 0,
          lexical_score: 0,
          vector_score: 0,
          retrieval_source: 'lexical',
          updated_at: '2026-06-11T10:00:00Z',
        },
        {
          memory_id: 'm-old',
          user_id: 'u-1',
          memory_type: 'history',
          content: '较早记忆',
          tags: [],
          importance: 0.5,
          score: 0,
          lexical_score: 0,
          vector_score: 0,
          retrieval_source: 'lexical',
          updated_at: '2026-06-10T10:00:00Z',
        },
      ],
    } as never);

    render(<MemorySearch userId="u-1" />);

    await waitFor(() => {
      expect(screen.getByText('最新记忆')).toBeInTheDocument();
    });

    const newest = screen.getByText('最新记忆');
    const oldest = screen.getByText('较早记忆');
    expect(newest.compareDocumentPosition(oldest) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('shows search trace id in result', async () => {
    vi.mocked(mcpAPI.searchAnswer).mockResolvedValue({
      data: {
        result: {
          summary: 'Found 1 relevant memory snippet(s) for your query.',
          evidence: ['我不吃花生'],
          retrieval_mode: 'hybrid',
          _audit: {
            trace_id: 'trace-test-123',
            user_id: 'u-1',
            action: 'invoke',
            tool_name: 'search.answer',
            timestamp: '2026-06-11T00:00:00Z',
          },
        },
      },
    } as never);

    render(<MemorySearch userId="u-1" />);

    fireEvent.change(screen.getByPlaceholderText('例：有什么饮食禁忌、我的身体状况、喜欢的烹饪方式'), {
      target: { value: '饮食禁忌' },
    });
    fireEvent.click(screen.getByRole('button', { name: '搜索' }));

    await waitFor(() => {
      expect(screen.getByText('trace-test-123')).toBeInTheDocument();
    });
  });

  it('deletes a saved memory from the list', async () => {
    vi.mocked(memoryAPI.list).mockResolvedValue({
      data: [
        {
          memory_id: 'm-delete',
          user_id: 'u-1',
          memory_type: 'profile',
          content: '待删除记忆',
          tags: [],
          importance: 0.5,
          score: 0,
          lexical_score: 0,
          vector_score: 0,
          retrieval_source: 'lexical',
          updated_at: '2026-06-11T10:00:00Z',
        },
      ],
    } as never);

    render(<MemorySearch userId="u-1" />);

    await waitFor(() => {
      expect(screen.getByText('待删除记忆')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: '删除' }));

    await waitFor(() => {
      expect(memoryAPI.remove).toHaveBeenCalledWith('m-delete', 'u-1');
      expect(screen.queryByText('待删除记忆')).not.toBeInTheDocument();
    });
  });
});
