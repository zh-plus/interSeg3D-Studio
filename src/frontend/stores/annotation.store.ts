import {defineStore} from 'pinia';
import {computed, ref} from 'vue';
import * as THREE from 'three';
import {ClickPoint} from '@/types/selection.types';
import {AnnotationMarker, ClickAction, MarkerOptions} from '@/types/annotation.types';
import {threeJsService} from '@/services/threeJs.service';
import {getSelectionColor} from '@/utils/color.util';
import {usePointCloudStore} from './pointCloud.store';
import {useUiStore} from './ui.store';

// Interface for history actions
interface SelectionHistoryAction {
  type: 'add' | 'remove'; // Type of action (add point, remove point)
  clickPoint: ClickPoint;  // The click point that was added/removed
  markerId?: string;      // Associated marker ID for visualization
  affectedPointIndices?: number[]; // Points affected by this action (for color restoration)
  previousColors?: Float32Array; // Previous colors of affected points (for undo)
}

export const useAnnotationStore = defineStore('annotation', () => {
  // References to other stores
  const pointCloudStore = usePointCloudStore();
  const uiStore = useUiStore();

  // State
  const clickedPoints = ref<ClickPoint[]>([]);
  const markers = ref<AnnotationMarker[]>([]);
  const clickHistory = ref<ClickAction[]>([]);
  const selectedCoordinate = ref<number[] | null>(null);
  const isProcessingSelection = ref(false);

  // Undo/Redo state
  const undoStack = ref<SelectionHistoryAction[]>([]);
  const redoStack = ref<SelectionHistoryAction[]>([]);
  const isUndoInProgress = ref(false);
  const isRedoInProgress = ref(false);
  const isUndoRedoOperation = ref(false);
  const undoRedoDebounceTime = 300; // milliseconds

  // Getters
  const clickCount = computed(() => clickedPoints.value.length);
  const canUndo = computed(() => undoStack.value.length > 0);
  const canRedo = computed(() => redoStack.value.length > 0);

  // Click data formatted for API
  const clickDataForApi = computed(() => {
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
      clickIdx[objKey].push(click.index ?? -1);
      clickTimeIdx[objKey].push(click.timeIdx || 0);
      clickPositions[objKey].push(click.position);
    }

    return {
      clickIdx,
      clickTimeIdx,
      clickPositions
    };
  });

  // Actions
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

  const applySelection = (
      position: number[],
      objectIdx: number,
      fromUndo: boolean = false
  ): { count: number, indices: number[] } => {
    if (!pointCloudStore.pointCloudData.currentColors ||
        !pointCloudStore.pointCloudData.geometry ||
        !pointCloudStore.spatialIndex) {
      return {count: 0, indices: []};
    }

    // Skip coloring points if in background mode
    if (objectIdx === 0) {
      return {count: 0, indices: []};
    }

    // Get selection color
    const color = getSelectionColor(objectIdx === 0 ? 'background' : 'object', objectIdx);

    // Use spatial index for better performance
    const pointIndices = pointCloudStore.spatialIndex.findPointsInCube(
        position,
        uiStore.cubeSize
    );

    const currentColors = pointCloudStore.pointCloudData.currentColors;

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
      if (pointCloudStore.pointCloudData.geometry.attributes.color) {
        (pointCloudStore.pointCloudData.geometry.attributes.color as THREE.BufferAttribute).needsUpdate = true;
      }
    }

    return {count: pointIndices.length, indices: pointIndices};
  };

  const restorePointColors = (indices: number[], colors: Float32Array): void => {
    if (!pointCloudStore.pointCloudData.currentColors ||
        !pointCloudStore.pointCloudData.geometry) {
      return;
    }

    const currentColors = pointCloudStore.pointCloudData.currentColors;

    for (let i = 0; i < indices.length; i++) {
      const pointIndex = indices[i];
      const colorIdx = pointIndex * 3;
      const storedColorIdx = i * 3;

      currentColors[colorIdx] = colors[storedColorIdx];
      currentColors[colorIdx + 1] = colors[storedColorIdx + 1];
      currentColors[colorIdx + 2] = colors[storedColorIdx + 2];
    }

    // Update buffer
    if (pointCloudStore.pointCloudData.geometry.attributes.color) {
      (pointCloudStore.pointCloudData.geometry.attributes.color as THREE.BufferAttribute).needsUpdate = true;
    }
  };

  // Marker management
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

    // Use provided radius or calculate from current cube size
    const radius = markerOptions.radius || Math.max(0.03, uiStore.cubeSize / 2);

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

  const createCurrentSelectionMarker = (position: number[]): AnnotationMarker | null => {
    const objectIdx = uiStore.clickMode === 'background'
        ? 0
        : uiStore.currentObjectIdx || 0;

    // Record this click action
    const clickAction: ClickAction = {
      position: [...position],
      objectIdx,
      timestamp: Date.now(),
      sequenceIdx: clickHistory.value.length,
      selectionSize: uiStore.cubeSize,
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

  const clearMarkers = (): void => {
    threeJsService.clearMarkerSpheres();
    markers.value = [];
  };

  const recreateMarkers = (): void => {
    // Clear existing markers
    clearMarkers();

    // Recreate from points
    clickedPoints.value.forEach((point, index) => {
      const markerRadius = Math.max(0.03, uiStore.cubeSize / 2);

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

  // Undo/Redo functionality
  const undo = (): SelectionHistoryAction | null => {
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

      // Remove marker if exists
      if (lastAction.markerId) {
        removeMarker(lastAction.markerId);
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

  const redo = (): SelectionHistoryAction | null => {
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
            action.clickPoint.objectIdx,
            true // fromUndo = true
        );
      }

      // Recreate marker
      let newMarkerId: string | undefined;
      newMarkerId = createMarkerForClick(
          action.clickPoint.position,
          action.clickPoint.objectIdx,
          action.clickPoint.timeIdx || 0
      );

      // Update the marker ID in the action
      action.markerId = newMarkerId;

      return action;
    } finally {
      isUndoRedoOperation.value = false;

      // Set a timeout to reset the flag
      setTimeout(() => {
        isRedoInProgress.value = false;
      }, undoRedoDebounceTime);
    }
  };

  const clearClickPoints = (): void => {
    clickedPoints.value = [];
    undoStack.value = [];
    redoStack.value = [];
  };

  const reset = (): void => {
    clearClickPoints();
    clearMarkers();
    clickHistory.value = [];
    selectedCoordinate.value = null;
    isProcessingSelection.value = false;
  };

  return {
    // State
    clickedPoints,
    markers,
    clickHistory,
    selectedCoordinate,
    isProcessingSelection,
    undoStack,
    redoStack,

    // Getters
    clickCount,
    canUndo,
    canRedo,
    clickDataForApi,

    // Actions
    addClickPoint,
    applySelection,
    createMarker,
    createCurrentSelectionMarker,
    createMarkerForClick,
    removeMarker,
    clearMarkers,
    recreateMarkers,
    undo,
    redo,
    clearClickPoints,
    reset
  };
});