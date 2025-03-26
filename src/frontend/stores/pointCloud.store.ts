import {defineStore} from 'pinia';
import {computed, markRaw, ref} from 'vue';
import * as THREE from 'three';
import {PointCloudData, SegmentedPointCloud} from '@/types/pointCloud.types';
import {pointCloudService} from '@/services/pointCloud.service';
import {GridSpatialIndexUtil} from '@/utils/gridSpatialIndex.util';
import {PerformanceLoggerUtil} from '@/utils/performanceLogger.util';
import {threeJsService} from '@/services/threeJs.service';

export const usePointCloudStore = defineStore('pointCloud', () => {
  // State
  const pointCloudData = ref<PointCloudData>({
    file: null,
    pointCount: 0,
    positions: null,
    originalColors: null,
    currentColors: null,
    geometry: null,
    boundingBox: null,
    pointSize: 0.03
  });

  const isLoading = ref(false);
  const loadingProgress = ref<number | null>(null);
  const loadingError = ref<string | null>(null);
  const spatialIndex = ref<GridSpatialIndexUtil | null>(null);
  const segmentedPointCloud = ref<SegmentedPointCloud | null>(null);

  // Getters
  const hasPointCloud = computed(() => pointCloudData.value.pointCount > 0);
  const isSegmented = computed(() => segmentedPointCloud.value !== null);
  const boundingBox = computed(() => pointCloudData.value.boundingBox);

  // Actions
  const loadPointCloud = async (file: File): Promise<void> => {
    if (!file || isLoading.value) {
      return;
    }

    // Reset state
    isLoading.value = true;
    loadingProgress.value = 0;
    loadingError.value = null;
    segmentedPointCloud.value = null;

    try {
      PerformanceLoggerUtil.start('load_point_cloud');

      // Load the point cloud
      const pointCloud = await pointCloudService.loadPLYFile(file, {
        pointSize: pointCloudData.value.pointSize,
        onProgress: (percent) => {
          loadingProgress.value = percent;
        }
      });

      // Extract data
      const geometry = pointCloud.geometry;
      const positions = geometry.attributes.position.array as Float32Array;
      const colors = geometry.attributes.color.array as Float32Array;

      // Store data - use markRaw for non-reactive Three.js objects
      pointCloudData.value = {
        file,
        pointCount: geometry.attributes.position.count,
        positions: positions.slice(0), // Clone the array
        originalColors: colors.slice(0), // Clone the array
        currentColors: colors,
        geometry: markRaw(geometry),
        boundingBox: markRaw(new THREE.Box3().setFromBufferAttribute(
            geometry.attributes.position as THREE.BufferAttribute
        )),
        pointSize: (pointCloud.material as THREE.PointsMaterial).size
      };

      // Set in Three.js service
      threeJsService.setPointCloud(pointCloud);

      // Build spatial index
      spatialIndex.value = pointCloudService.buildSpatialIndex(geometry);

      PerformanceLoggerUtil.end('load_point_cloud');
      console.log(`Loaded point cloud with ${pointCloudData.value.pointCount} points`);

    } catch (error) {
      console.error('Error loading point cloud:', error);
      loadingError.value = error instanceof Error ? error.message : 'Unknown error loading point cloud';
      throw error;
    } finally {
      isLoading.value = false;
      loadingProgress.value = null;
    }
  };

  const resetColors = (): void => {
    if (!pointCloudData.value.geometry) return;
    pointCloudService.resetColors(pointCloudData.value);
  };

  const centerCamera = (): void => {
    const context = threeJsService.getContext();
    if (!context.camera || !context.controls || !pointCloudData.value.geometry) {
      return;
    }

    const result = pointCloudService.centerCameraOnPointCloud(
        pointCloudData.value.geometry,
        context.camera,
        context.controls
    );

    // Add axis helper
    threeJsService.addAxisHelper(result.center, result.size);

    return result;
  };

  const applySegmentation = (segmentation: SegmentedPointCloud): boolean => {
    if (!pointCloudData.value.geometry || !segmentation) return false;

    const result = pointCloudService.applySegmentation(
        pointCloudData.value,
        segmentation
    );

    if (result) {
      segmentedPointCloud.value = segmentation;
    }

    return result;
  };

  const cleanup = (): void => {
    // Reset state
    pointCloudData.value = {
      file: null,
      pointCount: 0,
      positions: null,
      originalColors: null,
      currentColors: null,
      geometry: null,
      boundingBox: null,
      pointSize: 0.03
    };

    spatialIndex.value = null;
    segmentedPointCloud.value = null;
  };

  return {
    // State
    pointCloudData,
    isLoading,
    loadingProgress,
    loadingError,
    spatialIndex,
    segmentedPointCloud,

    // Getters
    hasPointCloud,
    isSegmented,
    boundingBox,

    // Actions
    loadPointCloud,
    resetColors,
    centerCamera,
    applySegmentation,
    cleanup
  };
});