/**
 * Firebase Authentication configuration for ExamGuard.
 *
 * This module provides:
 * 1. Firebase app initialization using the public web config
 * 2. Google sign-in with Firebase Authentication
 * 3. Firebase ID token retrieval for server-side verification
 * 4. Sign-out functionality
 *
 * IMPORTANT: Never store service account credentials or private keys in frontend code.
 * The Firebase web config is public information (apiKey, projectId, etc.) but does
 * not expose private signing keys. Token verification happens server-side in the
 * FastAPI backend using the Firebase Admin SDK.
 */

import {
  getAuth,
  signInWithPopup,
  signOut as firebaseSignOut,
  onAuthStateChanged,
  GoogleAuthProvider,
} from "firebase/auth";
import {
  getFirestore,
  doc,
  getDoc,
  setDoc,
  onSnapshot,
} from "firebase/firestore";
import { app, analytics } from "./firebase_init";

export {
  signInWithPopup,
};

/** Firebase Auth instance - always available after init */
export const auth = getAuth(app);

/** Firestore instance - for user data persistence */
export const db = getFirestore(app);

/** Google Auth Provider configured for ExamGuard */
export const googleProvider = new GoogleAuthProvider();
googleProvider.setCustomParameters({
  // Force re-consent and prompt for account selection
  prompt: "select_account",
});

/**
 * Initiate Google sign-in flow.
 *
 * Uses popup mode on desktop and can be adapted for mobile.
 * The popup returns a Firebase User with ID token usable for server verification.
 *
 * @returns Promise resolving to { user, idToken: string }
 * @throws Error if sign-in is cancelled or fails
 */
export async function signInWithGoogle(): Promise<{
  user: any;
  idToken: string;
}> {
  const provider = googleProvider;
  const result = await signInWithPopup(auth, provider);
  const user = result.user;

  // Get the ID token for server-side verification
  // This is a Firebase ID token (JWT) signed by Firebase auth
  const idToken = await user.getIdToken();

  return { user, idToken };
}

/**
 * Sign out from Firebase and ExamGuard session.
 *
 * Clears both the Firebase session and any ExamGuard JWT.
 *
 * @returns Promise resolving when sign-out is complete
 */
export async function signOut(): Promise<void> {
  await firebaseSignOut(auth);
}

/**
 * Get the current Firebase user ID token.
 *
 * This should be sent to the backend /auth/firebase/exchange endpoint
 * for verification and ExamGuard user mapping.
 *
 * @returns Promise resolving to ID token string, or null if not authenticated
 */
export async function getCurrentIdToken(): Promise<string | null> {
  const user = auth.currentUser;
  if (user) {
    return user.getIdToken();
  }
  return null;
}

/**
 * Set up authentication state listener.
 *
 * Calls the provided callback whenever the auth state changes.
 * Useful for React component auth state management.
 *
 * @param callback Called with { user: any | null, idToken: string | null }
 * @returns Unsubscribe function
 */
export function onAuthStateChangedCallback(
  callback: (user: any | null, idToken: string | null) => void
) {
  return onAuthStateChanged(auth, (user) => {
    if (user) {
      user.getIdToken()
        .then((token) => callback(user, token))
        .catch((err) => callback(user, null));
    } else {
      callback(user, null);
    }
  });
}

/**
 * Fetch the ExamGuard user data from the backend using the Firebase ID token.
 *
 * This is the bridge between Firebase authentication and ExamGuard's RBAC system.
 * The token should be sent to POST /api/v1/auth/firebase/exchange
 *
 * @param firebaseIdToken The Firebase ID token from getCurrentIdToken()
 * @returns Promise resolving to ExamGuard user session
 */
export async function exchangeFirebaseForExamGuard(
  firebaseIdToken: string,
): Promise<{
  user: {
    id: number;
    email: string | null;
    full_name: string | null;
    role: string;
    is_active: boolean;
    firebase_uid: string | null;
  };
  token: string; // ExamGuard JWT
  requires_onboarding: boolean;
}> {
  const response = await fetch("/api/v1/auth/firebase/exchange", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      firebaseToken: firebaseIdToken,
    }),
  });

  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(
      errorData.detail || "Authentication exchange failed",
    );
  }

  return response.json();
}

/**
 * Check if the user is currently authenticated with Firebase.
 *
 * @returns Boolean indicating auth state
 */
export function isAuthenticated(): boolean {
  const user = auth.currentUser;
  return !!user;
}

/**
 * Get the current user's display name or email.
 *
 * @returns User's display name, email, or "Guest" if not authenticated
 */
export function getUserDisplayName(): string {
  const user = auth.currentUser;
  if (!user) return "Guest";

  if (user.displayName) return user.displayName;
  if (user.email) return user.email;
  return "User";
}