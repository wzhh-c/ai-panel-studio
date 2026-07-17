import { useState } from 'react';
import DiscussionList from '../components/DiscussionList';
import CreateDiscussionModal from '../components/CreateDiscussionModal';
import useDiscussions from '../hooks/useDiscussions';

export default function Home() {
  const { discussions, loading, error, load, create } = useDiscussions();
  const [modalOpen, setModalOpen] = useState(false);

  const handleCreate = async (data) => {
    const result = await create(data);
    return result;
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16
                        flex items-center justify-between">
          {/* logo */}
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 bg-indigo-600 rounded-lg flex items-center
                            justify-center shadow-sm">
              <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24"
                   stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                      d="M17 8h2a2 2 0 012 2v6a2 2 0 01-2 2h-2v4l-4-4H9a1.994 1.994 0
                         01-1.414-.586m0 0L11 14h4a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2
                         0 00-2 2v6a2 2 0 002 2h2v4l.586-.586z" />
              </svg>
            </div>
            <h1 className="text-xl font-bold text-gray-900 tracking-tight">
              AI Panel Studio
            </h1>
          </div>

          {/* new discussion button */}
          <button
            onClick={() => setModalOpen(true)}
            className="inline-flex items-center gap-2 px-4 py-2.5
                       bg-indigo-600 text-white text-sm font-medium rounded-lg
                       hover:bg-indigo-700 active:bg-indigo-800
                       transition-colors shadow-sm hover:shadow-md"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24"
                 stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M12 4v16m8-8H4" />
            </svg>
            发起新讨论
          </button>
        </div>
      </header>

      {/* main content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-6">
          <h2 className="text-2xl font-bold text-gray-900">
            讨论列表
          </h2>
          <p className="text-sm text-gray-500 mt-1">
            共 {discussions.length} 场讨论
          </p>
        </div>

        <DiscussionList
          discussions={discussions}
          loading={loading}
          error={error}
          onRefresh={load}
        />
      </main>

      {/* create modal */}
      <CreateDiscussionModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onSubmit={handleCreate}
      />
    </div>
  );
}
