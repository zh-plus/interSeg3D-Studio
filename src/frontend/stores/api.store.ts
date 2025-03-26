import {defineStore} from 'pinia';
import {computed, ref} from 'vue';
import {apiService} from '@/services/api.service';
import {InferenceRequest, MaskObjectDetectionResult} from '@/types/apiService.types';
import {usePointCloudStore} from './pointCloud.store';
import {useAnnotationStore} from './annotation.store';
import {useUiStore} from './ui.store';

export const useApiStore = defineStore('api', () => {
  // References to other stores
  const pointCloudStore = usePointCloudStore();
  const annotationStore = useAnnotationStore();
  const uiStore = useUiStore();

  // State
  const isLoading = ref(false);
  const isProcessing = ref(false);
  const isAnalyzing = ref(false);
  const isDownloading = ref(false);
  const processingMessage = ref('');
  const operationLock = ref(false);
  const analysisResults = ref<MaskObjectDetectionResult[]>([]);

  // Computed
  const hasResults = computed(() => analysisResults.value.length > 0);
  const hasClickData = computed(() => annotationStore.clickCount > 0);

  // Helper functions
  const handleApiError = (error: any, defaultMessage: string): string => {
    console.error(defaultMessage, error);

    let errorMessage = defaultMessage;

    if (error.response) {
      console.error('Server error data:', error.response.data);

      // Extract error message from various possible response formats
      const data = error.response.data;
      if (typeof data === 'object' && data !== null) {
        errorMessage = `Server error ${error.response.status}: ${
            data.detail || data.message || JSON.stringify(data)
        }`;
      } else if (typeof data === 'string') {
        errorMessage = `Server error ${error.response.status}: ${data}`;
      } else {
        errorMessage = `Server error ${error.response.status}`;
      }
    } else if (error.request) {
      errorMessage = 'No response from server. Check your connection.';
    } else if (error.message) {
      errorMessage = `Error: ${error.message}`;
    }

    return errorMessage;
  };

  // Actions
  const uploadPointCloud = async (file: File): Promise<boolean> => {
    if (operationLock.value || isProcessing.value) {
      console.warn('Operation in progress. Please wait.');
      return false;
    }

    isProcessing.value = true;
    operationLock.value = true;
    processingMessage.value = 'Uploading to server...';

    try {
      await apiService.uploadPointCloud(file);

      // Reset state
      pointCloudStore.segmentedPointCloud = null;
      uiStore.reset();
      annotationStore.reset();

      processingMessage.value = 'Processing point cloud...';
      return true;
    } catch (error: any) {
      console.error('Error uploading file:', error);
      const errorMessage = handleApiError(error, 'Upload failed');
      throw new Error(errorMessage);
    } finally {
      isProcessing.value = false;
      processingMessage.value = '';
      operationLock.value = false;
    }
  };

  const runSegmentation = async (): Promise<boolean> => {
    if (!hasClickData.value) return false;

    if (operationLock.value || isProcessing.value) {
      console.warn('Operation in progress. Please wait.');
      return false;
    }

    operationLock.value = true;
    isProcessing.value = true;
    processingMessage.value = 'Running segmentation';

    try {
      // Get click data for API
      const clickData = annotationStore.clickDataForApi;

      // Ensure all objects have entries in the click data
      uiStore.objects.forEach((obj, idx) => {
        const objKey = (idx + 1).toString();
        if (!clickData.clickIdx[objKey]) {
          clickData.clickIdx[objKey] = [];
          clickData.clickTimeIdx[objKey] = [];
          clickData.clickPositions[objKey] = [];
        }
      });

      // Prepare inference request
      const request: InferenceRequest = {
        clickData: clickData,
        cubeSize: uiStore.cubeSize,
        objectNames: uiStore.objects.map(obj => obj.name)
      };

      // Call API
      const response = await apiService.runInference(request);

      if (!response.data || !response.data.segmentedPointCloud) {
        console.error('Invalid response format:', response.data);
        throw new Error('Invalid response from server');
      }

      // Apply segmentation
      pointCloudStore.applySegmentation(response.data.segmentedPointCloud);

      // Recreate markers to keep them visible
      annotationStore.recreateMarkers();

      return true;
    } catch (error: any) {
      const errorMessage = handleApiError(error, 'Error running segmentation');
      throw new Error(errorMessage);
    } finally {
      isProcessing.value = false;
      processingMessage.value = '';
      operationLock.value = false;
    }
  };

  const analyzeObjects = async (): Promise<boolean> => {
    if (!pointCloudStore.segmentedPointCloud) return false;

    if (operationLock.value || isProcessing.value) return false;

    isAnalyzing.value = true;
    operationLock.value = true;
    uiStore.showAnalysisDialog = true;
    analysisResults.value = [];

    try {
      const response = await apiService.runMaskObjectDetection(
          pointCloudStore.segmentedPointCloud.segmentation
      );

      if (response.data?.result && response.data.result.length > 0) {
        // Parse results and associate with object IDs if possible
        analysisResults.value = response.data.result.map((item, index) => {
          // Check if the backend provides an explicit object ID
          // If not, we'll try to determine it later
          let objId = null;

          // If the result includes an explicit obj_id field
          if ('obj_id' in item) {
            objId = item.obj_id;
          } else {
            // Try to extract from the label using regex
            const objIdMatch = /(\d+)/.exec(item.label);
            objId = objIdMatch ? parseInt(objIdMatch[0], 10) : null;

            // If still no ID, use index+1 (assuming 1-based IDs)
            if (objId === null) {
              objId = index + 1;
            }
          }

          // Return the result with added objId if found
          return {
            ...item,
            obj_id: objId
          };
        });

        return true;
      } else {
        console.warn('No object analysis results returned');
        return false;
      }
    } catch (error: any) {
      const errorMessage = handleApiError(error, 'Error analyzing objects');
      throw new Error(errorMessage);
    } finally {
      isAnalyzing.value = false;
      operationLock.value = false;
    }
  };

  const applyAnalysisLabel = (data: { label: string, index: number }): boolean => {
    const result = analysisResults.value[data.index];

    // We need to determine which object this result corresponds to
    // First try to extract object ID directly from the result
    let objId = null;

    // Option 1: The result may include an 'obj_id' property
    if ('obj_id' in result && typeof result.obj_id === 'number') {
      objId = result.obj_id;
    }
    // Option 2: Try to extract an ID from the label using regex
    else {
      const objIdMatch = /(\d+)/.exec(result.label);
      if (objIdMatch) {
        objId = parseInt(objIdMatch[0], 10);
      }

      // If no ID found but we have sequential objects and results
      if (objId === null && data.index < uiStore.objects.length) {
        // Use the index+1 as ID (since object IDs typically start at 1)
        objId = data.index + 1;
      }
    }

    if (objId !== null) {
      // Update object info
      return uiStore.updateObjectInfo(objId, {
        name: result.label,
        description: result.description
      });
    }

    return false;
  };

  const applyAllAnalysisResults = (): number => {
    // If there are more results than objects, just apply what we can
    const resultCount = Math.min(analysisResults.value.length, uiStore.objects.length);
    let appliedCount = 0;

    for (let i = 0; i < resultCount; i++) {
      if (applyAnalysisLabel({label: analysisResults.value[i].label, index: i})) {
        appliedCount++;
      }
    }

    return appliedCount;
  };

  const downloadResults = async (): Promise<boolean> => {
    if (!pointCloudStore.segmentedPointCloud) return false;

    // Prevent concurrent operations
    if (operationLock.value || isProcessing.value) return false;

    isDownloading.value = true;
    operationLock.value = true;

    try {
      const response = await apiService.downloadResults();

      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `segmentation_result_${Date.now()}.ply`);
      document.body.appendChild(link);
      link.click();

      // Cleanup
      setTimeout(() => {
        window.URL.revokeObjectURL(url);
        link.remove();
      }, 100);

      return true;
    } catch (error: any) {
      const errorMessage = handleApiError(error, 'Error downloading results');
      throw new Error(errorMessage);
    } finally {
      isDownloading.value = false;
      operationLock.value = false;
    }
  };

  return {
    // State
    isLoading,
    isProcessing,
    isAnalyzing,
    isDownloading,
    processingMessage,
    operationLock,
    analysisResults,

    // Computed
    hasResults,
    hasClickData,

    // Actions
    uploadPointCloud,
    runSegmentation,
    analyzeObjects,
    applyAnalysisLabel,
    applyAllAnalysisResults,
    downloadResults,
    handleApiError
  };
});