import {SegmentedPointCloud} from '@/types/pointCloud.types';
import {ApiClickData} from '@/types/annotation.types';

// Export updated MaskObjectRecognitionResult interface with optional obj_id field
export interface MaskObjectRecognitionResult {
    selected_views: number[];
    description: string;
    label: string;
    cost?: number;
    obj_id?: number; // Add obj_id field for better type support
}

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

export interface MaskObjectRecognitionRequest {
    mask: number[];
}

export interface MaskObjectRecognitionResult {
    selected_views: number[];
    description: string;
    label: string;
    cost?: number;
}

export interface MaskObjectRecognitionResponse {
    message: string;
    result: MaskObjectRecognitionResult[];
}

export interface ApiErrorInfo {
    message: string;
    status?: number;
    data?: any;
    isNetworkError: boolean;
}