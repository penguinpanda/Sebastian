import { useState } from 'react';
import InventoryManager from './components/InventoryManager';
import ConversationPage from './components/ConversationPage';
import RecipeRecommender from './components/RecipeRecommender';
import HealthAnalyzer from './components/HealthAnalyzer';
import EquipmentChecker from './components/EquipmentChecker';
import MemorySearch from './components/MemorySearch';
import { DEFAULT_TEST_USER_ID } from './data/defaultTestData';

type Tab = 'chat' | 'inventory' | 'recipe' | 'health' | 'equipment' | 'memory';

export default function App() {
  // App 只负责全局导航和 userId 传递，具体业务交给各个功能组件处理。
  const [activeTab, setActiveTab] = useState<Tab>('chat');
  const [userId, setUserId] = useState(DEFAULT_TEST_USER_ID);
  const [showUserInput, setShowUserInput] = useState(true);

  // tabs 是页面功能入口的单一配置源，新增模块时只需要扩展这里和下方渲染分支。
  const tabs: Array<{ id: Tab; label: string; icon: string }> = [
    { id: 'chat', label: '对话', icon: '💬' },
    { id: 'inventory', label: '库存管理', icon: '📦' },
    { id: 'recipe', label: '菜谱推荐', icon: '🍽️' },
    { id: 'health', label: '健康分析', icon: '💪' },
    { id: 'equipment', label: '厨具检查', icon: '🔪' },
    { id: 'memory', label: '模型记忆', icon: '🧠' },
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      {/* 头部 */}
      <header className="bg-white shadow">
        <div className="max-w-6xl mx-auto px-4 py-6">
          <h1 className="text-3xl font-bold text-gray-800">🤖 Sebastian</h1>
          <p className="text-gray-600 mt-2">个人生活与厨房 AI 助手系统</p>
        </div>
      </header>

      {/* 用户 ID 输入 */}
      {showUserInput && (
        <div className="bg-blue-50 border-b-2 border-blue-200 px-4 py-4">
          <div className="max-w-6xl mx-auto flex items-center gap-4">
            <label className="font-medium text-gray-700">用户 ID：</label>
            <input
              type="text"
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
              placeholder="输入用户 ID（如 user-001）"
              className="input flex-1"
            />
            <button
              onClick={() => setShowUserInput(false)}
              className="btn btn-primary"
            >
              确认
            </button>
          </div>
        </div>
      )}

      {/* 标签导航 */}
      <nav className="bg-white border-b sticky top-0 z-10">
        <div className="max-w-6xl mx-auto">
          <div className="flex overflow-x-auto">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`px-6 py-4 whitespace-nowrap border-b-2 transition-colors ${
                  activeTab === tab.id
                    ? 'border-blue-600 text-blue-600 font-semibold'
                    : 'border-transparent text-gray-700 hover:text-gray-900'
                }`}
              >
                {tab.icon} {tab.label}
              </button>
            ))}
          </div>
        </div>
      </nav>

      {/* 内容区域 */}
      <main className="max-w-6xl mx-auto px-4 py-8">
        {activeTab === 'chat' && <ConversationPage userId={userId} />}
        {activeTab === 'inventory' && <InventoryManager userId={userId} />}
        {activeTab === 'recipe' && <RecipeRecommender userId={userId} />}
        {activeTab === 'health' && <HealthAnalyzer userId={userId} />}
        {activeTab === 'equipment' && <EquipmentChecker userId={userId} />}
        {activeTab === 'memory' && <MemorySearch userId={userId} />}
      </main>

      {/* 页脚 */}
      <footer className="bg-gray-800 text-white mt-12 py-8">
        <div className="max-w-6xl mx-auto px-4 text-center">
          <p>Sebastian MVP © 2026 | 后端: http://127.0.0.1:8000</p>
          <p className="text-gray-400 mt-2 text-sm">
            提示：确保后端 API 服务已启动
          </p>
        </div>
      </footer>
    </div>
  );
}
