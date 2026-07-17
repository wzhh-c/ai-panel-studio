import DiscussionCard from './DiscussionCard';

export default function DiscussionList({ discussions, loading, error, onRefresh }) {
  if (loading) {
    return (
      <div className="flex justify-center py-20">
        <div className="animate-spin rounded-full h-10 w-10 border-4
                        border-indigo-200 border-t-indigo-600" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-20">
        <p className="text-red-500 mb-3">加载讨论列表失败</p>
        <button
          onClick={onRefresh}
          className="px-4 py-2 bg-indigo-600 text-white rounded-lg
                     hover:bg-indigo-700 transition-colors text-sm"
        >
          重试
        </button>
      </div>
    );
  }

  if (discussions.length === 0) {
    return (
      <div className="text-center py-20 text-gray-400">
        <svg className="mx-auto h-16 w-16 mb-4 text-gray-300" fill="none"
             viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1}
                d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8
                   a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042
                   3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
        </svg>
        <p className="text-lg mb-2">暂无讨论</p>
        <p className="text-sm">点击右上角按钮发起新讨论</p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4 gap-4">
      {discussions.map((d) => {
        // 防御性检查：如果讨论缺少 id，仍然渲染但记录警告（避免页面崩溃）
        if (!d || !d.id) {
          console.warn('讨论数据缺少 id:', d);
          return null;
        }
        return <DiscussionCard key={d.id} discussion={d} />;
      })}
    </div>
  );
}