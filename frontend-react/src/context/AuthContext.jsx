import React, { createContext, useContext, useEffect, useState } from 'react';
import { auth } from '../api/firebase';
import { onAuthStateChanged, signOut } from 'firebase/auth';

/**
 * Authentication Context object for storing user authentication status.
 * @type {React.Context<null|{user: import("firebase/auth").User|null, loading: boolean, logout: function(): Promise<void>}>}
 */
const AuthContext = createContext(null);

/**
 * AuthProvider component that wraps the application layout.
 * Listens to Firebase authentication state transitions and updates context value state.
 *
 * @component
 * @param {Object} props - React component props.
 * @param {React.ReactNode} props.children - Child elements to be rendered when loading is complete.
 * @returns {React.JSX.Element|null} The context provider rendering child components once loaded.
 */
export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (currentUser) => {
      setUser(currentUser);
      setLoading(false);
    });
    return () => unsubscribe();
  }, []);

  /**
   * Triggers Firebase signOut method to clear authentication tokens and session data.
   * @returns {Promise<void>} Resolves when sign out is complete.
   */
  const logout = () => signOut(auth);

  return (
    <AuthContext.Provider value={{ user, loading, logout }}>
      {!loading && children}
    </AuthContext.Provider>
  );
};

/**
 * Custom React hook to retrieve the current user session context and session actions.
 * 
 * @returns {{user: import("firebase/auth").User|null, loading: boolean, logout: function(): Promise<void>}} The active authentication context value.
 * @throws {Error} If consumed outside of a nested `<AuthProvider>` structure.
 */
export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

