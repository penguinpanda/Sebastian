import React, { useEffect, useState } from 'react';
import { mcpAPI, memoryAPI } from '../services/api';
import { MemoryHit, SearchAnswerResponse } from '../types';
import ErrorState from './common/ErrorState';
import EmptyState from './common/EmptyState';
import LoadingState from './common/LoadingState';
import { getFriendlyError } from '../services/error';

interface Props {
  userId: string;
}

export default function MemorySearch({ userId }: Props) {
  const [saveLoading, setSaveLoading] = useState(false);
  const [searchLoading, setSearchLoading] = useState(false);
  const [memoryListLoading, setMemoryListLoading] = useState(false);
  const [error, setError] = useState('');
  const [memoryListError, setMemoryListError] = useState('');
  const [successMessage, setSuccessMessage] = useState('');
  const [result, setResult] = useState<SearchAnswerResponse | null>(null);
  const [memories, setMemories] = useState<MemoryHit[]>([]);
  const [deletingMemoryIds, setDeletingMemoryIds] = useState<Set<string>>(new Set());

  const [saveForm, setSaveForm] = useState({
    memory_type: 'profile',
    content: '',
    tags: '',
    importance: 0.5,
  });

  const [searchForm, setSearchForm] = useState({
    query: '',
    retrieval_mode: 'hybrid' as const,
  });

  const fetchMemories = async () => {
    setMemoryListLoading(true);
    setMemoryListError('');
    try {
      const res = await memoryAPI.list(userId, 50);
      setMemories(res.data);
    } catch (err: unknown) {
      setMemoryListError(getFriendlyError(err, '记忆列表加载失败'));
    } finally {
      setMemoryListLoading(false);
    }
  };

  useEffect(() => {
    fetchMemories();
  }, [userId]);

  const formatMemoryTime = (value?: string | null) => {
    if (!value) {
      return '未知时间';
    }

    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return value;
    }

    return date.toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const memoryTypeLabel: Record<string, string> = {
    profile: '个人资料',
    preference: '偏好',
    profile_preference: '健康档案与偏好',
    allergy: '过敏/禁忌',
    history: '历史信息',
    other: '其他',
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaveLoading(true);
    setError('');
    setSuccessMessage('');

    if (!saveForm.content.trim()) {
      setError('记忆内容不能为空');
      setSaveLoading(false);
      return;
    }

    try {
      await memoryAPI.save({
        user_id: userId,
        memory_type: saveForm.memory_type,
        content: saveForm.content,
        tags: saveForm.tags
          .split(/[,，]/)
          .map((t) => t.trim())
          .filter((t) => t),
        importance: parseFloat(saveForm.importance.toString()),
      });

      setSaveForm({
        memory_type: 'profile',
        content: '',
        tags: '',
        importance: 0.5,
      });
      setError('');
      setSuccessMessage('记忆已保存');
      await fetchMemories();
    } catch (err: unknown) {
      setError(getFriendlyError(err, '记忆保存失败'));
    } finally {
      setSaveLoading(false);
    }
  };

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    setSearchLoading(true);
    setError('');
    setSuccessMessage('');

    if (!searchForm.query.trim()) {
      setError('搜索问题不能为空');
      setSearchLoading(false);
      return;
    }

    try {
      const res = await mcpAPI.searchAnswer({
        user_id: userId,
        input: {
          user_id: userId,
          query: searchForm.query.trim(),
        },
      });
      setResult(res.data.result);
    } catch (err: unknown) {
      setError(getFriendlyError(err, '记忆搜索失败'));
    } finally {
      setSearchLoading(false);
    }
  };

  const handleDeleteMemory = async (memoryId: string) => {
    if (deletingMemoryIds.has(memoryId)) {
      return;
    }

    const confirmed = window.confirm('确认删除这条记忆吗？');
    if (!confirmed) {
      return;
    }

    setDeletingMemoryIds((prev) => new Set(prev).add(memoryId));
    setError('');
    setSuccessMessage('');
    try {
      await memoryAPI.remove(memoryId, userId);
      setMemories((prev) => prev.filter((memory) => memory.memory_id !== memoryId));
      setSuccessMessage('记忆已删除');
    } catch (err: unknown) {
      setError(getFriendlyError(err, '记忆删除失败'));
    } finally {
      setDeletingMemoryIds((prev) => {
        const next = new Set(prev);
        next.delete(memoryId);
        return next;
      });
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-800">模型记忆</h2>
        <p className="text-sm text-gray-600 mt-1">按时间显示已添加的记忆，最新记录排在最前面。</p>
      </div>

      {error && <ErrorState message={error} />}
      {successMessage && (
        <div className="bg-green-50 text-green-700 p-3 rounded border border-green-200">{successMessage}</div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
        <div className="space-y-6">
          {/* 保存记忆 */}
          <div className="card">
            <h2 className="text-xl font-bold mb-4">保存个人记忆</h2>
            <form onSubmit={handleSave} className="space-y-4">
              <div>
                <label className="block font-medium mb-2">记忆类型</label>
                <select
                  value={saveForm.memory_type}
                  onChange={(e) => setSaveForm({ ...saveForm, memory_type: e.target.value })}
                  className="input w-full"
                >
                  <option value="profile">个人资料</option>
                  <option value="preference">偏好</option>
                  <option value="allergy">过敏/禁忌</option>
                  <option value="history">历史信息</option>
                  <option value="other">其他</option>
                </select>
              </div>

            <div>
              <label className="block font-medium mb-2">记忆内容</label>
              <textarea
                value={saveForm.content}
                onChange={(e) => setSaveForm({ ...saveForm, content: e.target.value })}
                placeholder="例：我不吃花生，对海鲜过敏"
                className="input w-full"
                rows={4}
                required
              />
            </div>

            <div>
              <label className="block font-medium mb-2">标签 (逗号分隔，可选)</label>
              <input
                type="text"
                value={saveForm.tags}
                onChange={(e) => setSaveForm({ ...saveForm, tags: e.target.value })}
                placeholder="例：allergy,important"
                className="input w-full"
              />
            </div>

            <div>
              <label className="block font-medium mb-2">重要性 (0-1)</label>
              <div className="flex items-center gap-4">
                <input
                  type="range"
                  min={0}
                  max={1}
                  step={0.1}
                  value={saveForm.importance}
                  onChange={(e) => setSaveForm({ ...saveForm, importance: parseFloat(e.target.value) })}
                  className="flex-1"
                />
                <span className="text-lg font-bold text-blue-600 w-12">
                  {saveForm.importance.toFixed(1)}
                </span>
              </div>
              <p className="text-xs text-gray-500 mt-1">越接近 1 表示越重要</p>
            </div>

            <button type="submit" className="btn btn-primary w-full" disabled={saveLoading}>
              {saveLoading ? '保存中...' : '保存记忆'}
            </button>
            </form>
          </div>
        </div>

        <div className="space-y-6">
          {/* 检索记忆 */}
          <div className="card">
            <h2 className="text-xl font-bold mb-4">记忆检索</h2>
            <form onSubmit={handleSearch} className="space-y-4">
              <div>
                <label className="block font-medium mb-2">搜索问题</label>
                <input
                  type="text"
                  value={searchForm.query}
                  onChange={(e) => setSearchForm({ ...searchForm, query: e.target.value })}
                  placeholder="例：有什么饮食禁忌、我的身体状况、喜欢的烹饪方式"
                  className="input w-full"
                  required
                />
              </div>

              <button type="submit" className="btn btn-primary w-full" disabled={searchLoading}>
                {searchLoading ? '搜索中...' : '搜索'}
              </button>
            </form>
          </div>

          <div className="card">
            <div className="flex items-center justify-between gap-3 mb-4">
              <h2 className="text-xl font-bold">已添加记忆</h2>
              <button
                type="button"
                onClick={fetchMemories}
                className="btn btn-secondary px-3 py-1 text-sm"
                disabled={memoryListLoading}
              >
                刷新
              </button>
            </div>

            {memoryListLoading ? (
              <LoadingState text="记忆加载中..." />
            ) : memoryListError ? (
              <ErrorState message={memoryListError} />
            ) : memories.length === 0 ? (
              <EmptyState text="暂无记忆，请先在左侧保存" />
            ) : (
              <div className="space-y-3 max-h-[560px] overflow-y-auto pr-1">
                {memories.map((memory) => (
                  <div key={memory.memory_id} className="border rounded p-3 bg-white">
                    <div className="flex items-start justify-between gap-3 mb-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-xs font-semibold text-blue-700 bg-blue-50 px-2 py-1 rounded">
                          {memoryTypeLabel[memory.memory_type] || memory.memory_type}
                        </span>
                        <span className="text-xs text-gray-500">
                          {formatMemoryTime(memory.updated_at)}
                        </span>
                      </div>
                      <button
                        type="button"
                        onClick={() => handleDeleteMemory(memory.memory_id)}
                        className="btn px-2 py-1 text-xs bg-red-600 hover:bg-red-700 text-white"
                        disabled={deletingMemoryIds.has(memory.memory_id)}
                      >
                        {deletingMemoryIds.has(memory.memory_id) ? '删除中' : '删除'}
                      </button>
                    </div>
                    <p className="text-sm text-gray-800 whitespace-pre-wrap">{memory.content}</p>
                    {memory.tags.length > 0 && (
                      <div className="flex flex-wrap gap-2 mt-3">
                        {memory.tags.map((tag) => (
                          <span key={tag} className="text-xs text-gray-600 bg-gray-100 px-2 py-1 rounded">
                            {tag}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* 搜索结果 */}
          {result && (
            <div className="card bg-purple-50 border-2 border-purple-200">
              <h2 className="text-xl font-bold mb-4">📝 搜索结果</h2>

              <div className="bg-white p-4 rounded mb-4">
                <p className="text-gray-700">{result.summary}</p>
              </div>

              {result.evidence.length > 0 && (
                <div>
                  <h3 className="font-semibold mb-2">💡 相关记忆</h3>
                  <div className="space-y-2">
                    {result.evidence.map((item, i) => (
                      <div key={i} className="bg-white p-3 rounded border-l-4 border-purple-400">
                        <p className="text-gray-700">{item}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {result.evidence.length === 0 && <EmptyState text="未检索到相关记忆" className="mt-2" />}

              <div className="mt-4 pt-4 border-t">
                <p className="text-xs text-gray-500">
                  检索模式: <span className="font-medium">{result.retrieval_mode}</span>
                </p>
                {result._audit?.trace_id && (
                  <p className="text-xs text-gray-500 mt-1">
                    trace_id: <span className="font-mono">{result._audit.trace_id}</span>
                  </p>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
