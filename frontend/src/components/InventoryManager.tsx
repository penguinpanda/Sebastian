import React, { useState, useEffect, useMemo } from 'react';
import { inventoryAPI } from '../services/api';
import { DEFAULT_INVENTORY_ITEM } from '../data/defaultTestData';
import { Inventory, ExpiringInventory } from '../types';
import ErrorState from './common/ErrorState';
import LoadingState from './common/LoadingState';
import EmptyState from './common/EmptyState';
import { getFriendlyError } from '../services/error';

interface Props {
  userId: string;
  itemType: 'ingredient' | 'equipment';
}

const LABELS: Record<'ingredient' | 'equipment', {
  pageTitle: string;
  addTitle: string;
  namePlaceholder: string;
  unitPlaceholder: string;
  createBtn: string;
  listTitle: string;
  emptyText: string;
  tableNameCol: string;
  tableItemLabel: string;
  deleteConfirm: string;
  createError: string;
  loadError: string;
  adjustError: string;
  deleteError: string;
  createValidation: string;
}> = {
  ingredient: {
    pageTitle: '食材管理',
    addTitle: '➕ 添加新食材',
    namePlaceholder: '食材名称',
    unitPlaceholder: '单位（个、斤、盒等）',
    createBtn: '添加食材',
    listTitle: '📋 当前食材',
    emptyText: '暂无食材，请添加',
    tableNameCol: '食材',
    tableItemLabel: '食材',
    deleteConfirm: '确认删除食材',
    createError: '创建食材失败',
    loadError: '食材加载失败',
    adjustError: '调整食材失败',
    deleteError: '删除食材失败',
    createValidation: '请完整填写食材名称、数量、单位和过期日期，且数量必须大于 0',
  },
  equipment: {
    pageTitle: '厨具管理',
    addTitle: '🔪 添加新厨具',
    namePlaceholder: '厨具名称',
    unitPlaceholder: '单位（个、台、套等）',
    createBtn: '添加厨具',
    listTitle: '🔪 当前厨具',
    emptyText: '暂无厨具，请添加',
    tableNameCol: '厨具',
    tableItemLabel: '厨具',
    deleteConfirm: '确认删除厨具',
    createError: '创建厨具失败',
    loadError: '厨具加载失败',
    adjustError: '调整厨具失败',
    deleteError: '删除厨具失败',
    createValidation: '请完整填写厨具名称、数量和单位，且数量必须大于 0',
  },
};

