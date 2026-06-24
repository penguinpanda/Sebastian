import { useState } from 'react';
import InventoryManager from './InventoryManager';

interface Props {
  userId: string;
}

type SubTab = 'ingredient' | 'equipment';

export default function InventoryPage({ userId }: Props) {
  const [subTab, setSubTab] = useState<SubTab>('ingredient');

  return (
    <div className="space-y-4">
      {/* 子标签导航 */}
      <div className="flex border-b border-gray-200">
        <button
          onClick={() => setSubTab('ingredient')}
          className={`px-6 py-3 whitespace-nowrap border-b-2 transition-colors text-sm font-medium ${
            subTab === 'ingredient'
              ? 'border-green-600 text-green-600'
              : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          🥬 食材
        </button>
        <button
          onClick={() => setSubTab('equipment')}
          className={`px-6 py-3 whitespace-nowrap border-b-2 transition-colors text-sm font-medium ${
            subTab === 'equipment'
              ? 'border-green-600 text-green-600'
              : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          🔪 厨具
        </button>
      </div>

      {/* 子页面内容 */}
      {subTab === 'ingredient' && <InventoryManager userId={userId} itemType="ingredient" />}
      {subTab === 'equipment' && <InventoryManager userId={userId} itemType="equipment" />}
    </div>
  );
}
