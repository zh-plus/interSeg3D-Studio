import {ComputedRef, Ref, ref} from 'vue';
import * as THREE from 'three';
import {PointCloudData} from '@/types/PointCloud';
import {ClickPoint, SelectionOptions} from '@/types/Selection';
import {PerformanceLogger} from '@/utils/performance-logger';
import {GridSpatialIndex} from '@/utils/GridSpatialIndex';
import {getSelectionColor} from '@/utils/color-utils';

// Add interface for the history action
interface SelectionHistoryAction {
    type: 'add' | 'remove'; // Type of action (add point, remove point)
    clickPoint: ClickPoint;  // The click point that was added/removed
    markerId?: string;      // Associated marker ID for visualization
    affectedPointIndices?: number[]; // Points affected by this action (for color restoration)
    previousColors?: Float32Array; // Previous colors of affected points (for undo)
}

interface UseSelectionToolOptions {
    // Reference to spatial index for optimized point finding
    spatialIndex?: Ref<GridSpatialIndex | null>;
    // Point cloud data
    pointCloudData?: Ref<PointCloudData>;
    // Size of selection cube
    cubeSize?: Ref<number>;
    // Click mode (object or background)
    clickMode?: Ref<'object' | 'background'>;
    // Current object index
    currentObjectIdx?: ComputedRef<number | null>;
}

/**
 * Composable for handling point selection and coloring
 */
