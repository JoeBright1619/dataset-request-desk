// Auth context for managing authentication state
import React, { createContext, useContext, useEffect, useState } from 'react';
import { getAccessToken, clearTokens, setTokens } from '../api/client';
import type { LoginResponse, User } from '../api/types';
interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

interface AuthProviderProps {
  children: React.ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  // Check for existing token on startup
  useEffect(() => {
    const checkAuth = async () => {
      const accessToken = getAccessToken();
      if (accessToken) {
        try {
          // Import here to avoid circular dependency
          const { get } = await import('../api/client');
          // Fetch user data from API
          const user = await get<User>('/auth/me');
          setUser(user);
        } catch (err) {
          clearTokens();
          setUser(null);
        }
      }
      setLoading(false);
    };

    checkAuth();
  }, []);

  const login = async (email: string, password: string) => {
    // Import here to avoid circular dependency
    const { post } = await import('../api/client');

    try {
      const response = await post<LoginResponse>('/auth/login', {
        email,
        password,
      }, { skipAuth: true });

      // Store tokens
      setTokens(response.access_token, response.refresh_token);

      // Fetch user data
      const { get } = await import('../api/client');
      const user = await get<User>('/auth/me');
      setUser(user);
    } catch (err) {
      throw err;
    }
  };

  const logout = () => {
    clearTokens();
    setUser(null);
  };

  const isAuthenticated = !!user;

  if (loading) {
    return <div>Loading...</div>;
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, isAuthenticated }}>
      {children}
    </AuthContext.Provider>
  );
}