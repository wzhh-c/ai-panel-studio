import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { getDiscussion, startDiscussion, regenerateRoster } from '../api/client';

export default function Discussion() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [discussion, setDiscussion] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [starting, setStarting] = useState(false);
  const [regenerating, setRegenerating] = useState(false);

  const loadDiscussion = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await getDiscussion(id);
      const data = res.data;
      setDiscussion(data);

      // 如果讨论已经 IN_PROGRESS，直接跳转到讨论室
      if (data.status === 'IN_PROGRESS') {
        navigate(`/room/${id}`);
        return;
      }
      // 如果讨论已结束，返回首页
      if (data.status === 'COMPLETED') {
        navigate('/');
        return;
      }
    } catch (err) {
      setError('讨论不存在或已被删除');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDiscussion();
  }, [id]);

  const handleStart = async () => {
    if (starting) return;
    setStarting(true);
    try {
      await startDiscussion(id, {});
      navigate(`/room/${id}`);
    } catch (err) {
      const detail = err.response?.data?.detail || '';
      // 如果错误是因为讨论已在 IN_PROGRESS，直接跳转
      if (detail.includes('IN_PROGRESS') || err.response?.status === 400) {
        navigate(`/room/${id}`);
        return;
      }
      setError('开始讨论失败，请稍后重试');
    } finally {
      setStarting(false);
    }
  };

  const handleRegenerate = async () => {
    if (regenerating) return;
    setRegenerating(true);
    try {
      await regenerateRoster(id);
      await loadDiscussion(); // 刷新阵容
    } catch (err) {
      setError('重新生成阵容失败');
    } finally {
      setRegenerating(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="animate-spin rounded-full h-10 w-10 border-4 border-indigo-200 border-t-indigo-600" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-gray-50 px-4">
        <p className="text-red-500 text-lg mb-4">{error}</p>
        <button
          onClick={() => navigate('/')}
          className="px-5 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition"
        >
          返回首页
        </button>
      </div>
    );
  }

  if (!discussion) return null;

  const isGenerating = discussion.status === 'GENERATING';
  const roster = discussion.experts || [];
  const moderator = roster.find((e) => e.role === 'moderator');
  const experts = roster.filter((e) => e.role === 'expert');

  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4">
      <div className="max-w-4xl mx-auto">
        <h2 className="text-2xl font-bold text-gray-800 mb-2">确认专家阵容</h2>
        <p className="text-gray-500 mb-6">{discussion.topic}</p>

        {/* GENERATING 状态提示 */}
        {isGenerating && (
          <div className="mb-6 flex items-center gap-3 bg-yellow-50 border border-yellow-200
                          rounded-lg px-4 py-3">
            <div className="animate-spin rounded-full h-5 w-5 border-2
                            border-yellow-400 border-t-yellow-600" />
            <p className="text-sm text-yellow-700">
              阵容生成中，请稍候…（这可能需要几秒钟）
            </p>
          </div>
        )}

        {/* 主持人 */}
        {moderator && (
          <div className="mb-6">
            <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-2">
              🎤 主持人
            </h3>
            <div
              className="bg-white rounded-xl shadow p-4 border-l-4"
              style={{ borderColor: moderator.color || '#6B7280' }}
            >
              <div className="flex items-center gap-3">
                <div
                  className="w-10 h-10 rounded-full flex items-center justify-center text-white font-bold"
                  style={{ backgroundColor: moderator.color || '#6B7280' }}
                >
                  {moderator.name[0]}
                </div>
                <div>
                  <p className="font-semibold text-gray-800">{moderator.name}</p>
                  <p className="text-sm text-gray-500">{moderator.profession} · {moderator.title}</p>
                </div>
              </div>
              <p className="text-sm text-gray-600 mt-2">{moderator.stance}</p>
            </div>
          </div>
        )}

        {/* 专家 */}
        <div className="mb-6">
          <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-2">
            👥 专家 ({experts.length} 位)
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {experts.map((e) => (
              <div
                key={e.id}
                className="bg-white rounded-xl shadow p-4 border-l-4"
                style={{ borderColor: e.color || '#9CA3AF' }}
              >
                <div className="flex items-center gap-3">
                  <div
                    className="w-8 h-8 rounded-full flex items-center justify-center text-white font-bold text-sm"
                    style={{ backgroundColor: e.color || '#9CA3AF' }}
                  >
                    {e.name[0]}
                  </div>
                  <div>
                    <p className="font-semibold text-gray-800">{e.name}</p>
                    <p className="text-xs text-gray-500">{e.profession}</p>
                  </div>
                </div>
                <p className="text-sm text-gray-600 mt-2">{e.stance}</p>
              </div>
            ))}
          </div>
        </div>

        {/* 按钮 */}
        <div className="flex flex-wrap gap-3">
          <button
            onClick={handleStart}
            disabled={starting}
            className="px-6 py-2.5 bg-green-600 text-white rounded-lg
                       hover:bg-green-700 transition disabled:opacity-50"
          >
            {starting ? '启动中...' : '✅ 确认阵容，开始讨论'}
          </button>
          <button
            onClick={handleRegenerate}
            disabled={regenerating || isGenerating}
            className="px-6 py-2.5 bg-gray-200 text-gray-700 rounded-lg
                       hover:bg-gray-300 transition disabled:opacity-50"
            title={isGenerating ? '阵容生成中，请稍候...' : undefined}
          >
            {regenerating || isGenerating ? '生成中...' : '🔄 重新生成阵容'}
          </button>
          <button
            onClick={() => navigate('/')}
            className="px-6 py-2.5 bg-gray-100 text-gray-500 rounded-lg
                       hover:bg-gray-200 transition"
          >
            返回首页
          </button>
        </div>
      </div>
    </div>
  );
}