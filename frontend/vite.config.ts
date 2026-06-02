/// <reference types="vitest" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const CONTRACT_API = 'https://gs1vczg5s7.execute-api.us-east-1.amazonaws.com/prod';
const SCHEMA_API   = 'https://ootbzgzcp0.execute-api.us-east-1.amazonaws.com/prod';
const NL_QUERY_API = 'https://u02uvpqhg1.execute-api.us-east-1.amazonaws.com/prod';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api/schema': { target: SCHEMA_API, changeOrigin: true },
      '/api/query':  { target: NL_QUERY_API, changeOrigin: true },
      '/api':        { target: CONTRACT_API, changeOrigin: true },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test-setup.ts'],
  },
});
