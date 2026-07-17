import { useState, useEffect, useCallback } from 'react';
import { fetchDiscussions, createDiscussion } from '../api/client';

export default function useDiscussions() {
  const [discussions, setDiscussions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchDiscussions({ limit: 100 });
      // 后端返回 { items: [...], total: ... } — 使用 res.data.items 而非 res.data
      const items = (res?.data?.items || []).sort(
        (a, b) => new Date(b.created_at) - new Date(a.created_at),
      );
      setDiscussions(items);
    } catch (err) {
      const message =
        err.response?.data?.detail ||
        err.response?.data?.message ||
        err.message ||
        '加载讨论列表失败';
      setError(message);
    } finally {
      setLoading(false);
    }
  }, []);

  const create = useCallback(async (data) => {
    const res = await createDiscussion(data);
    // res.data 是新创建的讨论对象，追加到列表头部
    setDiscussions((prev) => [res?.data, ...prev].filter(Boolean));
    return res?.data;
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return { discussions, loading, error, load, create };
}
