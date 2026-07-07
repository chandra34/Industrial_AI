import React, { useState } from 'react';
import { auth, googleProvider } from '../api/firebase';
import { signInWithEmailAndPassword, createUserWithEmailAndPassword, signInWithPopup } from 'firebase/auth';
import './Login.css';

/**
 * Login component rendering authentication dialogs.
 * Supports email/password registration (Sign Up), login (Sign In), and Google single sign-on (SSO).
 *
 * @component
 * @returns {React.JSX.Element} The rendered login card interface.
 */
export default function Login({ initialSignUp = false, onClose = null }) {
  const [isSignUp, setIsSignUp] = useState(initialSignUp);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const appName = import.meta.env.VITE_APP_NAME || 'RAG Documents App';

  /**
   * Submits authentication forms. Registers or authenticates users using Firebase Auth methods.
   *
   * @async
   * @param {React.FormEvent} e - Form submission event.
   */
  const handleSubmit = async (e) => {

    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      if (isSignUp) {
        await createUserWithEmailAndPassword(auth, email, password);
      } else {
        await signInWithEmailAndPassword(auth, email, password);
      }
    } catch (err) {
      console.error(err);
      let friendlyMsg = err.message;
      if (err.code === 'auth/user-not-found' || err.code === 'auth/wrong-password' || err.code === 'auth/invalid-credential') {
        friendlyMsg = 'Invalid email or password.';
      } else if (err.code === 'auth/email-already-in-use') {
        friendlyMsg = 'This email is already registered.';
      } else if (err.code === 'auth/weak-password') {
        friendlyMsg = 'Password must be at least 6 characters.';
      }
      setError(friendlyMsg);
    } finally {
      setLoading(false);
    }
  };

  /**
   * Spawns a Google OAuth popup dialog to authenticate users with Google Accounts.
   *
   * @async
   */
  const handleGoogleLogin = async () => {

    setError('');
    setLoading(true);
    try {
      await signInWithPopup(auth, googleProvider);
    } catch (err) {
      console.error(err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-container" style={onClose ? { minHeight: 'auto', width: 'auto', background: 'none', padding: 0 } : {}}>
      <div className="login-card" style={{ position: 'relative' }}>
        {onClose && (
          <button className="modal-close-btn" onClick={onClose} aria-label="Close">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        )}
        <div className="login-header">
          <div className="login-logo">
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 16.5V9.75m0 0l3 3m-3-3l-3 3M6.75 19.5a4.5 4.5 0 01-1.41-8.775 5.25 5.25 0 0110.233-2.33 3 3 0 013.758 3.848A3.752 3.752 0 0118 19.5H6.75z" />
            </svg>
          </div>
          <h1>{appName}</h1>
          <p>{isSignUp ? 'Create your account to start managing PDFs' : 'Sign in to access your secure document space'}</p>
        </div>

        {error && <div className="login-error">{error}</div>}

        <form onSubmit={handleSubmit} className="login-form">
          <div className="form-group">
            <label htmlFor="email">Email Address</label>
            <input
              id="email"
              type="email"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              disabled={loading}
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              disabled={loading}
            />
          </div>

          <button type="submit" className="btn-primary" disabled={loading}>
            {loading ? 'Please wait...' : isSignUp ? 'Sign Up' : 'Sign In'}
          </button>
        </form>

        <div className="divider">
          <span>or</span>
        </div>

        <button onClick={handleGoogleLogin} className="btn-google" disabled={loading}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
            <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
            <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
            <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z" fill="#FBBC05"/>
            <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
          </svg>
          Continue with Google
        </button>

        <div className="login-footer">
          {isSignUp ? (
            <span>
              Already have an account?{' '}
              <button onClick={() => { setIsSignUp(false); setError(''); }} type="button" disabled={loading}>
                Sign In
              </button>
            </span>
          ) : (
            <span>
              Don't have an account?{' '}
              <button onClick={() => { setIsSignUp(true); setError(''); }} type="button" disabled={loading}>
                Sign Up
              </button>
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
