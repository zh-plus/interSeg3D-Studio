// Export updated MaskObjectDetectionResult interface with optional obj_id field
export interface MaskObjectDetectionResult {
    selected_views: number[];
    description: string;
    label: string;
    cost?: number;
    obj_id?: number; // Add obj_id field for better type support
}