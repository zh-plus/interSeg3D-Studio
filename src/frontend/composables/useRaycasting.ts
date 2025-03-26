import { ref, Ref, computed } from 'vue';
import * as THREE from 'three';
import { ClickResult, RaycastResult } from '@/types/Selection';
import { threeJsService } from '@/services/ThreeJsService';
import { PerformanceLogger } from '@/utils/performance-logger';
import { usePointCloudStore } from '@/stores';

interface UseRaycastingOptions {
    // Reference to the container element
    container?: Ref<HTMLElement | null>;
    // Optional cube size override (defaults to using store value)
    cubeSize?: Ref<number>;
}

/**
 * Composable for handling raycasting and point selection
 */
export function useRaycasting(options?: UseRaycastingOptions) {
    // Get the point cloud store
    const pointCloudStore = usePointCloudStore();

    // State
    const isProcessingSelection = ref(false);
    const lastMousePosition = ref<THREE.Vector2 | null>(null);

    // Computed to get the current cube size (from options or defaults)
    const currentCubeSize = computed(() => {
        if (options?.cubeSize?.value !== undefined) {
            return options.cubeSize.value;
        }
        return 0.02; // Default cube size
    });

    /**
     * Update the mouse position for raycasting
     * @param clientX Client X coordinate
     * @param clientY Client Y coordinate
     * @param containerRect Container bounding rectangle (optional, will get latest if not provided)
     * @returns Normalized device coordinates as Vector2
     */
    const updateMousePosition = (
        clientX: number,
        clientY: number,
        containerRect?: DOMRect
    ): THREE.Vector2 => {
        // Always get the latest container rect if not provided
        if (!containerRect && options?.container?.value) {
            containerRect = options.container.value.getBoundingClientRect();
        }

        if (!containerRect) {
            console.error('Container rect not available for mouse position calculation');
            return lastMousePosition.value || new THREE.Vector2(0, 0);
        }

        // Calculate normalized device coordinates (NDC)
        // NDC range is [-1, 1] for both x and y
        const mouseX = ((clientX - containerRect.left) / containerRect.width) * 2 - 1;
        const mouseY = -((clientY - containerRect.top) / containerRect.height) * 2 + 1;

        lastMousePosition.value = new THREE.Vector2(mouseX, mouseY);

        // Debug log for troubleshooting
        console.debug(`Mouse NDC: (${mouseX.toFixed(3)}, ${mouseY.toFixed(3)}) from client (${clientX}, ${clientY}) in container ${containerRect.width.toFixed(0)}x${containerRect.height.toFixed(0)}`);

        return lastMousePosition.value;
    };

    /**
     * Perform raycasting on the point cloud
     * @param threshold Optional raycaster threshold override
     * @returns The raycasting result
     */
    const performRaycast = (threshold?: number): RaycastResult | null => {
        PerformanceLogger.start('raycasting');

        const context = threeJsService.getContext();
        if (!context.raycaster || !context.camera || !context.pointCloud) {
            PerformanceLogger.end('raycasting');
            return null;
        }

        // Set raycaster from camera and mouse position
        if (!lastMousePosition.value) {
            PerformanceLogger.end('raycasting');
            return null;
        }

        context.raycaster.setFromCamera(lastMousePosition.value, context.camera);

        // Set threshold if provided
        if (threshold !== undefined) {
            context.raycaster.params.Points = {threshold};
        } else {
            // Scale threshold with point density if available
            const pointCount = pointCloudStore.pointCloudData.pointCount;
            if (pointCount > 0) {
                const optimalThreshold = Math.max(0.01, Math.min(0.03, 5000 / Math.sqrt(pointCount)));
                context.raycaster.params.Points = {threshold: optimalThreshold};
            }
        }

        // Perform raycasting
        const intersects = context.raycaster.intersectObject(context.pointCloud, false);

        PerformanceLogger.end('raycasting');

        if (intersects.length > 0) {
            return {
                point: intersects[0].point,
                index: intersects[0].index,
                distance: intersects[0].distance
            };
        }

        return null;
    };

    /**
     * Try raycasting with increasing thresholds
     * @returns The raycasting result or null if no intersection
     */
    const tryProgressiveRaycast = (): RaycastResult | null => {
        // Try with initial threshold
        let result = performRaycast();

        // If no result, try with medium threshold
        if (!result) {
            result = performRaycast(0.05);
        }

        // If still no result, try with large threshold
        if (!result) {
            result = performRaycast(0.1);
        }

        return result;
    };

    /**
     * Find the nearest point to a position using spatial index
     * @param position The 3D position
     * @param maxDistance Maximum search distance
     * @returns The nearest point or null if none found
     */
    const findNearestPoint = (
        position: THREE.Vector3,
        maxDistance: number = 0.1
    ): ClickResult | null => {
        PerformanceLogger.start('find_nearest_point');

        // Use spatial index if available
        if (pointCloudStore.spatialIndex && pointCloudStore.pointCloudData.positions) {
            const cubeSize = currentCubeSize.value || 0.02;
            const pointIndices = pointCloudStore.spatialIndex.findPointsInCube(
                [position.x, position.y, position.z],
                cubeSize
            );

            if (pointIndices && pointIndices.length > 0) {
                const positions = pointCloudStore.pointCloudData.positions;
                let minDist = Number.MAX_VALUE;
                let nearestIndex = -1;

                for (const idx of pointIndices) {
                    const x = positions[idx * 3];
                    const y = positions[idx * 3 + 1];
                    const z = positions[idx * 3 + 2];

                    const dist = Math.pow(x - position.x, 2) +
                        Math.pow(y - position.y, 2) +
                        Math.pow(z - position.z, 2);

                    if (dist < minDist) {
                        minDist = dist;
                        nearestIndex = idx;
                    }
                }

                if (nearestIndex >= 0) {
                    PerformanceLogger.end('find_nearest_point');
                    return {
                        position: [
                            positions[nearestIndex * 3],
                            positions[nearestIndex * 3 + 1],
                            positions[nearestIndex * 3 + 2]
                        ],
                        index: nearestIndex // Ensure we're returning the index
                    };
                }
            }
        }

        PerformanceLogger.end('find_nearest_point');
        return null;
    };

    return {
        isProcessingSelection,
        lastMousePosition,
        updateMousePosition,
        performRaycast,
        tryProgressiveRaycast,
        findNearestPoint
    };
}