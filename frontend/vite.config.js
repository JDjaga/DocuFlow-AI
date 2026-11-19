import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Vite configuration for DocuFlow AI.
//
// - `npm run dev` starts the frontend on http://localhost:5173
// - requests to /api/* are forwarded to FastAPI on port 8001, so the
//   browser never needs to know the backend URL during development
//   (this also avoids CORS issues completely).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8001',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    // Split heavy vendor libraries into their own chunks so the app code
    // loads first and vendors are cached separately between deploys.
    rollupOptions: {
      output: {
        manualChunks: {
          'vendor-react': ['react', 'react-dom', 'react-router-dom'],
          'vendor-charts': ['recharts'],
          'vendor-motion': ['framer-motion'],
          'vendor-ui': ['axios', 'lucide-react', 'react-hot-toast'],
        },
      },
    },
    chunkSizeWarningLimit: 900,
  },
});
