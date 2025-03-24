import {ComputedRef, Ref, ref} from 'vue';
import * as THREE from 'three';
import {ClickPoint} from '@/types/Selection';
import {AnnotationMarker, ClickAction, MarkerOptions} from '@/types/Annotation';
import {threeJsService} from '@/services/ThreeJsService';
import {getSelectionColor} from '@/utils/color-utils';

interface UseAnnotationMarkersOptions {
    // Reference to clickPoints for recreating markers
    clickedPoints?: Ref<ClickPoint[]>;
    // Current click mode
    clickMode?: Ref<'object' | 'background'>;
    // Current object index
    currentObjectIdx?: ComputedRef<number | null>;
    // Size of marker spheres
    markerSize?: Ref<number>;
}

/**
 * Composable for managing annotation markers (spheres)
 */
export function useAnnotationMarkers(options?: UseAnnotationMarkersOptions) {
    // Track created markers for management
    const markers = ref<AnnotationMarker[]>([]);

    // Track click history
    const clickHistory = ref<ClickAction[]>([]);

    /**
     * Create a marker with the given options
     * @param markerOptions Marker creation options
     * @returns The created marker or null if creation failed
     */
    const createMarker = (markerOptions: MarkerOptions): AnnotationMarker | null => {
        // Convert position to Vector3 if it's an array
        const position = markerOptions.position instanceof THREE.Vector3
            ? markerOptions.position
            : new THREE.Vector3(
                markerOptions.position[0],
                markerOptions.position[1],
                markerOptions.position[2]
            );

        // Determine color based on object index or use provided color
        const color = markerOptions.color || (markerOptions.objectIdx === 0
            ? new THREE.Color(0.1, 0.1, 0.1) // Dark gray for background
            : getSelectionColor('object', markerOptions.objectIdx));

        // Use provided radius or calculate from composable options
        const radius = markerOptions.radius ||
            (options?.markerSize?.value ? Math.max(0.03, options.markerSize.value / 2) : 0.03);

        // Create unique ID for the marker
        const id = `marker-${Date.now()}-${Math.floor(Math.random() * 10000)}`;

        // Create the marker in the scene
        const mesh = threeJsService.createMarkerSphere(position, color, radius);

        if (!mesh) {
            console.error('Failed to create marker mesh');
            return null;
        }

        // Store the marker's object id so we can use it for events
        mesh.userData = {markerId: id};

        // Create and store the marker
        const marker: AnnotationMarker = {
            id,
            position,
            mesh,
            objectIdx: markerOptions.objectIdx,
            radius,
            color,
            visible: markerOptions.visible !== false,
            metadata: markerOptions.metadata || {},
            // Add clickPoint reference if available
            clickPointIndex: markerOptions.metadata?.clickPointIndex,
            timeIdx: markerOptions.metadata?.timeIdx
        };


        markers.value.push(marker);
        return marker;
    };

    /**
     * Create a marker for a specific click point
     * @param position Position array [x,y,z]
     * @param objectIdx Object index (0 for background)
     * @param timeIdx Time index for the click
     * @returns The marker ID if successfully created
     */
    const createMarkerForClick = (
        position: number[],
        objectIdx: number,
        timeIdx: number
    ): string | undefined => {
        // Create marker options
        const markerOptions: MarkerOptions = {
            position,
            objectIdx,
            metadata: {
                clickPointIndex: timeIdx,
                timeIdx
            }
        };

        // Create the marker
        const marker = createMarker(markerOptions);

        return marker?.id;
    };

    /**
     * Remove a specific marker by ID
     * @param markerId ID of the marker to remove
     * @returns Whether the marker was found and removed
     */
    const removeMarker = (markerId: string): boolean => {
        const index = markers.value.findIndex(m => m.id === markerId);
        if (index === -1) return false;

        // Get the marker
        const marker = markers.value[index];

        // Remove from scene
        if (marker.mesh) {
            threeJsService.getContext().scene?.remove(marker.mesh);

            // Dispose resources
            if (marker.mesh.geometry) {
                marker.mesh.geometry.dispose();
            }

            if (marker.mesh.material instanceof THREE.Material) {
                marker.mesh.material.dispose();
            } else if (Array.isArray(marker.mesh.material)) {
                marker.mesh.material.forEach(m => m.dispose());
            }
        }

        // Remove from array
        markers.value.splice(index, 1);
        return true;
    };

    /**
     * Clear all markers
     */
    const clearMarkers = (): void => {
        threeJsService.clearMarkerSpheres();
        markers.value = [];
    };

    /**
     * Recreate markers from click points
     * @param points Optional array of click points to use instead of ref
     */
    const recreateMarkers = (points?: ClickPoint[]): void => {
        // Clear existing markers
        clearMarkers();

        // Use provided points or from options
        const clickPoints = points || options?.clickedPoints?.value || [];

        // Recreate from points
        clickPoints.forEach((point, index) => {
            const markerRadius = options?.markerSize?.value
                ? Math.max(0.03, options.markerSize.value / 2)
                : 0.03;

            createMarker({
                position: point.position,
                objectIdx: point.objectIdx,
                radius: markerRadius,
                metadata: {
                    clickPointIndex: index,
                    timeIdx: point.timeIdx
                }
            });
        });

        console.log(`Recreated ${markers.value.length} markers`);
    };

    /**
     * Create a marker for the current selection
     * @param position Position array [x,y,z]
     * @returns The created marker or null if creation failed
     */
    const createCurrentSelectionMarker = (position: number[]): AnnotationMarker | null => {
        if (!options?.clickMode || options.clickMode.value === undefined) {
            return null;
        }

        const objectIdx = options.clickMode.value === 'background'
            ? 0
            : (options.currentObjectIdx?.value || 0);

        // Record this click action
        const clickAction: ClickAction = {
            position: [...position],
            objectIdx,
            timestamp: Date.now(),
            sequenceIdx: clickHistory.value.length,
            selectionSize: options?.markerSize?.value || 0.02,
            hasMarker: true,
        };

        // Create the marker
        const marker = createMarker({
            position,
            objectIdx,
            metadata: {
                clickPointIndex: clickHistory.value.length,
                timeIdx: clickHistory.value.length
            }
            // Use default radius and color
        });

        // Update click action with marker ID if created
        if (marker) {
            clickAction.markerId = marker.id;
        } else {
            clickAction.hasMarker = false;
        }

        // Add to history
        clickHistory.value.push(clickAction);

        return marker;
    };

    /**
     * Update marker visibility
     * @param markerId ID of the marker to update
     * @param visible Whether the marker should be visible
     */
    const setMarkerVisibility = (markerId: string, visible: boolean): void => {
        const marker = markers.value.find(m => m.id === markerId);
        if (!marker || !marker.mesh) return;

        marker.visible = visible;
        marker.mesh.visible = visible;
    };

    /**
     * Update marker color
     * @param markerId ID of the marker to update
     * @param color New color for the marker
     */
    const setMarkerColor = (markerId: string, color: THREE.Color): void => {
        const marker = markers.value.find(m => m.id === markerId);
        if (!marker || !marker.mesh) return;

        marker.color = color;

        if (marker.mesh.material instanceof THREE.Material) {
            (marker.mesh.material as THREE.MeshPhongMaterial).color.copy(color);
            (marker.mesh.material as THREE.MeshPhongMaterial).emissive.copy(color).multiplyScalar(0.2);
            marker.mesh.material.needsUpdate = true;
        }
    };

    /**
     * Get the click history for tracking annotation actions
     */
    const getClickHistory = (): ClickAction[] => {
        return [...clickHistory.value];
    };

    /**
     * Clear click history
     */
    const clearClickHistory = (): void => {
        clickHistory.value = [];
    };

    /**
     * Find a marker by position (approximate)
     * @param position Position to search near
     * @param threshold Distance threshold
     */
    const findMarkerByPosition = (
        position: number[] | THREE.Vector3,
        threshold: number = 0.01
    ): AnnotationMarker | null => {
        // Convert position to Vector3 if it's an array
        const pos = position instanceof THREE.Vector3
            ? position
            : new THREE.Vector3(position[0], position[1], position[2]);

        // Find closest marker
        let closestMarker: AnnotationMarker | null = null;
        let closestDistance = Infinity;

        for (const marker of markers.value) {
            const distance = marker.position.distanceTo(pos);
            if (distance < threshold && distance < closestDistance) {
                closestDistance = distance;
                closestMarker = marker;
            }
        }

        return closestMarker;
    };

    return {
        markers,
        clickHistory,
        createMarker,
        removeMarker,
        clearMarkers,
        recreateMarkers,
        createCurrentSelectionMarker,
        createMarkerForClick,
        setMarkerVisibility,
        setMarkerColor,
        getClickHistory,
        clearClickHistory,
        findMarkerByPosition
    };
}