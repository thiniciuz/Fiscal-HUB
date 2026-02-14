const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";

let authToken = null;

export function setAuthToken(token) {
  authToken = token || null;
}

function authHeaders(extra = {}, withAuth = true) {
  const out = { ...(extra || {}) };
  if (withAuth && authToken) {
    out.Authorization = `Bearer ${authToken}`;
  }
  return out;
}

async function request(path, options = {}) {
  const { withAuth = true, headers: rawHeaders, ...rest } = options;
  const headers = authHeaders(
    {
      "Content-Type": "application/json",
      ...(rawHeaders || {}),
    },
    withAuth
  );

  const res = await fetch(`${API_BASE}${path}`, {
    headers,
    ...rest,
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Erro ${res.status}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  listUsers: () => request("/users"),
  createUser: (payload) => request("/users", { method: "POST", body: JSON.stringify(payload) }),
  login: async (nome, senha) => {
    const out = await request("/auth/login", {
      method: "POST",
      body: JSON.stringify({ nome, senha }),
      withAuth: false,
    });
    setAuthToken(out?.access_token || null);
    return {
      ...(out?.user || {}),
      access_token: out?.access_token || null,
      token_type: out?.token_type || "bearer",
    };
  },

  getServerSettings: (userId) => request(`/settings/server?user_id=${userId}`),
  updateServerSettings: (userId, payload) =>
    request(`/settings/server?user_id=${userId}`, { method: "PATCH", body: JSON.stringify(payload) }),
  getEmailSettings: (userId) => request(`/settings/email?user_id=${userId}`),
  updateEmailSettings: (userId, payload) =>
    request(`/settings/email?user_id=${userId}`, { method: "PATCH", body: JSON.stringify(payload) }),

  listCompanies: (userId, query = "", regime = "", competencia = "") =>
    request(
      `/companies?user_id=${userId}&query=${encodeURIComponent(query)}&regime=${encodeURIComponent(
        regime
      )}&competencia=${encodeURIComponent(competencia)}`
    ),
  createCompany: (payload) => request("/companies", { method: "POST", body: JSON.stringify(payload) }),
  updateCompany: (companyId, userId, payload) =>
    request(`/companies/${companyId}?user_id=${userId}`, { method: "PATCH", body: JSON.stringify(payload) }),
  updateCompanyResponsavel: (companyId, userId, responsavel_id) =>
    request(`/companies/${companyId}/responsavel?user_id=${userId}`, {
      method: "PATCH",
      body: JSON.stringify({ responsavel_id }),
    }),

  listTasks: (params) => {
    const qs = new URLSearchParams();
    Object.entries(params || {}).forEach(([k, v]) => {
      if (v === undefined || v === null || v === "") return;
      if (Array.isArray(v)) {
        v.forEach((item) => qs.append(k, item));
      } else {
        qs.append(k, v);
      }
    });
    return request(`/tasks?${qs.toString()}`);
  },

  listUpcomingTasks: (userId, days = 7) => request(`/tasks/upcoming?user_id=${userId}&days=${days}`),
  listTaskComments: (taskId, userId) => request(`/tasks/${taskId}/comments?user_id=${userId}`),
  addTaskComment: (taskId, userId, text) =>
    request(`/tasks/${taskId}/comments?user_id=${userId}`, {
      method: "POST",
      body: JSON.stringify({ text }),
    }),
  ackTaskComment: (taskId, commentId, userId) =>
    request(`/tasks/${taskId}/comments/${commentId}/ack?user_id=${userId}`, { method: "POST" }),
  createTask: (payload) => request("/tasks", { method: "POST", body: JSON.stringify(payload) }),
  updateTaskStatus: (taskId, userId, status) =>
    request(`/tasks/${taskId}/status?user_id=${userId}`, { method: "PATCH", body: JSON.stringify({ status }) }),
  updateTask: (taskId, userId, payload) =>
    request(`/tasks/${taskId}?user_id=${userId}`, { method: "PATCH", body: JSON.stringify(payload) }),
  listNotifications: (userId, unreadOnly = false) =>
    request(`/notifications?user_id=${userId}&unread_only=${unreadOnly ? "true" : "false"}`),
  markNotificationRead: (notificationId, userId) =>
    request(`/notifications/${notificationId}/read?user_id=${userId}`, { method: "PATCH" }),

  getPdfUrl: (taskId, userId) => `${API_BASE}/tasks/${taskId}/pdf?user_id=${userId}`,

  openPdf: async (taskId, userId) => {
    const res = await fetch(`${API_BASE}/tasks/${taskId}/pdf?user_id=${userId}`, {
      headers: authHeaders({}, true),
    });
    if (!res.ok) throw new Error(await res.text());
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    window.open(url, "_blank", "noopener,noreferrer");
    setTimeout(() => URL.revokeObjectURL(url), 60_000);
  },

  uploadPdf: async (taskId, userId, file) => {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${API_BASE}/tasks/${taskId}/pdf?user_id=${userId}`, {
      method: "POST",
      headers: authHeaders({}, true),
      body: form,
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },
};
