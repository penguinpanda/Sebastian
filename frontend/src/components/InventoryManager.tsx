import React, { useState, useEffect } from 'react';
import { inventoryAPI } from '../services/api';
import { DEFAULT_INVENTORY_ITEM } from '../data/defaultTestData';
import { Inventory, ExpiringInventory } from '../types';
import ErrorState from './common/ErrorState';
import LoadingState from './common/LoadingState';
import EmptyState from './common/EmptyState';
import { getFriendlyError } from '../services/error';

interface Props {
  userId: string;
}

export default function InventoryManager({ userId }: Props) {
  // 列表、临期提醒和表单状态拆开管理，避免一次操作误触发不相关的加载态。
  const [inventories, setInventories] = useState<Inventory[]>([]);
  const [expiring, setExpiring] = useState<ExpiringInventory[]>([]);
  const [isListLoading, setIsListLoading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [newItem, setNewItem] = useState(DEFAULT_INVENTORY_ITEM);
  const [adjustingIds, setAdjustingIds] = useState<Set<string>>(new Set());
  const [deletingIds, setDeletingIds] = useState<Set<string>>(new Set());

  const isCreateFormValid =
    newItem.name.trim().length > 0 &&
    newItem.unit.trim().length > 0 &&
    Number.isFinite(newItem.quantity) &&
    newItem.quantity > 0 &&
    newItem.expire_date.trim().length > 0;

  const fetchData = async () => {
    setIsListLoading(true);
    setError('');
    try {
      // 库存列表是首屏主内容，先显示它；临期提醒慢或失败时不阻塞列表渲染。
      const listRes = await inventoryAPI.list(userId);
      setInventories(listRes.data);
    } catch (err: unknown) {
      setError(getFriendlyError(err, '库存加载失败'));
    } finally {
      setIsListLoading(false);
    }

    try {
      const expiringRes = await inventoryAPI.expiring(7, userId);
      setExpiring(expiringRes.data);
    } catch {
      setExpiring([]);
    }
  };

  useEffect(() => {
    // userId 变化时重新拉取数据，为后续多用户隔离预留入口。
    fetchData();
  }, [userId]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isCreateFormValid) {
      setError('请完整填写食材名称、数量、单位和过期日期，且数量必须大于 0');
      return;
    }

    setIsSubmitting(true);
    try {
      await inventoryAPI.create({ ...newItem, user_id: userId });
      // 创建成功后重置表单并刷新列表，确保临期提醒也同步更新。
      setNewItem(DEFAULT_INVENTORY_ITEM);
      setError('');
      await fetchData();
    } catch (err: unknown) {
      setError(getFriendlyError(err, '创建食材失败'));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleAdjust = async (id: string, delta: number) => {
    if (adjustingIds.has(id) || deletingIds.has(id)) {
      return;
    }

    setAdjustingIds((prev) => new Set(prev).add(id));
    try {
      // 使用 Set 记录行级操作状态，避免调整某一行时锁住整张表。
      await inventoryAPI.adjust(id, delta);
      await fetchData();
    } catch (err: unknown) {
      setError(getFriendlyError(err, '调整库存失败'));
    } finally {
      setAdjustingIds((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    }
  };

  const handleDelete = async (id: string, name: string) => {
    if (deletingIds.has(id) || adjustingIds.has(id)) {
      return;
    }

    const confirmed = window.confirm(`确认删除食材: ${name} ?`);
    if (!confirmed) {
      return;
    }

    setDeletingIds((prev) => new Set(prev).add(id));
    try {
      await inventoryAPI.remove(id);
      await fetchData();
    } catch (err: unknown) {
      setError(getFriendlyError(err, '删除库存失败'));
    } finally {
      setDeletingIds((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    }
  };

  return (
    <div className="space-y-6">
      {/* 新增食材 */}
      <div className="card">
        <h2 className="text-xl font-bold mb-4">➕ 添加新食材</h2>
        {error && <ErrorState message={error} className="mb-4" />}
        <form onSubmit={handleCreate} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <input
              type="text"
              placeholder="食材名称"
              value={newItem.name}
              onChange={(e) => setNewItem({ ...newItem, name: e.target.value })}
              className="input"
            />
            <input
              type="number"
              placeholder="数量"
              value={newItem.quantity}
              onChange={(e) => {
                const quantity = parseFloat(e.target.value);
                setNewItem({ ...newItem, quantity: Number.isFinite(quantity) ? quantity : 0 });
              }}
              className="input"
              min={0.1}
              step={0.1}
            />
            <input
              type="text"
              placeholder="单位（个、斤、盒等）"
              value={newItem.unit}
              onChange={(e) => setNewItem({ ...newItem, unit: e.target.value })}
              className="input"
            />
            <input
              type="date"
              value={newItem.expire_date}
              onChange={(e) => setNewItem({ ...newItem, expire_date: e.target.value })}
              className="input"
            />
            <textarea
              placeholder="备注（可选）"
              value={newItem.note}
              onChange={(e) => setNewItem({ ...newItem, note: e.target.value })}
              className="input col-span-2"
              rows={2}
            />
          </div>
          <button type="submit" className="btn btn-primary w-full" disabled={isSubmitting || !isCreateFormValid}>
            {isSubmitting ? '提交中...' : '添加食材'}
          </button>
        </form>
      </div>

      {/* 临期提醒 */}
      {expiring.length > 0 && (
        <div className="card bg-orange-50 border-2 border-orange-200">
          <h2 className="text-xl font-bold mb-4 text-orange-800">⚠️ 7天内即将过期</h2>
          <div className="space-y-2">
            {expiring.map((item) => (
              <div key={item.id} className="bg-white p-3 rounded flex justify-between items-center">
                <div>
                  <p className="font-semibold">{item.name}</p>
                  <p className="text-sm text-gray-600">
                    {item.quantity} {item.unit} • 剩余 {item.days_left} 天
                  </p>
                </div>
                <span className="text-lg font-bold text-orange-600">{item.days_left}d</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 库存列表 */}
      <div className="card">
        <h2 className="text-xl font-bold mb-4">📋 当前库存</h2>
        {isListLoading ? (
          <LoadingState text="库存加载中..." />
        ) : inventories.length === 0 ? (
          <EmptyState text="暂无库存，请添加食材" />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b">
                  <th className="text-left py-2">食材</th>
                  <th className="text-center py-2">数量</th>
                  <th className="text-center py-2">过期日期</th>
                  <th className="text-center py-2">操作</th>
                </tr>
              </thead>
              <tbody>
                {inventories.map((item) => (
                  <tr key={item.id} className="border-b hover:bg-gray-50">
                    <td className="py-3">
                      <p className="font-semibold">{item.name}</p>
                      {item.note && <p className="text-xs text-gray-500">{item.note}</p>}
                    </td>
                    <td className="text-center">{item.quantity} {item.unit}</td>
                    <td className="text-center text-sm">{item.expire_date}</td>
                    <td className="text-center space-x-2">
                      <button
                        onClick={() => handleAdjust(item.id, -1)}
                        className="btn btn-secondary px-2 py-1 text-xs"
                        disabled={adjustingIds.has(item.id) || deletingIds.has(item.id) || item.quantity <= 0}
                      >
                        -
                      </button>
                      <button
                        onClick={() => handleAdjust(item.id, 1)}
                        className="btn btn-primary px-2 py-1 text-xs"
                        disabled={adjustingIds.has(item.id) || deletingIds.has(item.id)}
                      >
                        +
                      </button>
                      <button
                        onClick={() => handleDelete(item.id, item.name)}
                        className="btn px-2 py-1 text-xs bg-red-600 hover:bg-red-700 text-white"
                        disabled={deletingIds.has(item.id) || adjustingIds.has(item.id)}
                      >
                        删
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