export function useSelectionTool(options?: UseSelectionToolOptions) {
    const isUndoInProgress = ref(false);
    const isRedoInProgress = ref(false);
    const undoRedoDebounceTime = 300; // milliseconds

    // Track clicked points for adding spheres
    const clickedPoints = ref<ClickPoint[]>([]);

    // Add history stacks for undo/redo
    const undoStack = ref<SelectionHistoryAction[]>([]);
    const redoStack = ref<SelectionHistoryAction[]>([]);

    // Track whether an undo/redo operation is in progress
    const isUndoRedoOperation = ref(false);

    /**
     * Add a click point
     * @param position Position of the click
     * @param objectIdx Index of the object to assign (0 for background)
     * @param index Optional index of the point in the point cloud
     * @param markerId Optional ID of the associated marker
     * @param fromUndo Whether this is called from an undo/redo operation
     * @returns The added click point
     */
    const addClickPoint = (
        position: number[],
        objectIdx: number,
        index?: number,
        markerId?: string,
        fromUndo: boolean = false
    ): ClickPoint => {
        const clickPoint: ClickPoint = {
            position,
            objectIdx,
            timeIdx: clickedPoints.value.length,
            index // Store the actual point index if provided
        };

        clickedPoints.value.push(clickPoint);

        // Only add to undo stack if not part of an undo/redo operation
        if (!fromUndo && !isUndoRedoOperation.value) {
            // Clear redo stack when new action is performed
            redoStack.value = [];

            // Add to undo stack
            undoStack.value.push({
                type: 'add',
                clickPoint,
                markerId
            });
        }

        return clickPoint;
    };

    /**
     * Apply selection to points in a cube around the position
     * @param position Center position
     * @param selectionOptions Selection options
     * @param fromUndo Whether this is called from an undo operation
     * @returns Number of points selected and affected indices
     */
    const applySelection = (
        position: number[],
        selectionOptions?: Partial<SelectionOptions>,
        fromUndo: boolean = false
    ): { count: number, indices: number[] } => {
        PerformanceLogger.start('apply_selection');

        if (!options?.pointCloudData?.value.currentColors ||
            !options?.pointCloudData?.value.geometry) {
            PerformanceLogger.end('apply_selection');
            return {count: 0, indices: []};
        }

        // Selection options
        const cubeSize = selectionOptions?.cubeSize || options?.cubeSize?.value || 0.02;
        const mode = selectionOptions?.mode || options?.clickMode?.value || 'object';
        const objectIdx = selectionOptions?.objectIdx !== undefined
            ? selectionOptions.objectIdx
            : (options?.currentObjectIdx?.value || null);

        // Skip coloring points if in background mode (only create a sphere)
        if (mode === 'background') {
            PerformanceLogger.end('apply_selection');
            return {count: 0, indices: []};
        }

        // Get selection color
        const color = getSelectionColor(mode, objectIdx);

        // Use spatial index if available for better performance
        if (options?.spatialIndex?.value) {
            return applySpatialIndexSelection(position, color, cubeSize, fromUndo);
        } else {
            return applyLegacySelection(position, color, cubeSize, fromUndo);
        }
    };

    /**
     * Apply selection using spatial index for efficiency
     */
    const applySpatialIndexSelection = (
        position: number[],
        color: THREE.Color,
        cubeSize: number,
        fromUndo: boolean = false
    ): { count: number, indices: number[] } => {
        PerformanceLogger.start('spatial_selection');

        if (!options?.spatialIndex?.value ||
            !options?.pointCloudData?.value.currentColors ||
            !options?.pointCloudData?.value.geometry) {
            PerformanceLogger.end('spatial_selection');
            return {count: 0, indices: []};
        }

        const pointIndices = options.spatialIndex.value.findPointsInCube(position, cubeSize);
        const currentColors = options.pointCloudData.value.currentColors;

        // Store previous colors for undo if not already in an undo operation
        let previousColors: Float32Array | undefined;

        if (!fromUndo && !isUndoRedoOperation.value && pointIndices.length > 0) {
            previousColors = new Float32Array(pointIndices.length * 3);
            for (let i = 0; i < pointIndices.length; i++) {
                const idx = pointIndices[i];
                const colorIdx = idx * 3;
                previousColors[i * 3] = currentColors[colorIdx];
                previousColors[i * 3 + 1] = currentColors[colorIdx + 1];
                previousColors[i * 3 + 2] = currentColors[colorIdx + 2];
            }

            // Update the last action in the undo stack with the affected points and colors
            if (undoStack.value.length > 0) {
                const lastAction = undoStack.value[undoStack.value.length - 1];
                lastAction.affectedPointIndices = [...pointIndices];
                lastAction.previousColors = previousColors;
            }
        }

        if (pointIndices.length > 0) {
            for (let i = 0; i < pointIndices.length; i++) {
                const idx = pointIndices[i];
                const colorIdx = idx * 3;
                currentColors[colorIdx] = color.r;
                currentColors[colorIdx + 1] = color.g;
                currentColors[colorIdx + 2] = color.b;
            }

            // Update buffer
            if (options.pointCloudData.value.geometry.attributes.color) {
                (options.pointCloudData.value.geometry.attributes.color as THREE.BufferAttribute).needsUpdate = true;
            }
        }

        PerformanceLogger.end('spatial_selection');
        return {count: pointIndices.length, indices: pointIndices};
    };

    /**
     * Apply selection using traditional iteration (slower but works without spatial index)
     */
    const applyLegacySelection = (
        position: number[],
        color: THREE.Color,
        cubeSize: number,
        fromUndo: boolean = false
    ): { count: number, indices: number[] } => {
        PerformanceLogger.start('legacy_selection');

        if (!options?.pointCloudData?.value.positions ||
            !options?.pointCloudData?.value.currentColors ||
            !options?.pointCloudData?.value.geometry) {
            PerformanceLogger.end('legacy_selection');
            return {count: 0, indices: []};
        }

        const positions = options.pointCloudData.value.positions;
        const currentColors = options.pointCloudData.value.currentColors;

        // Bounding box optimization
        const minX = position[0] - cubeSize;
        const maxX = position[0] + cubeSize;
        const minY = position[1] - cubeSize;
        const maxY = position[1] + cubeSize;
        const minZ = position[2] - cubeSize;
        const maxZ = position[2] + cubeSize;

        // Track selected points
        let selectedCount = 0;
        const affectedIndices: number[] = [];
        let previousColors: Float32Array | undefined;

        // First pass: identify affected points
        for (let i = 0; i < positions.length; i += 3) {
            const x = positions[i];
            const y = positions[i + 1];
            const z = positions[i + 2];

            if (x >= minX && x <= maxX && y >= minY && y <= maxY && z >= minZ && z <= maxZ) {
                const pointIndex = i / 3;
                affectedIndices.push(pointIndex);
                selectedCount++;
            }
        }

        // Store previous colors for undo if not already in an undo operation
        if (!fromUndo && !isUndoRedoOperation.value && affectedIndices.length > 0) {
            previousColors = new Float32Array(affectedIndices.length * 3);
            for (let i = 0; i < affectedIndices.length; i++) {
                const pointIndex = affectedIndices[i];
                const colorIdx = pointIndex * 3;
                previousColors[i * 3] = currentColors[colorIdx];
                previousColors[i * 3 + 1] = currentColors[colorIdx + 1];
                previousColors[i * 3 + 2] = currentColors[colorIdx + 2];
            }

            // Update the last action in the undo stack
            if (undoStack.value.length > 0) {
                const lastAction = undoStack.value[undoStack.value.length - 1];
                lastAction.affectedPointIndices = affectedIndices;
                lastAction.previousColors = previousColors;
            }
        }

        // Second pass: update colors
        for (const pointIndex of affectedIndices) {
            const colorIndex = pointIndex * 3;
            currentColors[colorIndex] = color.r;
            currentColors[colorIndex + 1] = color.g;
            currentColors[colorIndex + 2] = color.b;
        }

        // Update buffer
        if (options.pointCloudData.value.geometry.attributes.color) {
            (options.pointCloudData.value.geometry.attributes.color as THREE.BufferAttribute).needsUpdate = true;
        }

        PerformanceLogger.end('legacy_selection');
        return {count: selectedCount, indices: affectedIndices};
    };

    /**
     * Restore specific points to their original colors
     * @param indices Point indices to restore
     * @param colors Colors to restore (must match indices length * 3)
     */
    const restorePointColors = (indices: number[], colors: Float32Array): void => {
        if (!options?.pointCloudData?.value.currentColors ||
            !options?.pointCloudData?.value.geometry) {
            return;
        }

        const currentColors = options.pointCloudData.value.currentColors;

        for (let i = 0; i < indices.length; i++) {
            const pointIndex = indices[i];
            const colorIdx = pointIndex * 3;
            const storedColorIdx = i * 3;

            currentColors[colorIdx] = colors[storedColorIdx];
            currentColors[colorIdx + 1] = colors[storedColorIdx + 1];
            currentColors[colorIdx + 2] = colors[storedColorIdx + 2];
        }

        // Update buffer
        if (options.pointCloudData.value.geometry.attributes.color) {
            (options.pointCloudData.value.geometry.attributes.color as THREE.BufferAttribute).needsUpdate = true;
        }
    };

    /**
     * Perform undo operation
     * @param removeMarkerCallback Optional callback to remove the marker
     * @returns The undone action or null if no action to undo
     */
    const undo = (removeMarkerCallback?: (markerId: string) => void): SelectionHistoryAction | null => {
        if (undoStack.value.length === 0 || isUndoInProgress.value || isRedoInProgress.value) return null;

        isUndoInProgress.value = true;
        isUndoRedoOperation.value = true;

        try {
            // Get the last action
            const lastAction = undoStack.value.pop()!;

            // Add to redo stack
            redoStack.value.push(lastAction);

            // Restore colors if needed
            if (lastAction.affectedPointIndices && lastAction.previousColors) {
                restorePointColors(lastAction.affectedPointIndices, lastAction.previousColors);
            }

            // Remove the click point
            const index = clickedPoints.value.findIndex(p =>
                p.timeIdx === lastAction.clickPoint.timeIdx &&
                p.objectIdx === lastAction.clickPoint.objectIdx
            );

            if (index !== -1) {
                clickedPoints.value.splice(index, 1);
            }

            // Remove marker if callback provided
            if (lastAction.markerId && removeMarkerCallback) {
                removeMarkerCallback(lastAction.markerId);
            }

            return lastAction;
        } finally {
            isUndoRedoOperation.value = false;

            // Set a timeout to reset the flag
            setTimeout(() => {
                isUndoInProgress.value = false;
            }, undoRedoDebounceTime);
        }
    };

    /**
     * Perform redo operation
     * @param createMarkerCallback Optional callback to recreate the marker
     * @returns The redone action or null if no action to redo
     */
    const redo = (
        createMarkerCallback?: (
            position: number[],
            objectIdx: number,
            timeIdx: number
        ) => string | undefined
    ): SelectionHistoryAction | null => {
        if (redoStack.value.length === 0 || isUndoInProgress.value || isRedoInProgress.value) return null;

        isRedoInProgress.value = true;
        isUndoRedoOperation.value = true;

        try {
            // Get the last undone action
            const action = redoStack.value.pop()!;

            // Add back to undo stack
            undoStack.value.push(action);

            // Add the click point back
            const clickPoint = addClickPoint(
                action.clickPoint.position,
                action.clickPoint.objectIdx,
                action.clickPoint.index,
                action.markerId,
                true // fromUndo = true
            );

            // Apply selection coloring if object mode
            if (action.clickPoint.objectIdx !== 0) {
                applySelection(
                    action.clickPoint.position,
                    {
                        objectIdx: action.clickPoint.objectIdx,
                        mode: action.clickPoint.objectIdx === 0 ? 'background' : 'object'
                    },
                    true // fromUndo = true
                );
            }

            // Recreate marker if callback provided
            let newMarkerId: string | undefined;
            if (createMarkerCallback) {
                newMarkerId = createMarkerCallback(
                    action.clickPoint.position,
                    action.clickPoint.objectIdx,
                    action.clickPoint.timeIdx || 0
                );

                // Update the marker ID in the action
                action.markerId = newMarkerId;
            }

            return action;
        } finally {
            isUndoRedoOperation.value = false;

            // Set a timeout to reset the flag
            setTimeout(() => {
                isRedoInProgress.value = false;
            }, undoRedoDebounceTime);
        }
    };

    /**
     * Clear all click points
     */
    const clearClickPoints = (): void => {
        clickedPoints.value = [];
        undoStack.value = [];
        redoStack.value = [];
    };

    /**
     * Get total click count
     */
    const getClickCount = (): number => {
        return clickedPoints.value.length;
    };

    /**
     * Check if undo is available
     */
    const canUndo = (): boolean => {
        return undoStack.value.length > 0;
    };

    /**
     * Check if redo is available
     */
    const canRedo = (): boolean => {
        return redoStack.value.length > 0;
    };

    /**
     * Format click data for API
     */
    const getClickDataForApi = (): {
        clickIdx: Record<string, number[]>;
        clickTimeIdx: Record<string, number[]>;
        clickPositions: Record<string, number[][]>;
    } => {
        const clickIdx: Record<string, number[]> = {'0': []};
        const clickTimeIdx: Record<string, number[]> = {'0': []};
        const clickPositions: Record<string, number[][]> = {'0': []};

        for (const click of clickedPoints.value) {
            const objKey = String(click.objectIdx);

            // Initialize arrays if needed
            if (!clickIdx[objKey]) {
                clickIdx[objKey] = [];
                clickTimeIdx[objKey] = [];
                clickPositions[objKey] = [];
            }

            // Use the index if available, otherwise use -1
            // The backend will find the nearest point if index is -1
            clickIdx[objKey].push(click.index ?? -1);
            clickTimeIdx[objKey].push(click.timeIdx || 0);
            clickPositions[objKey].push(click.position);
        }

        return {
            clickIdx,
            clickTimeIdx,
            clickPositions
        };
    };

    return {
        clickedPoints,
        addClickPoint,
        applySelection,
        clearClickPoints,
        getClickCount,
        getClickDataForApi,
        // Undo/redo functionality
        undo,
        redo,
        canUndo,
        canRedo,
        undoStack,
        redoStack
    };
}