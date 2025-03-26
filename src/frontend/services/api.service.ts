import axios, {AxiosError, AxiosRequestConfig, AxiosResponse} from 'axios';
import {SegmentedPointCloud} from '@/types/pointCloud.types';
import {ApiClickData} from '@/types/annotation.types';

// Configuration from environment variables
const BACKEND_URL = import.meta.env.VITE_API_BASE_URL || 'http://172.18.35.200:9500';
const USE_PROXY = import.meta.env.VITE_USE_PROXY !== 'false';

// Interfaces for API requests and responses
export interface InferenceRequest {
    clickData: ApiClickData;
    cubeSize: number;
    objectNames: string[];
}

export interface InferenceResponse {
    message: string;
    segmentedPointCloud: SegmentedPointCloud;
}

export interface MaskObjectDetectionRequest {
    mask: number[];
}

export interface MaskObjectDetectionResult {
    selected_views: number[];
    description: string;
    label: string;
    cost?: number;
}

export interface MaskObjectDetectionResponse {
    message: string;
    result: MaskObjectDetectionResult[];
}

export interface ApiErrorInfo {
    message: string;
    status?: number;
    data?: any;
    isNetworkError: boolean;
}

// Create axios instance with base URL
export const api = axios.create({
    baseURL: USE_PROXY ? '/api' : `${BACKEND_URL}/api`,
    headers: {
        'Content-Type': 'application/json'
    },
    // Increase timeout for larger point cloud files
    timeout: 120000, // 2 minutes
    // Don't include credentials since we're using a wildcard CORS policy
    withCredentials: false
});

// Log connectivity info in development
if (import.meta.env.DEV) {
    console.log(`API configured with ${USE_PROXY ? 'proxy to' : 'direct connection to'} ${BACKEND_URL}`);
}

// Helper function to extract meaningful error messages
function extractErrorInfo(error: AxiosError): ApiErrorInfo {
    if (error.response) {
        const data = error.response.data;
        const status = error.response.status;
        let message = `Server error ${status}`;

        if (typeof data === 'object' && data !== null) {
            // Use type assertion to specify expected properties
            const errorData = data as { detail?: string; message?: string; };
            message = errorData.detail || errorData.message || JSON.stringify(data);
        } else if (typeof data === 'string') {
            message = data;
        }

        return {
            message,
            status,
            data,
            isNetworkError: false
        };
    }

    if (error.request) {
        return {
            message: 'No response received from server. Check your connection.',
            isNetworkError: true
        };
    }

    return {
        message: error.message || 'Unknown error occurred',
        isNetworkError: false
    };
}

// Track retry state
let isRetrying = false;

// Add request/response interceptors for debugging and error handling
api.interceptors.request.use(
    config => {
        if (import.meta.env.DEV) {
            console.log(`API Request: ${config.method?.toUpperCase()} ${config.url}`);
        }
        return config;
    },
    error => {
        console.error('API Request Error:', error);
        return Promise.reject(error);
    }
);

api.interceptors.response.use(
    response => response,
    async (error: AxiosError) => {
        // Handle network errors and connection issues
        if (error.code === 'ECONNABORTED' && !isRetrying) {
            isRetrying = true;
            console.warn('Request timeout - retrying with extended timeout');

            const originalRequest = error.config as AxiosRequestConfig;
            if (originalRequest) {
                originalRequest.timeout = 240000; // 4 minutes on retry

                return api(originalRequest).finally(() => {
                    isRetrying = false;
                });
            }
        } else if (!error.response) {
            console.error(`Network error connecting to backend at ${BACKEND_URL}`);
        } else {
            console.error(`API Error (${error.response.status}):`, error.response.data);
        }

        // Always reset retry flag on non-timeout errors
        isRetrying = false;

        return Promise.reject(error);
    }
);

/**
 * API Service for interacting with the backend
 */
