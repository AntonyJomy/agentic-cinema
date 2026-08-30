import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import {
  getIdToken,
  isAuthConfigured,
  signInWithGoogle,
  signOutUser,
  subscribeToAuth,
} from './firebase';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(isAuthConfigured);

  useEffect(() => {
    if (!isAuthConfigured) {
      setLoading(false);
      return undefined;
    }
    return subscribeToAuth((next) => {
      setUser(next);
      setLoading(false);
    });
  }, []);

  const value = useMemo(
    () => ({
      user,
      loading,
      configured: isAuthConfigured,
      // When Firebase env is missing, treat the session as open for local API stub mode.
      isAuthenticated: !isAuthConfigured || Boolean(user),
      signInWithGoogle,
      signOut: signOutUser,
      getIdToken,
    }),
    [user, loading]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return ctx;
}
