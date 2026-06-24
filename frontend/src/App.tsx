import { useState, useEffect, useRef } from 'react';
import InventoryPage from './components/InventoryPage';
import ConversationPage from './components/ConversationPage';
import MemorySearch from './components/MemorySearch';
import ProfileForm from './components/ProfileForm';
import RegisterPage from './components/RegisterPage';
import { DEFAULT_TEST_USER_ID } from './data/defaultTestData';

type Tab = 'chat' | 'inventory' | 'memory' | 'profile';

const STORAGE_KEY = 'sebastian_user_id';
const REGISTERED_KEY = 'sebastian_registered';

// 预置用户 ID
const PRESET_USER_IDS = [
  DEFAULT_TEST_USER_ID,
  'test-happy-001',
];

function loadSavedUserId(): string {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved && saved.trim()) return saved.trim();
  } catch { /* localStorage 不可用时忽略 */ }
  return DEFAULT_TEST_USER_ID;
}

function saveUserId(id: string) {
  try { localStorage.setItem(STORAGE_KEY, id); } catch { /* ignore */ }
}

function loadRegisteredUser(): { userId: string } | null {
  try {
    const raw = localStorage.getItem(REGISTERED_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (parsed?.userId && typeof parsed.userId === 'string') return parsed;
    }
  } catch { /* ignore */ }
  return null;
}

function saveRegisteredUser(userId: string) {
  try {
    localStorage.setItem(REGISTERED_KEY, JSON.stringify({ userId, timestamp: Date.now() }));
  } catch { /* ignore */ }
}

function clearRegisteredUser() {
  try { localStorage.removeItem(REGISTERED_KEY); } catch { /* ignore */ }
}

export default function App() {
  const [activeTab, setActiveTab] = useState<Tab>('chat');
  const [userId, setUserId] = useState(() => {
    // 已注册用户优先使用注册时的 userId
    const reg = loadRegisteredUser();
    return reg?.userId || loadSavedUserId();
  });
  const [editingUserId, setEditingUserId] = useState(false);
  const [draftUserId, setDraftUserId] = useState(userId);
  const inputRef = useRef<HTMLInputElement>(null);

  // 注册状态
  const registered = loadRegisteredUser();
  const [isRegistered, setIsRegistered] = useState(!!registered);

  // userId 变更时持久化
  useEffect(() => {
    saveUserId(userId);
  }, [userId]);

  // 进入编辑模式时自动聚焦
  useEffect(() => {
    if (editingUserId && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [editingUserId]);

  const applyUserId = (id: string) => {
    const trimmed = id.trim();
    if (trimmed && trimmed.length <= 64) {
      setUserId(trimmed);
      setDraftUserId(trimmed);
    }
    setEditingUserId(false);
  };

  const handleUserIdKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') applyUserId(draftUserId);
    if (e.key === 'Escape') {
      setDraftUserId(userId);
      setEditingUserId(false);
    }
  };

  const tabs: Array<{ id: Tab; label: string; icon: string }> = [
    { id: 'chat', label: '对话', icon: '💬' },
    { id: 'inventory', label: '库存管理', icon: '📦' },
    { id: 'memory', label: '模型记忆', icon: '🧠' },
    { id: 'profile', label: '健康档案', icon: '🩺' },
  ];

  // 注册完成回调
  const handleRegisterComplete = (newUserId: string) => {
    saveRegisteredUser(newUserId);
    saveUserId(newUserId);
    setUserId(newUserId);
    setIsRegistered(true);
  };

  // 退出登录
  const handleLogout = () => {
    clearRegisteredUser();
    setIsRegistered(false);
    setUserId(DEFAULT_TEST_USER_ID);
  };

  // 未注册 → 显示注册页
  if (!isRegistered) {
    return <RegisterPage onRegisterComplete={handleRegisterComplete} />;
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      {/* 头部：左侧品牌 + 右侧用户 ID */}
      <header className="bg-white shadow">
        <div className="max-w-6xl mx-auto px-4 py-4 flex items-center justify-between flex-wrap gap-3">
          {/* 左侧品牌 */}
          <div>
            <h1 className="text-2xl font-bold text-gray-800">🤖 Sebastian</h1>
            <p className="text-sm text-gray-500 mt-1">个人生活与厨房 AI 助手系统</p>
          </div>

          {/* 右侧用户 ID 选择器 */}
          <div className="flex items-center gap-2">
            <label className="text-sm font-medium text-gray-600 whitespace-nowrap">
              👤 用户
            </label>
            {editingUserId ? (
              <div className="flex items-center gap-1">
                <input
                  ref={inputRef}
                  type="text"
                  value={draftUserId}
                  onChange={(e) => setDraftUserId(e.target.value)}
                  onKeyDown={handleUserIdKeyDown}
                  onBlur={() => applyUserId(draftUserId)}
                  placeholder="输入用户 ID"
                  maxLength={64}
                  className="w-40 px-2 py-1 text-sm border border-blue-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-400"
                />
              </div>
            ) : (
              <button
                onClick={() => { setDraftUserId(userId); setEditingUserId(true); }}
                className="px-3 py-1 text-sm font-mono bg-gray-100 hover:bg-gray-200 rounded border border-gray-300 transition-colors max-w-[200px] truncate"
                title="点击修改用户 ID"
              >
                {userId}
              </button>
            )}

            {/* 快速切换下拉 */}
            <select
              value={userId}
              onChange={(e) => applyUserId(e.target.value)}
              className="px-2 py-1 text-sm border border-gray-300 rounded bg-white hover:border-blue-400 focus:outline-none focus:ring-1 focus:ring-blue-400 cursor-pointer max-w-[160px] truncate"
              title="快速切换预置用户"
            >
              {PRESET_USER_IDS.map((id) => (
                <option key={id} value={id}>{id}</option>
              ))}
              {!PRESET_USER_IDS.includes(userId) && (
                <option value={userId}>{userId}</option>
              )}
            </select>

            {/* 退出登录 */}
            <button
              onClick={handleLogout}
              className="px-3 py-1 text-sm text-gray-500 hover:text-red-600 hover:bg-red-50 rounded border border-gray-200 hover:border-red-300 transition-colors whitespace-nowrap"
              title="退出登录，回到注册页"
            >
              🚪 退出
            </button>
          </div>
        </div>
      </header>

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
        {activeTab === 'inventory' && <InventoryPage userId={userId} />}
        {activeTab === 'memory' && <MemorySearch userId={userId} />}
        {activeTab === 'profile' && <ProfileForm userId={userId} />}
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
