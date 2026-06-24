import { fireEvent, render, screen } from '@testing-library/react';
import App from '../../App';

// Mock child components to isolate App navigation logic
vi.mock('../ConversationPage', () => ({
  default: ({ userId }: { userId: string }) => (
    <div data-testid="conversation-page">ConversationPage (userId: {userId})</div>
  ),
}));

vi.mock('../InventoryPage', () => ({
  default: ({ userId }: { userId: string }) => (
    <div data-testid="inventory-page">InventoryPage (userId: {userId})</div>
  ),
}));

vi.mock('../MemorySearch', () => ({
  default: ({ userId }: { userId: string }) => (
    <div data-testid="memory-search">MemorySearch (userId: {userId})</div>
  ),
}));

vi.mock('../ProfileForm', () => ({
  default: ({ userId }: { userId: string }) => (
    <div data-testid="profile-form">ProfileForm (userId: {userId})</div>
  ),
}));

// ─── 分组 A：导航标签 ────────────────────────────────────────

describe('App — 导航标签', () => {
  it('A1. 渲染所有 4 个标签（不含菜谱推荐）', () => {
    render(<App />);

    expect(screen.getByRole('button', { name: '💬 对话' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '📦 库存管理' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '🧠 模型记忆' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '🩺 健康档案' })).toBeInTheDocument();
  });

  it('A2. 「菜谱推荐」标签不存在', () => {
    render(<App />);
    expect(screen.queryByRole('button', { name: /菜谱推荐/ })).toBeNull();
    expect(screen.queryByText('🍽️ 菜谱推荐')).toBeNull();
  });

  it('A3. 默认激活「对话」标签，渲染 ConversationPage', () => {
    render(<App />);
    expect(screen.getByTestId('conversation-page')).toBeInTheDocument();
  });
});

// ─── 分组 B：标签切换 ────────────────────────────────────────

describe('App — 标签切换', () => {
  it('B1. 点击各标签切换到对应组件', () => {
    render(<App />);

    fireEvent.click(screen.getByRole('button', { name: '📦 库存管理' }));
    expect(screen.getByTestId('inventory-page')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '🧠 模型记忆' }));
    expect(screen.getByTestId('memory-search')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '🩺 健康档案' }));
    expect(screen.getByTestId('profile-form')).toBeInTheDocument();
  });
});
// ─── 分组 C：用户 ID 选择器 ──────────────────────────────────

describe('App — 用户 ID 选择器', () => {
  it('C1. 右上角显示用户 ID 下拉和可编辑按钮', () => {
    render(<App />);

    // 下拉选择器存在
    const select = screen.getByRole('combobox');
    expect(select).toBeInTheDocument();
    expect(select).toHaveValue('user-001');

    // 当前用户 ID 按钮存在（可点击编辑）
    expect(screen.getByTitle('点击修改用户 ID')).toBeInTheDocument();
  });

  it('C2. 下拉切换 user_id 后传递到子组件', () => {
    render(<App />);

    const select = screen.getByRole('combobox');
    fireEvent.change(select, { target: { value: 'test-inv-only-001' } });

    // ConversationPage 应该收到新 userId
    expect(screen.getByTestId('conversation-page')).toHaveTextContent(
      'userId: test-inv-only-001'
    );
  });

  it('C3. 点击用户 ID 按钮进入编辑模式', () => {
    render(<App />);

    // 点击当前 userId 按钮
    fireEvent.click(screen.getByTitle('点击修改用户 ID'));

    // 输入框应该出现
    const input = screen.getByPlaceholderText('输入用户 ID');
    expect(input).toBeInTheDocument();
  });
});