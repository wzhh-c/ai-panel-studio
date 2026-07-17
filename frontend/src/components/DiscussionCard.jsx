import { useNavigate } from 'react-router-dom';

const STATUS_MAP = {
  GENERATING:      { label: '生成中',   color: 'bg-yellow-100 text-yellow-800 border-yellow-300' },
  PENDING_CONFIRM: { label: '待确认',   color: 'bg-blue-100 text-blue-800 border-blue-300' },
  IN_PROGRESS:     { label: '进行中',   color: 'bg-green-100 text-green-800 border-green-300' },
  COMPLETED:       { label: '已结束',   color: 'bg-gray-200 text-gray-600 border-gray-400' },
};

function formatDate(iso) {
  if (!iso) return '';
  return new Date(iso).toLocaleDateString('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
  });
}

export default function DiscussionCard({ discussion }) {
  const navigate = useNavigate();
  const s = STATUS_MAP[discussion.status] || STATUS_MAP.GENERATING;

  const handleClick = () => {
    // 空值保护：若 discussion.id 缺失，不跳转并输出警告
    if (!discussion || !discussion.id) {
      console.warn('讨论 ID 缺失，无法跳转');
      return;
    }
    navigate(`/discussion/${discussion.id}`);
  };

  return (
    <div
      onClick={handleClick}
      className="bg-white rounded-xl shadow-md border border-gray-100 p-5
                 hover:shadow-lg hover:-translate-y-0.5 transition-all duration-200
                 cursor-pointer flex flex-col gap-3"
    >
      {/* topic */}
      <h3 className="text-lg font-semibold text-gray-800 leading-snug line-clamp-2">
        {discussion.topic}
      </h3>

      {/* meta row */}
      <div className="flex items-center justify-between text-sm">
        <span className="text-gray-500">
          {discussion.expert_count ?? '?'} 位专家
        </span>
        <span
          className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs
                      font-medium border ${s.color}`}
        >
          {s.label}
        </span>
      </div>

      {/* date */}
      <div className="text-xs text-gray-400 mt-auto pt-1 border-t border-gray-100">
        {formatDate(discussion.created_at)}
      </div>
    </div>
  );
}