class ApiService {
    /**
     * Upload a point cloud file to the server
     * @param file File containing the point cloud
     * @returns Promise with upload response
     */
    async uploadPointCloud(file: File): Promise<AxiosResponse<any>> {
        // Validate file before upload
        if (!file.name.toLowerCase().endsWith('.ply')) {
            return Promise.reject(new Error('Invalid file type. Only PLY files are supported.'));
        }

        // Check file size (50MB max)
        const MAX_SIZE_MB = 50;
        if (file.size > MAX_SIZE_MB * 1024 * 1024) {
            return Promise.reject(new Error(`File too large. Maximum size is ${MAX_SIZE_MB}MB.`));
        }

        // Create a new FormData instance
        const formData = new FormData();

        // Append the file with the correct field name expected by FastAPI
        formData.append('file', file);

        console.log(`Uploading file ${file.name} (${(file.size / 1024 / 1024).toFixed(2)} MB)`);

        // Use the correct endpoint path - always include /api
        const endpoint = '/api/upload';
        console.log(`Making upload request to: ${endpoint}`);

        try {
            return await axios({
                method: 'post',
                url: endpoint,
                data: formData,
                baseURL: USE_PROXY ? '' : BACKEND_URL,
                // DO NOT set Content-Type header manually for FormData
                // Let the browser set it with the correct boundary
                headers: {
                    // Add debug header to track requests
                    'X-Client-Info': 'Frontend-Upload'
                },
                timeout: 120000,
                onUploadProgress: (progressEvent) => {
                    const percentCompleted = Math.round((progressEvent.loaded * 100) / (progressEvent.total || 1));
                    console.log(`Upload progress: ${percentCompleted}%`);
                }
            });
        } catch (error) {
            console.error('Upload error details:', error);

            if (axios.isAxiosError(error) && error.response) {
                console.error('Response status:', error.response.status);
                console.error('Response headers:', error.response.headers);
                console.error('Response data:', error.response.data);
            } else if (axios.isAxiosError(error) && error.request) {
                console.error('No response received from server');
            }

            return Promise.reject(error);
        }
    }

    /**
     * Run inference on the current point cloud with the provided click data
     * @param request Inference request data
     * @returns Promise with segmentation results
     */
    async runInference(request: InferenceRequest): Promise<AxiosResponse<InferenceResponse>> {
        // Log more details to help debug
        console.log('Running inference with:', {
            objectCount: Object.keys(request.clickData.clickPositions).length - 1, // Subtract background
            clickCount: Object.values(request.clickData.clickPositions).flat().length,
            cubeSize: request.cubeSize
        });

        // Validate click data before sending
        if (!request.clickData || !request.cubeSize || !request.objectNames) {
            return Promise.reject(new Error('Invalid inference request: missing required fields'));
        }

        // Ensure all objects have corresponding click data
        for (const objKey in request.clickData.clickPositions) {
            const positions = request.clickData.clickPositions[objKey];
            const timeIndices = request.clickData.clickTimeIdx[objKey];

            if (!timeIndices || positions.length !== timeIndices.length) {
                return Promise.reject(
                    new Error(`Mismatch in click data for object ${objKey}: positions and timeIndices don't match`)
                );
            }
        }

        try {
            // Make request
            return await api.post<InferenceResponse>('/infer', request);
        } catch (error) {
            // Enhanced error logging
            console.error('Inference request failed:', error);
            if (axios.isAxiosError(error) && error.response) {
                console.error('Response status:', error.response.status);
                console.error('Response data:', error.response.data);
            }
            return Promise.reject(error);
        }
    }

    /**
     * Run mask-based object detection on the segmented point cloud
     * @param mask Array of integer values representing the segmentation mask
     * @returns Promise with object detection results
     */
    async runMaskObjectDetection(mask: number[]): Promise<AxiosResponse<MaskObjectDetectionResponse>> {
        console.log('Running object detection with mask of length:', mask.length);

        try {
            return await api.post<MaskObjectDetectionResponse>('/mask_obj_detection', {
                mask: mask
            });
        } catch (error) {
            console.error('Object detection failed:', error);
            if (axios.isAxiosError(error) && error.response) {
                console.error('Response status:', error.response.status);
                console.error('Response data:', error.response.data);
            }
            return Promise.reject(error);
        }
    }

    /**
     * Download the segmentation results
     * @returns Promise with blob data for download
     */
    async downloadResults(): Promise<AxiosResponse<Blob>> {
        try {
            return await api.get('/download-results', {
                responseType: 'blob'
            });
        } catch (error) {
            console.error('Download failed:', error);
            return Promise.reject(error);
        }
    }

    /**
     * Get formatted error information from an API error
     * @param error The error object from an API call
     * @returns A structured error info object
     */
    getErrorInfo(error: any): ApiErrorInfo {
        if (axios.isAxiosError(error)) {
            return extractErrorInfo(error);
        }

        return {
            message: error?.message || 'Unknown error',
            isNetworkError: false
        };
    }

    /**
     * Get a user-friendly error message
     * @param error The error object
     * @param defaultMessage Default message to use if extraction fails
     * @returns A user-friendly error message
     */
    getErrorMessage(error: any, defaultMessage: string = 'An error occurred'): string {
        const errorInfo = this.getErrorInfo(error);
        return errorInfo.message || defaultMessage;
    }
}

// Export a singleton instance
export const apiService = new ApiService();