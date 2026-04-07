import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from "react";
import {
  CognitoUserPool,
  CognitoUser,
  AuthenticationDetails,
  CognitoUserSession,
} from "amazon-cognito-identity-js";
import type { AuthState } from "../types";

const poolData = {
  UserPoolId: import.meta.env.VITE_COGNITO_USER_POOL_ID || "",
  ClientId: import.meta.env.VITE_COGNITO_CLIENT_ID || "",
};

const userPool = new CognitoUserPool(poolData);

interface AuthCtx extends AuthState {
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  loading: boolean;
}

const AuthContext = createContext<AuthCtx>({
  isAuthenticated: false,
  idToken: null,
  email: null,
  login: async () => {},
  logout: () => {},
  loading: true,
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [auth, setAuth] = useState<AuthState>({
    isAuthenticated: false,
    idToken: null,
    email: null,
  });
  const [loading, setLoading] = useState(true);

  // Check for existing session on mount
  useEffect(() => {
    const user = userPool.getCurrentUser();
    if (user) {
      user.getSession((err: Error | null, session: CognitoUserSession | null) => {
        if (!err && session && session.isValid()) {
          setAuth({
            isAuthenticated: true,
            idToken: session.getIdToken().getJwtToken(),
            email: session.getIdToken().payload.email || null,
          });
        }
        setLoading(false);
      });
    } else {
      setLoading(false);
    }
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    return new Promise<void>((resolve, reject) => {
      const user = new CognitoUser({ Username: email, Pool: userPool });
      const authDetails = new AuthenticationDetails({
        Username: email,
        Password: password,
      });

      user.authenticateUser(authDetails, {
        onSuccess: (session) => {
          setAuth({
            isAuthenticated: true,
            idToken: session.getIdToken().getJwtToken(),
            email: session.getIdToken().payload.email || email,
          });
          resolve();
        },
        onFailure: (err) => reject(err),
        newPasswordRequired: () => {
          // For first-time admin login with temp password
          user.completeNewPasswordChallenge(password, {}, {
            onSuccess: (session) => {
              setAuth({
                isAuthenticated: true,
                idToken: session.getIdToken().getJwtToken(),
                email: session.getIdToken().payload.email || email,
              });
              resolve();
            },
            onFailure: (err) => reject(err),
          });
        },
      });
    });
  }, []);

  const logout = useCallback(() => {
    const user = userPool.getCurrentUser();
    if (user) user.signOut();
    setAuth({ isAuthenticated: false, idToken: null, email: null });
  }, []);

  return (
    <AuthContext.Provider value={{ ...auth, login, logout, loading }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
