/**
 * ExamGuard Authentication Context.
 *
 * Manages the authentication state bridging Firebase Authentication and
 * ExamGuard's RBAC system.
 *
 * Authentication flow:
 *   1. User clicks "Continue with Google"
 *   2. Firebase sign-in popup opens
 *   3. Frontend gets Firebase ID token
 *   4. Frontend calls /api/v1/auth/firebase/exchange
 *   5. Backend verifies token, maps user, issues ExamGuard JWT
 *   6. ExamGuard JWT is stored and sent with API requests
 *   7. Frontend updates auth state and shows role-specific UI
 */

"use client";

import { createContext, useContext, useState, useEffect, useRef, ReactNode, useCallback } from "react";
import {
  signInWithPopup,
  signOut as firebaseSignOut,
  exchangeFirebaseForExamGuard,
  onAuthStateChangedCallback,
  auth,
  googleProvider,
} from "../lib/firebase";
import { setTokenGetter } from "../lib/api";

export type UserRole = "ADMIN" | "OPERATOR" | "REVIEWER";

export interface AuthUser {
  id: number;
  email: string | null;
  full_name: string | null;
  role: UserRole;
  is_active: boolean;
  firebase_uid: string | null;
}

export type AuthPhase = "initializing" | "idle" | "popup" | "exchanging" | "authenticated" | "error";

export interface AuthState {
  user: AuthUser | null;
  loading: boolean;
  firebaseIdToken: string | null;
  examGuardToken: string | null;
  requiresOnboarding: boolean;
  displayName: string;
  isAuthenticated: boolean;
  signInWithGoogle: () => Promise<void>;
  signOut: () => Promise<void>;
  signInAsDev?: (role?: UserRole) => Promise<void>;
  authPhase: AuthPhase;
  authError: string | null;
  clearAuthError: () => void;
}

const AuthStateDefault: AuthState = {
  user: null,
  loading: true,
  firebaseIdToken: null,
  examGuardToken: null,
  requiresOnboarding: true,
  displayName: "Guest",
  isAuthenticated: false,
  signInWithGoogle: async () => {},
  signOut: async () => {},
  signInAsDev: async () => {},
  authPhase: "initializing",
  authError: null,
  clearAuthError: () => {},
};

const AuthContext = createContext<AuthState>(AuthStateDefault);

export const useAuth = (): AuthState => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
};

function getDevToken(): string | null {
  // In production builds, development authentication bypass is strictly forbidden
  // regardless of any client-side or public environment variables.
  if (process.env.NODE_ENV === "production") {
    return null;
  }
  if (
    (process.env.NODE_ENV === "development" ||
      process.env.NEXT_PUBLIC_ENABLE_DEV_AUTH === "true") &&
    typeof window !== "undefined"
  ) {
    const params = new URLSearchParams(window.location.search);
    const urlToken = params.get("eg_token");
    if (urlToken) {
      sessionStorage.setItem("eg_dev_token", urlToken);
      window.history.replaceState({}, "", window.location.pathname);
      return urlToken;
    }
    return sessionStorage.getItem("eg_dev_token");
  }
  return null;
}

function devTokenToUser(token: string): AuthUser | null {
  try {
    const payload = JSON.parse(atob(token.split(".")[1]));
    const parsedId = parseInt(payload.sub, 10);
    return {
      id: Number.isFinite(parsedId) ? parsedId : 1,
      email: payload.email || (payload.sub && payload.sub.includes("@") ? payload.sub : null),
      full_name: payload.full_name || null,
      role: payload.role as UserRole,
      is_active: true,
      firebase_uid: null,
    };
  } catch {
    return null;
  }
}

