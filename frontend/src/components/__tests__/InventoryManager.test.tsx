import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import InventoryManager from '../InventoryManager';
import { inventoryAPI } from '../../services/api';

vi.mock('../../services/api', () => ({
  inventoryAPI: {
    list: vi.fn(),
    expiring: vi.fn(),
    create: vi.fn(),
    adjust: vi.fn(),
  },
}));

describe('InventoryManager', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it('shows empty state when no inventory', async () => {
    vi.mocked(inventoryAPI.list).mockResolvedValue({ data: [] } as never);
    vi.mocked(inventoryAPI.expiring).mockResolvedValue({ data: [] } as never);

    render(<InventoryManager userId="u-1" itemType="ingredient" />);

    await waitFor(() => {
      expect(screen.getByText('暂无食材，请添加')).toBeInTheDocument();
    });
  });

  it('disables submit button when create form is invalid', async () => {
    vi.mocked(inventoryAPI.list).mockResolvedValue({ data: [] } as never);
    vi.mocked(inventoryAPI.expiring).mockResolvedValue({ data: [] } as never);

    render(<InventoryManager userId="u-1" itemType="ingredient" />);

    const nameInput = screen.getByPlaceholderText('食材名称');
    fireEvent.change(nameInput, { target: { value: '' } });

    const submitButton = screen.getByRole('button', { name: '添加食材' });
    expect(submitButton).toBeDisabled();
  });
});
