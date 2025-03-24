import {ref} from 'vue';
import * as THREE from 'three';
import {PointCloudData} from '@/types/PointCloud';
import {pointCloudService} from '@/services/PointCloudService';
import {PerformanceLogger} from '@/utils/performance-logger';
import {threeJsService} from '@/services/ThreeJsService';
import {GridSpatialIndex} from '@/utils/GridSpatialIndex';

/**
 * Composable for loading and managing point cloud data
 */
export function usePointCloudLoader() {
    // Point cloud data
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

    // Loading state
    const isLoading = ref(false);
    const loadingProgress = ref<number | null>(null);
    const loadingError = ref<string | null>(null);

    // Spatial index
    const spatialIndex = ref<GridSpatialIndex | null>(null);

    /**
     * Load a point cloud from a PLY file
     * @param file PLY file to load
     * @returns Promise that resolves when loading is complete
     */
    const loadPointCloud = async (file: File): Promise<void> => {
        if (!file || isLoading.value) {
            return;
        }

        // Reset state
        isLoading.value = true;
        loadingProgress.value = 0;
        loadingError.value = null;

        try {
            PerformanceLogger.start('load_point_cloud');

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

            // Store data
            pointCloudData.value = {
                file,
                pointCount: geometry.attributes.position.count,
                positions: positions.slice(0), // Clone the array
                originalColors: colors.slice(0), // Clone the array
                currentColors: colors,
                geometry,
                boundingBox: new THREE.Box3().setFromBufferAttribute(
                    geometry.attributes.position as THREE.BufferAttribute
                ),
                pointSize: (pointCloud.material as THREE.PointsMaterial).size
            };

            // Set in Three.js service
            threeJsService.setPointCloud(pointCloud);

            // Build spatial index
            spatialIndex.value = pointCloudService.buildSpatialIndex(geometry);

            PerformanceLogger.end('load_point_cloud');
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

    /**
     * Reset point cloud colors to original state
     */
    const resetColors = (): void => {
        if (!pointCloudData.value.geometry) return;

        pointCloudService.resetColors(pointCloudData.value);
    };

    /**
     * Clean up resources
     */
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
    };

    /**
     * Center camera on the current point cloud
     */
    const centerCamera = (): void => {
        const context = threeJsService.getContext();
        if (!context.camera || !context.controls || !pointCloudData.value.geometry) {
            return;
        }

        const {center, size} = pointCloudService.centerCameraOnPointCloud(
            pointCloudData.value.geometry,
            context.camera,
            context.controls
        );

        // Add axis helper
        threeJsService.addAxisHelper(center, size);
    };

    return {
        pointCloudData,
        isLoading,
        loadingProgress,
        loadingError,
        spatialIndex,
        loadPointCloud,
        resetColors,
        cleanup,
        centerCamera
    };
}