export const AuthProvider: React.FC<{ children: ReactNode }> = ({
  children,
}) => {
  const [authState, setAuthState] = useState<AuthState>(AuthStateDefault);

  const devTokenUsed = useRef(false);
  const exchangeInProgress = useRef(false);
  const signInWithGoogleRef = useRef<() => Promise<void>>(async () => {});
  const signOutRef = useRef<() => Promise<void>>(async () => {});

  const doExchange = useCallback(async (idToken: string) => {
    exchangeInProgress.current = true;
    setAuthState(prev => ({ ...prev, authPhase: "exchanging", loading: true }));
    try {
      const result = await exchangeFirebaseForExamGuard(idToken);
      const authUser: AuthUser = {
        id: result.user.id,
        email: result.user.email,
        full_name: result.user.full_name,
        role: result.user.role as UserRole,
        is_active: result.user.is_active,
        firebase_uid: result.user.firebase_uid,
      };
      setTokenGetter(() => result.token);
      setAuthState({
        ...AuthStateDefault,
        user: authUser,
        loading: false,
        firebaseIdToken: idToken,
        examGuardToken: result.token,
        requiresOnboarding: result.requires_onboarding,
        displayName: result.user.email
          ? `${result.user.full_name || ""} (${result.user.email})`
          : "User",
        isAuthenticated: true,
        authPhase: "authenticated",
        signInWithGoogle: signInWithGoogleRef.current,
        signOut: signOutRef.current,
        clearAuthError: () => setAuthState(prev => ({ ...prev, authError: null })),
      });
    } catch (error: unknown) {
      console.error("[ExamGuard] Auth exchange failed:", error);
      const errObj = error as { message?: string };
      const msg = errObj?.message || "Authentication failed. Please try again.";
      setAuthState(prev => ({
        ...prev,
        user: null,
        loading: false,
        firebaseIdToken: idToken,
        examGuardToken: null,
        requiresOnboarding: true,
        displayName: "Guest",
        isAuthenticated: false,
        authPhase: "error",
        authError: msg,
        signInWithGoogle: signInWithGoogleRef.current,
        signOut: signOutRef.current,
        clearAuthError: () => setAuthState(prev => ({ ...prev, authError: null })),
      }));
    } finally {
      exchangeInProgress.current = false;
    }
  }, []);

  useEffect(() => {
    const token = getDevToken();
    const devUser = token ? devTokenToUser(token) : null;
    if (token && devUser) {
      devTokenUsed.current = true;
      setTokenGetter(() => token);
      setAuthState({
        ...AuthStateDefault,
        user: devUser,
        loading: false,
        examGuardToken: token,
        requiresOnboarding: false,
        displayName: devUser.email || "Dev User",
        isAuthenticated: true,
        authPhase: "authenticated",
        signInWithGoogle: signInWithGoogleRef.current,
        signOut: signOutRef.current,
        clearAuthError: () => setAuthState((prev) => ({ ...prev, authError: null })),
      });
      return;
    }

    if (devTokenUsed.current) return;

    const fallbackTimer = setTimeout(() => {
      setAuthState(prev => {
        if (prev.loading && !prev.isAuthenticated) {
          return { ...prev, loading: false, authPhase: "idle" };
        }
        return prev;
      });
    }, 1200);

    const unsubscribe = onAuthStateChangedCallback(
      (firebaseUser, idToken) => {
        clearTimeout(fallbackTimer);
        if (devTokenUsed.current) return;
        if (exchangeInProgress.current) return;

        if (firebaseUser && idToken) {
          doExchange(idToken);
        } else {
          setAuthState(prev => ({
            ...prev,
            user: null,
            loading: false,
            firebaseIdToken: null,
            examGuardToken: null,
            requiresOnboarding: true,
            displayName: "Guest",
            isAuthenticated: false,
            authPhase: "idle",
            authError: null,
            signInWithGoogle: signInWithGoogleRef.current,
            signOut: signOutRef.current,
            clearAuthError: () => setAuthState(p => ({ ...p, authError: null })),
          }));
        }
      }
    );

    return () => {
      clearTimeout(fallbackTimer);
      unsubscribe();
    };
  }, [doExchange]);

  const signInWithGoogle = useCallback(async () => {
    setAuthState(prev => ({ ...prev, authPhase: "popup", loading: true, authError: null }));
    try {
      const result = await signInWithPopup(auth, googleProvider);
      const idToken = await result.user.getIdToken();
      setAuthState(prev => ({ ...prev, authPhase: "exchanging" }));
      await doExchange(idToken);
    } catch (error: unknown) {
      console.error("[ExamGuard] Google sign-in failed:", error);
      let msg = "Sign-in was cancelled or failed. Please try again.";
      const errObj = error as { code?: string; message?: string };
      if (errObj?.code === "auth/popup-closed-by-user") {
        msg = "Sign-in popup was closed. Please try again.";
      } else if (errObj?.code === "auth/network-request-failed") {
        msg = "Network error. Please check your connection and try again.";
      } else if (errObj?.message && !errObj.message.includes("popup")) {
        msg = errObj.message;
      }
      setAuthState(prev => ({
        ...prev,
        loading: false,
        authPhase: "error",
        authError: msg,
        signInWithGoogle: signInWithGoogleRef.current,
        signOut: signOutRef.current,
        clearAuthError: () => setAuthState(p => ({ ...p, authError: null })),
      }));
    }
  }, [doExchange]);

  const signInAsDev = useCallback(async (role: UserRole = "ADMIN") => {
    if (process.env.NODE_ENV === "production") return;
    try {
      setAuthState(prev => ({ ...prev, loading: true, authPhase: "exchanging" }));
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${apiUrl}/api/v1/auth/dev/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ role }),
      });
      if (!res.ok) {
        throw new Error("Dev login request failed");
      }
      const data = await res.json();
      if (typeof window !== "undefined") {
        sessionStorage.setItem("eg_dev_token", data.token);
      }
      devTokenUsed.current = true;
      setTokenGetter(() => data.token);
      setAuthState({
        ...AuthStateDefault,
        user: data.user,
        loading: false,
        examGuardToken: data.token,
        requiresOnboarding: false,
        displayName: data.user.email || `Dev ${role}`,
        isAuthenticated: true,
        authPhase: "authenticated",
        signInWithGoogle: signInWithGoogleRef.current,
        signOut: signOutRef.current,
        signInAsDev,
        clearAuthError: () => setAuthState(prev => ({ ...prev, authError: null })),
      });
    } catch (err: unknown) {
      setAuthState(prev => ({
        ...prev,
        loading: false,
        authPhase: "error",
        authError: (err as Error).message || "Dev sign in failed",
      }));
    }
  }, []);

  const handleSignOut = useCallback(async () => {
    if (typeof window !== "undefined") {
      sessionStorage.removeItem("eg_dev_token");
    }
    devTokenUsed.current = false;
    setTokenGetter(() => null);
    try {
      await firebaseSignOut();
    } catch (error) {
      console.error("[ExamGuard] Sign out error:", error);
    }
    setAuthState({
      ...AuthStateDefault,
      loading: false,
      authPhase: "idle",
      signInWithGoogle: signInWithGoogleRef.current,
      signOut: signOutRef.current,
      signInAsDev,
      clearAuthError: () => setAuthState(p => ({ ...p, authError: null })),
    });
  }, [signInAsDev]);

  useEffect(() => {
    signInWithGoogleRef.current = signInWithGoogle;
    signOutRef.current = handleSignOut;
  }, [signInWithGoogle, handleSignOut]);

  // Set the token during render so child effects (dashboard fetches) see it.
  // A later effect would run after those children and the first request would
  // go out without Authorization.
  if (authState.examGuardToken) {
    setTokenGetter(() => authState.examGuardToken);
  }

  useEffect(() => {
    setTokenGetter(() => authState.examGuardToken);
  }, [authState.examGuardToken]);

  return (
    <AuthContext
      value={{
        user: authState.user,
        loading: authState.loading,
        firebaseIdToken: authState.firebaseIdToken,
        examGuardToken: authState.examGuardToken,
        requiresOnboarding: authState.requiresOnboarding,
        displayName: authState.displayName,
        isAuthenticated: authState.isAuthenticated,
        signInWithGoogle,
        signOut: handleSignOut,
        signInAsDev,
        authPhase: authState.authPhase,
        authError: authState.authError,
        clearAuthError: () => setAuthState(p => ({ ...p, authError: null })),
      }}
    >
      {children}
    </AuthContext>
  );
};

export const useAuthState = (): AuthState => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuthState must be used within an AuthProvider");
  }
  return context;
};
