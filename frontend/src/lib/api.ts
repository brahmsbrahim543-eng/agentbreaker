const BASE_URL = "";

class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public data?: unknown
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function getToken(): string | null {
  return localStorage.getItem("ab_token");
}

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers,
  });

  if (response.status === 401) {
    localStorage.removeItem("ab_token");
    localStorage.removeItem("ab_user");
    window.location.href = "/login";
    throw new ApiError(401, "Unauthorized");
  }

  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new ApiError(
      response.status,
      data?.detail || data?.message || `Request failed with status ${response.status}`,
      data
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
}

export const api = {
  get<T>(path: string): Promise<T> {
    return request<T>(path, { method: "GET" });
  },

  post<T>(path: string, body?: unknown): Promise<T> {
    return request<T>(path, {
      method: "POST",
      body: body ? JSON.stringify(body) : undefined,
    });
  },

  put<T>(path: string, body?: unknown): Promise<T> {
    return request<T>(path, {
      method: "PUT",
      body: body ? JSON.stringify(body) : undefined,
    });
  },

  delete<T>(path: string): Promise<T> {
    return request<T>(path, { method: "DELETE" });
  },
};

export function createWebSocket(path: string): WebSocket {
  const token = getToken();
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const host = window.location.host;
  const url = `${protocol}//${host}${path}${token ? `?token=${encodeURIComponent(token)}` : ""}`;

  let ws = new WebSocket(url);
  let reconnectTimeout: ReturnType<typeof setTimeout>;
  let reconnectAttempts = 0;
  const maxReconnectAttempts = 5;
  const baseDelay = 1000;

  const originalClose = ws.close.bind(ws);
  let intentionalClose = false;

  ws.close = (code?: number, reason?: string) => {
    intentionalClose = true;
    clearTimeout(reconnectTimeout);
    originalClose(code, reason);
  };

  ws.addEventListener("close", () => {
    if (intentionalClose || reconnectAttempts >= maxReconnectAttempts) return;

    const delay = baseDelay * Math.pow(2, reconnectAttempts);
    reconnectAttempts++;

    reconnectTimeout = setTimeout(() => {
      const newWs = createWebSocket(path);
      Object.assign(ws, newWs);
    }, delay);
  });

  ws.addEventListener("open", () => {
    reconnectAttempts = 0;
  });

  return ws;
}

export { ApiError };
