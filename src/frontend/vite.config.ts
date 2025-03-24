import {defineConfig, loadEnv} from 'vite';
import vue from '@vitejs/plugin-vue';
import path from 'path';

// Load environment variables from .env files
// This properly loads VITE_* environment variables from .env files
export default defineConfig(({command, mode}) => {
    // Load env file based on `mode` in the current directory.
    // Set the third parameter to '' to load all env regardless of the `VITE_` prefix.
    const env = loadEnv(mode, process.cwd(), '');

    // Get API URL from env or use default
    const apiBaseUrl = env.VITE_API_BASE_URL || 'http://172.18.35.200:9001';

    console.log(`Using API Base URL: ${apiBaseUrl}`);

    return {
        plugins: [
            vue(),
            // Consider adding the following plugins for better debugging:
            // vitePluginVueDevtools() - Enhances Vue debugging experience
            // For example: import vitePluginVueDevtools from 'vite-plugin-vue-devtools'
        ],
        resolve: {
            alias: {
                '@': path.resolve(__dirname, './')
            }
        },
        server: {
            port: 3001,
            proxy: {
                '/api': {
                    target: apiBaseUrl,
                    changeOrigin: true,
                    secure: false,
                    rewrite: (path) => path, // Don't rewrite paths - keep /api prefix
                    configure: (proxy, _options) => {
                        proxy.on('error', (err, _req, _res) => {
                            console.log('proxy error', err);
                        });
                        proxy.on('proxyReq', (proxyReq, req, _res) => {
                            console.log('Sending Request:', req.method, req.url);
                        });
                        proxy.on('proxyRes', (proxyRes, req, _res) => {
                            console.log('Received Response:', proxyRes.statusCode, req.url);
                        });
                    },
                }
            },
            cors: true
        }
    };
});