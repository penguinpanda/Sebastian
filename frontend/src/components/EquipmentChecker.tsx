import React, { useState } from 'react';
import { mcpAPI } from '../services/api';
import { DEFAULT_EQUIPMENT_FORM } from '../data/defaultTestData';
import { EquipmentCheckResponse } from '../types';
import ErrorState from './common/ErrorState';
import { getFriendlyError } from '../services/error';

interface Props {
  userId: string;
}

export default function EquipmentChecker({ userId: _userId }: Props) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [result, setResult] = useState<EquipmentCheckResponse | null>(null);
  const [error, setError] = useState('');
  const [owned, setOwned] = useState<string>(DEFAULT_EQUIPMENT_FORM.owned);
  const [required, setRequired] = useState<string>(DEFAULT_EQUIPMENT_FORM.required);

  const ownedList = owned
    .split(/[,，]/)
    .map((s) => s.trim())
    .filter((s) => s.length > 0);
  const requiredList = required
    .split(/[,，]/)
    .map((s) => s.trim())
    .filter((s) => s.length > 0);
  const isFormValid = ownedList.length > 0 && requiredList.length > 0;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setError('');

    if (!isFormValid) {
      setError('已拥有厨具和所需厨具都不能为空');
      setIsSubmitting(false);
      return;
    }

    try {
      const res = await mcpAPI.equipmentCheck({
        user_id: _userId || 'anonymous',
        input: {
          equipment_owned: ownedList,
          required_equipment: requiredList,
        },
      });
      setResult(res.data.result);
    } catch (err: unknown) {
      setError(getFriendlyError(err, '厨具检查失败'));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* 输入表单 */}
      <div className="card">
        <h2 className="text-xl font-bold mb-4">🔪 厨具检查</h2>
        {error && <ErrorState message={error} className="mb-4" />}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block font-medium mb-2">已拥有的厨具 (逗号分隔)</label>
            <textarea
              value={owned}
              onChange={(e) => setOwned(e.target.value)}
              placeholder="例：平底锅,砂锅,刀,砧板,微波炉"
              className="input w-full"
              rows={3}
            />
            <p className="text-xs text-gray-500 mt-1">提示：使用逗号或中文逗号分隔</p>
          </div>

          <div>
            <label className="block font-medium mb-2">所需的厨具 (逗号分隔)</label>
            <textarea
              value={required}
              onChange={(e) => setRequired(e.target.value)}
              placeholder="例：平底锅,烤箱,高压锅"
              className="input w-full"
              rows={3}
            />
            <p className="text-xs text-gray-500 mt-1">提示：输入菜谱或某道菜需要的厨具</p>
          </div>

          <button type="submit" className="btn btn-primary w-full" disabled={isSubmitting || !isFormValid}>
            {isSubmitting ? '检查中...' : '检查可行性'}
          </button>
        </form>
      </div>

      {/* 检查结果 */}
      {result && (
        <div
          className={`card border-2 ${
            result.feasible ? 'border-green-200 bg-green-50' : 'border-red-200 bg-red-50'
          }`}
        >
          <div className="mb-4">
            <h2 className="text-2xl font-bold mb-2">
              {result.feasible ? '✅ 可以做！' : '❌ 暂时无法做'}
            </h2>
            <p className={`text-lg ${result.feasible ? 'text-green-700' : 'text-red-700'}`}>
              {result.suggestion}
            </p>
          </div>

          {result.missing_equipment.length > 0 && (
            <div className="bg-white p-4 rounded">
              <h3 className="font-semibold mb-2 text-orange-600">缺少的厨具</h3>
              <ul className="space-y-1">
                {result.missing_equipment.map((item, i) => (
                  <li key={i} className="flex items-center gap-2">
                    <span className="text-lg">🔴</span>
                    <span className="font-medium">{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {result._audit?.trace_id && (
            <div className="pt-3 border-t mt-3">
              <p className="text-xs text-gray-500">
                trace_id: <span className="font-mono">{result._audit.trace_id}</span>
              </p>
            </div>
          )}
        </div>
      )}

      {/* 常见厨具列表 */}
      <div className="card">
        <h3 className="font-semibold mb-3">📌 常见厨具参考</h3>
        <div className="grid grid-cols-2 gap-2 text-sm">
          {[
            '平底锅',
            '砂锅',
            '高压锅',
            '烤箱',
            '微波炉',
            '电饭煲',
            '豆浆机',
            '榨汁机',
            '刀',
            '砧板',
            '锅铲',
            '漏勺',
          ].map((item) => (
            <div key={item} className="bg-gray-50 p-2 rounded">
              {item}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
