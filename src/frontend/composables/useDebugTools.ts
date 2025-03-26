import {ref} from 'vue';
import {apiService} from '@/services/api.service';

/**
 * Composable for debugging tools - only active in development mode
 * This provides programmatic debugging capabilities without requiring UI components
 */
export function useDebugTools() {
    // Only enable in development mode
    const isEnabled = ref(import.meta.env.DEV || false);

    // Debug panel visibility
    const showDebugPanel = ref(false);

    // Toggle debug mode entirely
    const toggleDebugMode = () => {
        isEnabled.value = !isEnabled.value;
        if (!isEnabled.value) {
            showDebugPanel.value = false;
        }
    };

    // Toggle debug panel visibility
    const toggleDebugPanel = () => {
        if (isEnabled.value) {
            showDebugPanel.value = !showDebugPanel.value;
        }
    };

    // Direct file upload testing (replicates functionality from DebugUpload.vue)
    const uploadFile = async (file: File, onUploadProgress?: (percent: number) => void): Promise<any> => {
        if (!isEnabled.value) return null;

        try {
            console.log(`[DEBUG] Uploading file: ${file.name} (${Math.round(file.size / 1024)}KB)`);

            // Use the existing API service for consistency
            const response = await apiService.uploadPointCloud(file);
            console.log('[DEBUG] Upload response:', response.data);

            return response.data;
        } catch (error) {
            console.error('[DEBUG] Upload error:', error);
            const errorInfo = apiService.getErrorInfo(error);
            return {error: true, ...errorInfo};
        }
    };

    // Component-contextualized logging
    const createLogger = (componentName: string) => {
        return {
            log: (...args: any[]) => {
                if (!isEnabled.value) return;
                console.log(`[${componentName}]`, ...args);
            },
            warn: (...args: any[]) => {
                if (!isEnabled.value) return;
                console.warn(`[${componentName}]`, ...args);
            },
            error: (...args: any[]) => {
                if (!isEnabled.value) return;
                console.error(`[${componentName}]`, ...args);
            },
            time: (label: string) => {
                if (!isEnabled.value) return;
                console.time(`[${componentName}] ${label}`);
            },
            timeEnd: (label: string) => {
                if (!isEnabled.value) return;
                console.timeEnd(`[${componentName}] ${label}`);
            }
        };
    };

    return {
        isEnabled,
        showDebugPanel,
        toggleDebugMode,
        toggleDebugPanel,
        uploadFile,
        createLogger
    };
}