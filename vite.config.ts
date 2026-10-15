import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig({base:'/value-daily/',plugins:[react()],build:{outDir:'dist'}});
