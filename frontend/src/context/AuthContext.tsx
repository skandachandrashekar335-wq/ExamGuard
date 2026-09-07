/**
 * ExamGuard Authentication Context.
 *
 * Manages the authentication state bridging Firebase Authentication and
 * ExamGuard's RBAC system.
 *
 * The AuthContext provides:
 * - current user state (ExamGuard user, not Firebase user)
 * - loading state during authentication flow
 * - signInWithGoogle() - initiates Firebase Google sign-in
 * - signOut() - clears both Firebase and ExamGuard sessions
 * - firebaseIdToken - the current Firebase ID token for API exchange
 * - requiresOnboarding - whether the user needs to complete onboarding
 * - role-based UI visibility
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

import { createContext, useContext, useState, useEffect, ReactNode } from "react";
import {
  signInWithPopup,
  signOut as firebaseSignOut,
  exchangeFirebaseForExamGuard,
  onAuthStateChangedCallback,
  auth,
  googleProvider,
} from "../lib/firebase";
import { setTokenGetter } from "../lib/api";

// Types for the auth context state
export type UserRole = "ADMIN" | "OPERATOR" | "REVIEWER";

export interface AuthUser {
  id: number;
  email: string | null;
  full_name: string | null;
  role: UserRole;
  is_active: boolean;
  firebase_uid: string | null;
}

// The public auth state visible to components
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
}

// Default state for the context
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
};

const AuthContext = createContext<AuthState>(AuthStateDefault);

export const useAuth = (): AuthState => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
};

export const AuthProvider: React.FC<{ children: ReactNode }> = ({
  children,
}) => {
  const [authState, setAuthState] = useState<AuthState>(AuthStateDefault);

  // Initialize auth state on component mount
  useEffect(() => {
    // Set up Firebase auth state listener
    const unsubscribe = onAuthStateChangedCallback(
      (firebaseUser, idToken) => {
        // idToken can be null during initial state
        if (firebaseUser && idToken) {
          // User is signed in to Firebase - exchange token for ExamGuard session
          exchangeFirebaseForExamGuard(idToken)
            .then((result) => {
              const user: AuthUser = {
                id: result.user.id,
                email: result.user.email,
                full_name: result.user.full_name,
                role: result.user.role as UserRole,
                is_active: result.user.is_active,
                firebase_uid: result.user.firebase_uid,
              };

              setAuthState({
                user,
                loading: false,
                firebaseIdToken: idToken,
                examGuardToken: result.token,
                requiresOnboarding: result.requires_onboarding,
                displayName: result.user.email
                  ? `${result.user.full_name || ""} (${result.user.email})`
                  : "User",
                isAuthenticated: true,
                signInWithGoogle: async () => {},
                signOut: async () => {},
              });
            })
            .catch((error) => {
              console.error("Auth exchange failed:", error);
              // Fallback: create a minimal user and mark as needing onboarding
              setAuthState({
                user: null,
                loading: false,
                firebaseIdToken: idToken ?? null,
                examGuardToken: null,
                requiresOnboarding: true,
                displayName: "User",
                isAuthenticated: false,
                signInWithGoogle: async () => {},
                signOut: async () => {},
              });
            });
        } else {
          // User signed out from Firebase or initial state
          firebaseSignOut()
            .then(() => {
              setAuthState({
                user: null,
                loading: false,
                firebaseIdToken: null,
                examGuardToken: null,
                requiresOnboarding: true,
                displayName: "Guest",
                isAuthenticated: false,
                signInWithGoogle: async () => {},
                signOut: async () => {},
              });
            })
            .catch((err) => {
              console.error("Sign out error:", err);
              setAuthState({
                user: null,
                loading: false,
                firebaseIdToken: null,
                examGuardToken: null,
                requiresOnboarding: true,
                displayName: "Guest",
                isAuthenticated: false,
                signInWithGoogle: async () => {},
                signOut: async () => {},
              });
            });
        }
      }
    );

    // Cleanup on unmount
    return () => unsubscribe();
  }, []);

  // Initial loading check - the onAuthStateChangedCallback will handle
  // determining if there's already a session. This effect runs after
  // the callback is set up.
  useEffect(() => {
  }, []);

  const signInWithGoogle = async () => {
    setAuthState((prev) => ({ ...prev, loading: true }));
    try {
      // Use signInWithPopup directly with the exported googleProvider
      const result = await signInWithPopup(auth, googleProvider);
      const idToken = await result.user.getIdToken();
      const exchangeResult = await exchangeFirebaseForExamGuard(idToken);

      const authUser: AuthUser = {
        id: exchangeResult.user.id,
        email: exchangeResult.user.email,
        full_name: exchangeResult.user.full_name,
        role: exchangeResult.user.role as UserRole,
        is_active: exchangeResult.user.is_active,
        firebase_uid: exchangeResult.user.firebase_uid,
      };

      setAuthState({
        user: authUser,
        loading: false,
        firebaseIdToken: idToken,
        examGuardToken: exchangeResult.token,
        requiresOnboarding: exchangeResult.requires_onboarding,
        displayName: authUser.email
          ? `${authUser.full_name || ""} (${authUser.email})`
          : "User",
        isAuthenticated: true,
        signInWithGoogle: async () => {},
        signOut: async () => {},
      });
    } catch (error: any) {
      console.error("Google sign-in failed:", error);
      setAuthState((prev) => ({
        ...prev,
        loading: false,
        requiresOnboarding: true,
      }));
      throw error;
    }
  };

  const handleSignOut = async () => {
    try {
      // Sign out from Firebase first
      await firebaseSignOut();
      // Clear ExamGuard state
      setAuthState({
        user: null,
        loading: false,
        firebaseIdToken: null,
        examGuardToken: null,
        requiresOnboarding: true,
        displayName: "Guest",
        isAuthenticated: false,
        signInWithGoogle: async () => {},
        signOut: async () => {},
      });
    } catch (error) {
      console.error("Sign out error:", error);
      // Still try to clear local state
      setAuthState({
        user: null,
        loading: false,
        firebaseIdToken: null,
        examGuardToken: null,
        requiresOnboarding: true,
        displayName: "Guest",
        isAuthenticated: false,
        signInWithGoogle: async () => {},
        signOut: async () => {},
      });
    }
  };

  // Initialize API client with token getter
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