export default function InventoryManager({ userId, itemType }: Props) {
  const labels = LABELS[itemType];
  const isIngredient = itemType === 'ingredient';

  // 列表、临期提醒和表单状态拆开管理，避免一次操作误触发不相关的加载态。
  const [inventories, setInventories] = useState<Inventory[]>([]);
  const [expiring, setExpiring] = useState<ExpiringInventory[]>([]);
  const [isListLoading, setIsListLoading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');

  const defaultForm = useMemo(() => ({
    ...DEFAULT_INVENTORY_ITEM,
    item_type: itemType,
    name: isIngredient ? DEFAULT_INVENTORY_ITEM.name : '电饭锅',
    quantity: isIngredient ? DEFAULT_INVENTORY_ITEM.quantity : 1,
    unit: isIngredient ? DEFAULT_INVENTORY_ITEM.unit : '个',
    note: isIngredient ? DEFAULT_INVENTORY_ITEM.note : '',
    expire_date: isIngredient
      ? DEFAULT_INVENTORY_ITEM.expire_date
      : new Date(Date.now() + 365 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
  }), [itemType, isIngredient]);

  const [newItem, setNewItem] = useState(defaultForm);
  const [adjustingIds, setAdjustingIds] = useState<Set<string>>(new Set());
  const [deletingIds, setDeletingIds] = useState<Set<string>>(new Set());

  // 当 itemType 变化时重置表单
  useEffect(() => {
    setNewItem(defaultForm);
  }, [defaultForm]);

  const isCreateFormValid =
    newItem.name.trim().length > 0 &&
    newItem.unit.trim().length > 0 &&
    Number.isFinite(newItem.quantity) &&
    newItem.quantity > 0 &&
    (isIngredient ? newItem.expire_date.trim().length > 0 : true);

  const fetchData = async () => {
    setIsListLoading(true);
    setError('');
    try {
      const listRes = await inventoryAPI.list(userId, itemType);
      setInventories(listRes.data);
    } catch (err: unknown) {
      setError(getFriendlyError(err, labels.loadError));
    } finally {
      setIsListLoading(false);
    }

    // 厨具不过期，不需要加载临期提醒
    if (isIngredient) {
      try {
        const expiringRes = await inventoryAPI.expiring(7, userId, itemType);
        setExpiring(expiringRes.data);
      } catch {
        setExpiring([]);
      }
    }
  };

  useEffect(() => {
    fetchData();
  }, [userId, itemType]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isCreateFormValid) {
      setError(labels.createValidation);
      return;
    }

    setIsSubmitting(true);
    try {
      await inventoryAPI.create({ ...newItem, user_id: userId, item_type: itemType });
      setNewItem(defaultForm);
      setError('');
      await fetchData();
    } catch (err: unknown) {
      setError(getFriendlyError(err, labels.createError));
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
      await inventoryAPI.adjust(id, delta);
      await fetchData();
    } catch (err: unknown) {
      setError(getFriendlyError(err, labels.adjustError));
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

    const confirmed = window.confirm(`${labels.deleteConfirm}: ${name} ?`);
    if (!confirmed) {
      return;
    }

    setDeletingIds((prev) => new Set(prev).add(id));
    try {
      await inventoryAPI.remove(id);
      await fetchData();
    } catch (err: unknown) {
      setError(getFriendlyError(err, labels.deleteError));
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
      {/* 新增 */}
      <div className="card">
        <h2 className="text-xl font-bold mb-4">{labels.addTitle}</h2>
        {error && <ErrorState message={error} className="mb-4" />}
        <form onSubmit={handleCreate} className="space-y-3">
          {/* 第一行：名称 + 数量 + 单位 */}
          <div className="grid grid-cols-3 gap-3">
            <input
              type="text"
              placeholder={labels.namePlaceholder}
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
              placeholder={labels.unitPlaceholder}
              value={newItem.unit}
              onChange={(e) => setNewItem({ ...newItem, unit: e.target.value })}
              className="input"
            />
          </div>
          {/* 第二行：日期（仅食材） */}
          {isIngredient && (
            <input
              type="date"
              value={newItem.expire_date}
              onChange={(e) => setNewItem({ ...newItem, expire_date: e.target.value })}
              className="input w-full"
            />
          )}
          {/* 第三行：备注 */}
          <textarea
            placeholder="备注（可选）"
            value={newItem.note}
            onChange={(e) => setNewItem({ ...newItem, note: e.target.value })}
            className="input w-full"
            rows={2}
          />
          <button type="submit" className="btn btn-primary w-full" disabled={isSubmitting || !isCreateFormValid}>
            {isSubmitting ? '提交中...' : labels.createBtn}
          </button>
        </form>
      </div>

      {/* 临期提醒 — 仅食材 */}
      {isIngredient && expiring.length > 0 && (
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
        <h2 className="text-xl font-bold mb-4">{labels.listTitle}</h2>
        {isListLoading ? (
          <LoadingState text="加载中..." />
        ) : inventories.length === 0 ? (
          <EmptyState text={labels.emptyText} />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b">
                  <th className="text-left py-2">{labels.tableNameCol}</th>
                  <th className="text-center py-2">数量</th>
                  {isIngredient && <th className="text-center py-2">过期日期</th>}
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
                    {isIngredient && <td className="text-center text-sm">{item.expire_date}</td>}
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
