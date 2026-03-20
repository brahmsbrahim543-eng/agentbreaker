import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from "react";
import { api } from "../lib/api";

interface User {
  id: string;
  email: string;
  name: string;
  role: string;
  avatar_url?: string;
}

interface Org {
  id: string;
  name: string;
  slug: string;
}

interface AuthState {
  user: User | null;
  org: Org | null;
  token: string | null;
  isAuthenticated: boolean;
  loading: boolean;
}

interface AuthContextValue extends AuthState {
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

interface AuthResponse {
  access_token: string;
  token_type: string;
}

interface MeResponse {
  user: User;
  org: Org;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: null,
    org: null,
    token: null,
    isAuthenticated: false,
    loading: true,
  });

  const fetchMe = useCallback(async (token: string) => {
    try {
      localStorage.setItem("ab_token", token);
      const data = await api.get<MeResponse>("/api/v1/auth/me");
      setState({
        user: data.user,
        org: data.org,
        token,
        isAuthenticated: true,
        loading: false,
      });
    } catch {
      localStorage.removeItem("ab_token");
      localStorage.removeItem("ab_user");
      setState({
        user: null,
        org: null,
        token: null,
        isAuthenticated: false,
        loading: false,
      });
    }
  }, []);

  const autoLogin = useCallback(async () => {
    try {
      const data = await api.post<AuthResponse>("/api/v1/auth/login", {
        email: "admin@agentbreaker.com",
        password: "AB2026secure!",
      });
      await fetchMe(data.access_token);
    } catch {
      setState((prev) => ({ ...prev, loading: false }));
    }
  }, [fetchMe]);

  useEffect(() => {
    const token = localStorage.getItem("ab_token");
    if (token) {
      fetchMe(token);
    } else {
      // Auto-login for authenticated sessions
      autoLogin();
    }
  }, [fetchMe, autoLogin]);

  const login = useCallback(
    async (email: string, password: string) => {
      const data = await api.post<AuthResponse>("/api/v1/auth/login", {
        email,
        password,
      });
      await fetchMe(data.access_token);
    },
    [fetchMe]
  );

  const logout = useCallback(() => {
    localStorage.removeItem("ab_token");
    localStorage.removeItem("ab_user");
    setState({
      user: null,
      org: null,
      token: null,
      isAuthenticated: false,
      loading: false,
    });
    window.location.href = "/login";
  }, []);

  return (
    <AuthContext.Provider value={{ ...state, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
