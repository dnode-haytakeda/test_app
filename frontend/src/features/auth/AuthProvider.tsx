import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import {
  ApiError,
  AUTH_SIGNED_OUT_EVENT,
  api,
  clearAccessToken,
  setAccessToken,
} from "../../shared/api/client";
import { AuthContext, type AuthContextValue, type User } from "./auth-context";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const refreshMe = useCallback(async () => {
    try {
      const me = await api.get<User>("/auth/me");
      setUser(me);
    } catch (err) {
      if (err instanceof ApiError) {
        setUser(null);
        return;
      }

      throw err;
    }
  }, []);

  useEffect(() => {
    let cancelled = false;

    void (async () => {
      try {
        await refreshMe();
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [refreshMe]);

  useEffect(() => {
    const onSignedOut = () => {
      setUser(null);
    };

    window.addEventListener(AUTH_SIGNED_OUT_EVENT, onSignedOut);

    return () => {
      window.removeEventListener(AUTH_SIGNED_OUT_EVENT, onSignedOut);
    };
  }, []);

  const login = useCallback(
    async (email: string, password: string) => {
      const tokens = await api.post<{
        access_token: string;
      }>("/auth/login", { body: { email, password } });

      setAccessToken(tokens.access_token);
      await refreshMe();
    },
    [refreshMe],
  );

  const logout = useCallback(async () => {
    try {
      await api.post("/auth/logout");
    } catch {
      // Ignore logout API errors and clear local auth state anyway.
    }

    clearAccessToken();
    setUser(null);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ user, isLoading, login, logout, refreshMe }),
    [user, isLoading, login, logout, refreshMe],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
