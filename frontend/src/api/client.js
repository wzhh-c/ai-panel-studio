import axios from 'axios';

const apiClient = axios.create({
  baseURL: 'http://127.0.0.1:8080/api',
  timeout: 60000,
  headers: { 'Content-Type': 'application/json' },
});

// 请求拦截器：打印请求信息（方便调试）
apiClient.interceptors.request.use(
  (config) => {
    const payload =
      config.method === 'get'
        ? { params: config.params || undefined }
        : { data: config.data || undefined };
    console.log(`[API] ${config.method.toUpperCase()} ${config.url}`, payload);
    return config;
  },
  (error) => Promise.reject(error)
);

// 响应拦截器：统一处理错误
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error(
      '[API Error]',
      error.response?.status,
      error.response?.data?.detail || error.message
    );
    return Promise.reject(error);
  }
);

/** GET /discussions — fetch discussion list. */
export function fetchDiscussions(params = {}) {
  return apiClient.get('/discussions', { params });
}

/** POST /discussions — create a new discussion. */
export function createDiscussion(data) {
  return apiClient.post('/discussions', data);
}

/** GET /discussions/:id — get discussion detail. */
export function getDiscussion(id) {
  return apiClient.get(`/discussions/${id}`);
}

/** POST /discussions/:id/start — confirm roster and start discussion. */
export function startDiscussion(id, data = {}) {
  // 确保始终发送有效的 JSON 对象（即使 data 为 undefined 或 null）
  return apiClient.post(`/discussions/${id}/start`, data || {});
}

/** POST /discussions/:id/regenerate-roster — regenerate expert roster. */
export function regenerateRoster(id) {
  return apiClient.post(`/discussions/${id}/regenerate-roster`);
}

/** POST /discussions/:id/end — end discussion. */
export function endDiscussion(id) {
  return apiClient.post(`/discussions/${id}/end`);
}

/** POST /discussions/:id/ask — ask an expert a question. */
export function askQuestion(id, question) {
  return apiClient.post(`/discussions/${id}/ask`, { question });
}

export default apiClient;