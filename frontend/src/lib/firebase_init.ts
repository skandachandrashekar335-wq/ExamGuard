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
 */

const firebaseConfig = {
  // Firebase project configuration - public web app settings
  apiKey: "AIzaSyBotQRBro543rZAvblrLbP1BkvniHZ4-Qk",
  authDomain: "ggvoting-8ac37.firebaseapp.com",
  projectId: "ggvoting-8ac37",
  storageBucket: "ggvoting-8ac37.firebasestorage.app",
  messagingSenderId: "832618179222",
  appId: "1:832618179222:web:59847d8441b6a7636ab0b7",
  measurementId: "G-7XMZ3X0YHH",
};

// Initialize Firebase app (client-side)
import { initializeApp } from "firebase/app";
import { getAnalytics } from "firebase/analytics";

export const app = initializeApp(firebaseConfig);
export const analytics = getAnalytics(app);