import { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import { getCurrentUser, fetchAuthSession, signOut as amplifySignOut } from 'aws-amplify/auth';

export interface AuthUser {
  userId: string;
  email: string;
  name: string;
  groups: string[];
  isMerckAdmin: boolean;
  isCMOUser: boolean;
}

interface AuthContextValue {
  user: AuthUser | null;
  loading: boolean;
  signOut: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  loading: true,
  signOut: async () => {},
  refreshUser: async () => {},
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  const loadUser = async () => {
    try {
      const cognitoUser = await getCurrentUser();
      const session = await fetchAuthSession();
      const claims = session.tokens?.idToken?.payload ?? {};
      const groupsClaim = claims['cognito:groups'];
      const groups: string[] = Array.isArray(groupsClaim) ? (groupsClaim as string[]) : [];

      setUser({
        userId: cognitoUser.userId,
        email: String(claims.email ?? cognitoUser.username),
        name: `${claims.given_name ?? ''} ${claims.family_name ?? ''}`.trim() || String(claims.email ?? cognitoUser.username),
        groups,
        isMerckAdmin: groups.includes('merck-admins'),
        isCMOUser: groups.includes('cmo-users'),
      });
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadUser(); }, []);

  const signOut = async () => {
    await amplifySignOut();
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, signOut, refreshUser: loadUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
