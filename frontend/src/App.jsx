/**
 * App - application root.
 *
 * Order matters:
 *   AuthProvider  -> must wrap the router because routes read the session
 *   BrowserRouter -> enables client side routing
 *   Toaster      -> global toast notifications (react-hot-toast)
 */
import { BrowserRouter } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import { AuthProvider } from './context/AuthContext';
import AppRoutes from './routes/AppRoutes';

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AppRoutes />
        <Toaster
          position="top-right"
          toastOptions={{
            duration: 3500,
            style: {
              borderRadius: '12px',
              fontSize: '14px',
              boxShadow: '0 8px 24px rgba(15, 23, 42, 0.12)',
            },
            success: { iconTheme: { primary: '#059669', secondary: '#ffffff' } },
            error: { iconTheme: { primary: '#e11d48', secondary: '#ffffff' } },
          }}
        />
      </BrowserRouter>
    </AuthProvider>
  );
}
