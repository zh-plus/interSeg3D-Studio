// Import types from ApiService
import {
  InferenceRequest,
  InferenceResponse,
  MaskObjectDetectionRequest,
  MaskObjectDetectionResponse,
  ApiErrorInfo
} from '@/services/ApiService';

// Export updated MaskObjectDetectionResult interface with optional obj_id field
export interface MaskObjectDetectionResult {
  selected_views: number[];
  description: string;
  label: string;
  cost?: number;
  obj_id?: number; // Add obj_id field for better type support
}

// Re-export types from ApiService for convenience
export {
  InferenceRequest,
  InferenceResponse,
  MaskObjectDetectionRequest,
  MaskObjectDetectionResponse,
  ApiErrorInfo
};