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
    const isProcessingSegmentation = ref(false);
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
                positions: positions, // Use reference to original array instead of copying
                originalColors: colors.slice(0), // Clone to preserve original colors
                currentColors: colors, // Reference to the actual buffer
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
            console.log(`Loaded point cloud with ${pointCloudData.value.pointCount.toLocaleString()} points`);

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

    const applySegmentation = (segmentation: SegmentedPointCloud): Promise<boolean> => {
        if (!pointCloudData.value.geometry || !segmentation) return Promise.resolve(false);

        // Show processing state
        isProcessingSegmentation.value = true;
        loadingProgress.value = 0;

        return new Promise((resolve) => {
            pointCloudService.applySegmentation(
                pointCloudData.value,
                segmentation,
                (progress) => {
                    // Update progress indicator
                    loadingProgress.value = Math.floor(progress * 100);
                },
                () => {
                    // Processing complete callback
                    isProcessingSegmentation.value = false;
                    loadingProgress.value = null;
                    segmentedPointCloud.value = segmentation;
                    resolve(true);
                }
            );
        });
    };

    const cleanup = (): void => {
        // Clean up Three.js resources before resetting state
        if (pointCloudData.value.geometry) {
            // Dispose geometry, which automatically disposes all attributes
            pointCloudData.value.geometry.dispose();

            // If we have a pointCloud reference in the context, properly dispose it
            const context = threeJsService.getContext();
            if (context.pointCloud) {
                threeJsService.disposeThreeJsObject(context.pointCloud);
                context.pointCloud = null;
                context.pointGeometry = null;
            }
        }

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

        // Clear spatial index
        spatialIndex.value = null;
        segmentedPointCloud.value = null;

        // Force garbage collection (if available in debug mode)
        if (typeof window !== 'undefined' && (window as any).gc) {
            try {
                (window as any).gc();
            } catch (e) {
                console.log('Unable to force garbage collection');
            }
        }
    };

    return {
        // State
        pointCloudData,
        isLoading,
        isProcessingSegmentation,
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