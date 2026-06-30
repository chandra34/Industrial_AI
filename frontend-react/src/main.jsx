import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './App.css';
import { AuthProvider } from './context/AuthContext';

/**
 * Entry point for the React application.
 * Renders the application wrapped inside React.StrictMode and AuthProvider
 * to ensure context propagation and strict runtime checks.
 */
ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <AuthProvider>
      <App />
    </AuthProvider>
  </React.StrictMode>
);

