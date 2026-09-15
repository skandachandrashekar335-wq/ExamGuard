/**
 * Firebase initialization configuration for ExamGuard.
 *
 * Public Firebase web configuration. This uses the standard Firebase JS SDK
 * initialization with the apiKey, projectId, etc. that are safe to expose
 * in client-side code.
 *
 * CRITICAL: This configuration does NOT contain:
 * - Service account private keys
 * - Database secrets
 * - Admin SDK credentials
 * - Any information that could compromise Firebase project security
 *
 * The Firebase Admin SDK credentials (service account JSON) MUST remain on the
 * backend only, in environment variables accessed via the FastAPI application.
 *
 * Analytics initialization is browser-only. It must NOT execute during
 * Next.js server-side rendering (Node.js environment has no `window`).
 * The `analytics` export below is null during SSR and resolves in the browser.
 */

const firebaseConfig = {
  // Firebase project configuration - public web app settings
  apiKey: "AIzaSyCRoOlMP-VO6dgg_TeXhwAkRsE94rZG7GQ",
  authDomain: "exam-guard-75675.firebaseapp.com",
  projectId: "exam-guard-75675",
  storageBucket: "exam-guard-75675.firebasestorage.app",
  messagingSenderId: "391945763373",
  appId: "1:391945763373:web:57d1c6193de6abe30956a4",
  measurementId: "G-L38NDKWP89",
};

// Initialize Firebase app (safe for both server and client)
import { initializeApp } from "firebase/app";
export const app = initializeApp(firebaseConfig);

/**
 * Firebase Analytics instance.
 *
 * This is null during server-side rendering (SSR) because the `window`
 * global is not available in Node.js. In a real browser environment,
 * it should be initialized lazily via:
 *   import { analytics } from "@/lib/firebase_init";
 *   // In a "use client" component or effect, call:
 *   // import { getAnalytics } from "firebase/analytics";
 *   // const analyticsInstance = getAnalytics(app);
 *
 * For now, this export is null to prevent the "Window is not defined"
 * runtime error during Next.js server components and static generation.
 */
export const analytics = null as
  | import("firebase/analytics").Analytics
  | null;