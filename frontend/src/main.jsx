import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';

/**
 * React entry point.
 * - loads the global stylesheet
 * - renders <App /> inside StrictMode (double-invokes effects in dev,
 *   which helps catch missing cleanup code)
 */
ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
