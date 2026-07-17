import { useState } from 'react';

export default function CreateDiscussionModal({ open, onClose, onSubmit }) {
  const [topic, setTopic] = useState('');
  const [expertCount, setExpertCount] = useState(4);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  if (!open) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (!topic.trim()) {
      setError('请输入讨论话题');
      return;
    }

    setSubmitting(true);
    try {
      await onSubmit({
        topic: topic.trim(),
        expert_count: expertCount,
        user_id: '550e8400-e29b-41d4-a716-446655440001',
      });
      setTopic('');
      setExpertCount(4);
      onClose();
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* backdrop */}
      <div
        className="absolute inset-0 bg-black/40 backdrop-blur-sm"
        onClick={submitting ? undefined : onClose}
      />

      {/* modal */}
      <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-lg
                      mx-4 p-6 animate-[fadeIn_0.2s_ease-out]">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-xl font-bold text-gray-800">发起新讨论</h2>
          <button
            onClick={onClose}
            disabled={submitting}
            className="p-1 rounded-lg text-gray-400 hover:text-gray-600
                       hover:bg-gray-100 transition-colors disabled:opacity-40"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          {/* topic */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              讨论话题 <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="例如：人工智能是否应该拥有法律主体资格？"
              maxLength={500}
              className="w-full px-3 py-2.5 border border-gray-300 rounded-lg
                         focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500
                         outline-none transition-shadow text-sm"
              autoFocus
            />
          </div>

          {/* expert count */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              专家人数
            </label>
            <div className="flex items-center gap-3">
              <input
                type="range"
                min={1}
                max={8}
                value={expertCount}
                onChange={(e) => setExpertCount(Number(e.target.value))}
                className="flex-1 accent-indigo-600"
              />
              <span className="w-8 text-center text-sm font-semibold text-indigo-700">
                {expertCount}
              </span>
            </div>
          </div>

          {/* error */}
          {error && (
            <p className="text-sm text-red-600 bg-red-50 px-3 py-2 rounded-lg">
              {error}
            </p>
          )}

          {/* actions */}
          <div className="flex justify-end gap-3 mt-2">
            <button
              type="button"
              onClick={onClose}
              disabled={submitting}
              className="px-4 py-2 text-sm font-medium text-gray-700
                         bg-gray-100 rounded-lg hover:bg-gray-200
                         transition-colors disabled:opacity-40"
            >
              取消
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="px-5 py-2 text-sm font-medium text-white
                         bg-indigo-600 rounded-lg hover:bg-indigo-700
                         transition-colors disabled:opacity-60
                         inline-flex items-center gap-2"
            >
              {submitting && (
                <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10"
                          stroke="currentColor" strokeWidth="4" fill="none" />
                  <path className="opacity-75" fill="currentColor"
                        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
              )}
              {submitting ? '生成中...' : '发起讨论'}
            </button>
          </div>
        </form>
      </div>

      {/* keyframe for fadeIn */}
      <style>{`
        @keyframes fadeIn {
          from { opacity: 0; transform: scale(0.95) translateY(-8px); }
          to   { opacity: 1; transform: scale(1) translateY(0); }
        }
      `}</style>
    </div>
  );
}
