import {ref, Ref} from 'vue';
import * as THREE from 'three';
import {GridSpatialIndex, SpatialIndexOptions} from '@/utils/GridSpatialIndex';
import {PointCloudData} from '@/types/PointCloud';
import {PerformanceLogger} from '@/utils/performance-logger';

interface UseSpatialIndexOptions {
    // Reference to point cloud data
    pointCloudData?: Ref<PointCloudData>;
    // Default cell size, if not calculated automatically
    defaultCellSize?: number;
}

/**
 * Composable for managing spatial indexing
 */
export function useSpatialIndex(options?: UseSpatialIndexOptions) {
    // Spatial index reference
    const spatialIndex = ref<GridSpatialIndex | null>(null);

    // Calculated optimal cell size
    const cellSize = ref<number>(options?.defaultCellSize || 0.05);

    /**
     * Build the spatial index from the point cloud geometry
     * @param geometry Geometry to index, or use from options
     * @param buildOptions Additional build options
     * @returns The built spatial index or null if failed
     */
    const buildIndex = (
        geometry?: THREE.BufferGeometry,
        buildOptions?: SpatialIndexOptions
    ): GridSpatialIndex | null => {
        // Use provided geometry or from options
        const geom = geometry || options?.pointCloudData?.value?.geometry;

        if (!geom || !geom.attributes.position) {
            console.error('Cannot build spatial index: no geometry available');
            return null;
        }

        PerformanceLogger.start('build_spatial_index');

        try {
            // Calculate optimal cell size if not provided
            if (!buildOptions?.cellSize && !options?.defaultCellSize) {
                const boundingBox = new THREE.Box3().setFromBufferAttribute(
                    geom.attributes.position as THREE.BufferAttribute
                );

                const size = new THREE.Vector3();
                boundingBox.getSize(size);

                const maxDimension = Math.max(size.x, size.y, size.z);
                const pointCount = geom.attributes.position.count;

                // Adjust cell size based on point count and dimensions
                if (pointCount > 1000000) {
                    cellSize.value = maxDimension / 30;
                } else if (pointCount < 100000) {
                    cellSize.value = maxDimension / 100;
                } else {
                    cellSize.value = maxDimension / 50;
                }
            } else {
                cellSize.value = buildOptions?.cellSize || options?.defaultCellSize || 0.05;
            }

            // Create and build index
            spatialIndex.value = new GridSpatialIndex(cellSize.value);
            spatialIndex.value.build(
                geom.attributes.position.array as Float32Array,
                buildOptions
            );

            console.log(`Built spatial index with cell size ${cellSize.value} for ${geom.attributes.position.count} points`);

            // Use a type assertion to tell TypeScript that this is indeed a GridSpatialIndex
            return spatialIndex.value as GridSpatialIndex;
        } catch (error) {
            console.error('Error building spatial index:', error);
            return null;
        } finally {
            PerformanceLogger.end('build_spatial_index');
        }
    };

    /**
     * Find points within a cube centered at the position
     * @param position Center position [x,y,z]
     * @param size Half-width of the cube
     * @returns Array of point indices or empty array if no index
     */
    const findPointsInCube = (position: number[], size: number): number[] => {
        if (!spatialIndex.value) return [];

        return spatialIndex.value.findPointsInCube(position, size);
    };

    /**
     * Clear the spatial index
     */
    const clearIndex = (): void => {
        spatialIndex.value = null;
    };

    return {
        spatialIndex,
        cellSize,
        buildIndex,
        findPointsInCube,
        clearIndex
    };
}