import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  // Assets are served under the public /dispatch/ prefix.
  base: '/dispatch/',
});
