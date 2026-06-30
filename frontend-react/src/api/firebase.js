import { initializeApp } from 'firebase/app';
import { getAuth, GoogleAuthProvider } from 'firebase/auth';

/**
 * Firebase client configuration object populated from environment variables.
 * @type {Object}
 * @property {string} apiKey - The Firebase API key.
 * @property {string} authDomain - The authorization domain.
 * @property {string} projectId - The Firebase project ID.
 * @property {string} storageBucket - The storage bucket URI.
 * @property {string} messagingSenderId - The sender ID for cloud messaging.
 * @property {string} appId - The Firebase app identification string.
 */
const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID
};

/**
 * The initialized Firebase Application instance.
 * @type {import("firebase/app").FirebaseApp}
 */
const app = initializeApp(firebaseConfig);

/**
 * Firebase Authentication service instance. Used across the application for managing session state.
 * @type {import("firebase/auth").Auth}
 */
export const auth = getAuth(app);

/**
 * Google Authentication provider instance configured for popup sign-ins.
 * @type {GoogleAuthProvider}
 */
export const googleProvider = new GoogleAuthProvider();

