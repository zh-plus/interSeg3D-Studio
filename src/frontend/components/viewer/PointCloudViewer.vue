<template>
  <div ref="container" class="point-cloud-viewer">
    <!-- Loading overlay -->
    <LoadingOverlay
        :message="loadingMessage"
        :progress="loadingProgress ?? undefined"
        :show="isLoading"
    />

    <!-- Mode indicator -->
    <ModeIndicator
        :click-mode="internalClickMode"
        :mode="internalInteractionMode"
    />

    <!-- Selection info -->
    <SelectionInfo
        :can-redo="canRedo()"
        :can-undo="canUndo()"
        :click-count="getClickCount()"
        :click-points="clickedPoints"
        :coordinate="selectedCoordinate"
        :is-processing-selection="isProcessingSelection"
        :point-count="pointCloudData.pointCount"
        :show-debug="showDebug"
    />

    <!-- Undo/Redo notification -->
    <div v-if="showUndoRedoNotification" class="undo-redo-notification">
      {{ undoRedoNotificationText }}
    </div>
  </div>
</template>

<script lang="ts" setup>
import {onBeforeUnmount, onMounted, PropType, ref, Ref, watch} from 'vue';
import * as THREE from 'three';
import {SegmentedPointCloud} from '@/types/PointCloud';
import {ClickMode, InteractionMode} from '@/types/Selection';
import {PerformanceLogger} from '@/utils/performance-logger';
import {pointCloudService} from '@/services/PointCloudService';
import {threeJsService} from '@/services/ThreeJsService';
import {GridSpatialIndex} from '@/utils/GridSpatialIndex';

// Components
import LoadingOverlay from './LoadingOverlay.vue';
import ModeIndicator from './ModeIndicator.vue';
import SelectionInfo from './SelectionInfo.vue';

// Composables
import {useThreeJsRenderer} from '@/composables/useThreeJsRenderer';
import {usePointCloudLoader} from '@/composables/usePointCloudLoader';
import {useInteractionMode} from '@/composables/useInteractionMode';
import {useRaycasting} from '@/composables/useRaycasting';
import {useSelectionTool} from '@/composables/useSelectionTool';
import {useAnnotationMarkers} from '@/composables/useAnnotationMarkers';

// Props definition
const props = defineProps({
  plyFile: {
    type: Object as PropType<File | null>,
    default: null
  },
  segmentedPointCloud: {
    type: Object as PropType<SegmentedPointCloud | null>,
    default: null
  },
  clickMode: {
    type: String as PropType<ClickMode>,
    default: 'object'
  },
  currentObjectIdx: {
    type: Number,
    default: null
  },
  cubeSize: {
    type: Number,
    default: 0.02
  },
  interactionMode: {
    type: String as PropType<InteractionMode>,
    default: 'navigate'
  },
  objects: {
    type: Array as PropType<{ id: number; name: string }[]>,
    default: () => []
  }
});

// Define emits
const emit = defineEmits([
  'point-clicked',
  'point-cloud-loaded',
  'error',
  'create-object',
  'select-object',
  'undo',
  'redo'
]);

// DOM Container reference
const container = ref<HTMLElement | null>(null);

// Debug settings
const showDebug = ref(import.meta.env.DEV || false);

// Loading state
const isLoading = ref(false);
const loadingMessage = ref('');
const loadingProgress = ref<number | null>(null);

// Selection state
const selectedCoordinate = ref<number[] | null>(null);
const isProcessingSelection = ref(false);

// Mouse interaction state
const isSelecting = ref(false);
const isDragging = ref(false);
const startMousePosition = ref<{ x: number, y: number } | null>(null);

// Undo/Redo notification
const showUndoRedoNotification = ref(false);
const undoRedoNotificationText = ref('');
const undoRedoNotificationTimer = ref<number | null>(null);

// Internal props tracking for reactivity
const internalInteractionMode = ref<InteractionMode>(props.interactionMode);
const internalClickMode = ref<ClickMode>(props.clickMode);
const internalObjectIdx = ref<number | null>(props.currentObjectIdx);
const internalCubeSize = ref(props.cubeSize);

// Initialize Three.js
const {threeContext, refreshViewport} = useThreeJsRenderer(container);

// Point cloud loading and management
const {
  pointCloudData,
  spatialIndex: rawSpatialIndex,
  loadPointCloud,
  resetColors,
  centerCamera
} = usePointCloudLoader();

// Fix type compatibility issue with a proper type assertion
const spatialIndex = rawSpatialIndex as Ref<GridSpatialIndex | null>;

// Set up interaction mode
const {
  interactionMode: modeState,
  clickMode: clickModeState,
  updateControlsState,
  selectObject,
  currentObjectIdx: currentObjIdx
} = useInteractionMode({
  initialMode: props.interactionMode,
  container
});

// Raycasting for point selection
const {
  isProcessingSelection: raycastProcessing,
  updateMousePosition,
  tryProgressiveRaycast,
  findNearestPoint,
  performRaycast
} = useRaycasting({
  spatialIndex,
  pointCloudData,
  cubeSize: internalCubeSize,
  container
});

// Selection tools
const {
  clickedPoints,
  addClickPoint,
  applySelection,
  getClickCount,
  getClickDataForApi,
  undo: undoSelection,
  redo: redoSelection,
  canUndo,
  canRedo
} = useSelectionTool({
  spatialIndex,
  pointCloudData,
  cubeSize: internalCubeSize,
  clickMode: internalClickMode,
  currentObjectIdx: currentObjIdx
});

// Annotation markers
const {
  createCurrentSelectionMarker,
  clearMarkers,
  recreateMarkers,
  removeMarker,
  createMarkerForClick
} = useAnnotationMarkers({
  clickedPoints,
  clickMode: internalClickMode,
  currentObjectIdx: currentObjIdx,
  markerSize: internalCubeSize
});

// Sync internal state with props
watch(() => props.interactionMode, (newMode) => {
  internalInteractionMode.value = newMode;
  modeState.value = newMode;
});

watch(() => props.clickMode, (newMode) => {
  internalClickMode.value = newMode;
  clickModeState.value = newMode;
});

watch(() => props.currentObjectIdx, (newIdx) => {
  internalObjectIdx.value = newIdx;
  if (newIdx !== null) {
    selectObject(newIdx - 1); // Convert to 0-based
  }
});

watch(() => props.cubeSize, (newSize) => {
  internalCubeSize.value = newSize;
});

/**
 * Display a brief notification for undo/redo actions
 */
const showNotification = (text: string): void => {
  // Clear any existing timer
  if (undoRedoNotificationTimer.value) {
    window.clearTimeout(undoRedoNotificationTimer.value);
    undoRedoNotificationTimer.value = null;
  }

  // Set notification text and show it
  undoRedoNotificationText.value = text;
  showUndoRedoNotification.value = true;

  // Hide after 2 seconds
  undoRedoNotificationTimer.value = window.setTimeout(() => {
    showUndoRedoNotification.value = false;
    undoRedoNotificationTimer.value = null;
  }, 2000);
};

/**
 * Handle file changes from props
 */
watch(() => props.plyFile, async (newFile) => {
  if (!newFile || isLoading.value) return;

  try {
    isLoading.value = true;
    loadingMessage.value = 'Loading point cloud...';

    // Load the file
    await loadPointCloud(newFile);

    // Center camera on loaded point cloud
    centerCamera();

    // Clear any previous markers
    clearMarkers();

    // Emit loaded event
    emit('point-cloud-loaded', {
      pointCount: pointCloudData.value.pointCount
    });
  } catch (error) {
    console.error('Error loading point cloud:', error);
    emit('error', error instanceof Error ? error.message : 'Failed to load point cloud');
  } finally {
    isLoading.value = false;
    loadingMessage.value = '';
  }
});

/**
 * Handle segmentation data changes
 */
watch(() => props.segmentedPointCloud, async (newData) => {
  if (!newData || !pointCloudData.value.pointCount) return;

  try {
    isLoading.value = true;
    loadingMessage.value = 'Applying segmentation...';

    // Apply segmentation with the PointCloudService
    const result = await pointCloudService.applySegmentation(
        pointCloudData.value,
        newData
    );

    if (!result) {
      throw new Error('Failed to apply segmentation data');
    }

    // Recreate markers to keep them visible
    recreateMarkers();

    // Force a render update after segmentation
    if (threeContext.value?.renderer && threeContext.value?.scene && threeContext.value?.camera) {
      console.log('Explicitly rendering after segmentation update');
      threeContext.value.renderer.render(threeContext.value.scene, threeContext.value.camera);
    }
  } catch (error) {
    console.error('Error applying segmentation:', error);
    emit('error', error instanceof Error ? error.message : 'Failed to apply segmentation');
  } finally {
    isLoading.value = false;
    loadingMessage.value = '';
  }
});

/**
 * Handle mouse down event
 */
const onMouseDown = (event: MouseEvent): void => {
  startMousePosition.value = {x: event.clientX, y: event.clientY};

  if (isLoading.value) return;

  if (event.button === 2) {
    // Right-click: temporarily enable controls for panning
    event.preventDefault();
    if (internalInteractionMode.value === 'annotate' && threeContext.value?.controls) {
      threeContext.value.controls.enabled = true;
      threeContext.value.controls.enablePan = true;
    }
    return;
  }

  if (event.button === 0 && internalInteractionMode.value === 'annotate') {
    isSelecting.value = true;
    event.preventDefault();
  }
};

/**
 * Handle mouse move event
 */
const onMouseMove = (event: MouseEvent): void => {
  if (!startMousePosition.value) return;

  const deltaX = Math.abs(event.clientX - startMousePosition.value.x);
  const deltaY = Math.abs(event.clientY - startMousePosition.value.y);

  if (deltaX > 3 || deltaY > 3) {
    isDragging.value = true;
  }
};

/**
 * Handle mouse up event
 */
const onMouseUp = (event: MouseEvent): void => {
  const wasDragging = isDragging.value;
  isDragging.value = false;
  startMousePosition.value = null;

  if (event.button === 2) {
    // Right-click: restore controls state
    if (internalInteractionMode.value === 'annotate' && threeContext.value?.controls) {
      threeContext.value.controls.enabled = false;
      threeContext.value.controls.enablePan = false;
    }
    return;
  }

  if (internalInteractionMode.value === 'annotate' && isSelecting.value && !wasDragging) {
    handleAnnotationClick(event);
  }

  isSelecting.value = false;
};

/**
 * Handle annotation click with improved viewport synchronization
 */
const handleAnnotationClick = (event: MouseEvent): void => {
  PerformanceLogger.start('total_click_processing');

  if (isLoading.value || !container.value) return;

  // Check valid click mode - if object mode requires currentObjectIdx, background mode doesn't
  if (internalClickMode.value === 'object' && internalObjectIdx.value === null) {
    console.warn('No object selected for labeling');
    return;
  }

  // Ensure the Three.js viewport is correctly sized and synchronized with the container
  // This is critical for accurate raycasting when moving between different displays
  if (threeContext.value && threeContext.value.renderer) {
    const canvasElement = threeContext.value.renderer.domElement;
    const canvasRect = canvasElement.getBoundingClientRect();
    const containerRect = container.value.getBoundingClientRect();

    // Check if there's a significant mismatch between canvas and container
    if (Math.abs(canvasRect.width - containerRect.width) > 1 ||
        Math.abs(canvasRect.height - containerRect.height) > 1) {
      console.debug(`Size mismatch detected before click processing:
        Canvas: ${canvasRect.width.toFixed(0)}x${canvasRect.height.toFixed(0)}
        Container: ${containerRect.width.toFixed(0)}x${containerRect.height.toFixed(0)}`);

      // Force viewport update to ensure synchronized dimensions
      threeJsService.updateViewport({
        width: containerRect.width,
        height: containerRect.height,
        pixelRatio: Math.min(window.devicePixelRatio, 2)
      });
    }
  }

  // Get the latest container rect after ensuring synchronization
  const rect = container.value.getBoundingClientRect();

  // Debug log container and click position
  console.debug(`Click at (${event.clientX}, ${event.clientY}) in container ${rect.width.toFixed(0)}x${rect.height.toFixed(0)}`);

  // Update mouse position with the latest container rect
  updateMousePosition(event.clientX, event.clientY, rect);

  // Perform raycasting
  isProcessingSelection.value = true;

  // Try to raycast
  const raycastResult = tryProgressiveRaycast();

  if (raycastResult && raycastResult.point) {
    // If we got a point, find the nearest actual point
    const nearestPoint = findNearestPoint(raycastResult.point);

    if (nearestPoint) {
      // Store the selected point
      selectedCoordinate.value = nearestPoint.position;

      // Create a marker at the point
      const marker = createCurrentSelectionMarker(nearestPoint.position);

      // Add the click point to our history
      const objectIdx = internalClickMode.value === 'background' ? 0 : (internalObjectIdx.value || 0);
      addClickPoint(nearestPoint.position, objectIdx, nearestPoint.index, marker?.id);  // Pass the marker ID

      // Apply selection coloring
      if (internalClickMode.value === 'object') {
        applySelection(nearestPoint.position);
      }

      // Emit the click event
      emit('point-clicked', nearestPoint.position);
    } else {
      console.warn('No nearest point found');
    }
  } else {
    console.warn('No intersection found');
  }

  isProcessingSelection.value = false;
  PerformanceLogger.end('total_click_processing');
};

/**
 * Handle keyboard events
 */
const handleKeydown = (e: KeyboardEvent): void => {
  // Prevent handling if any input elements are focused
  if (e.target instanceof HTMLInputElement ||
      e.target instanceof HTMLTextAreaElement ||
      e.target instanceof HTMLSelectElement) {
    return;
  }

  // 'A' key to toggle between annotation and navigation modes
  if (e.key === 'a' || e.key === 'A') {
    internalInteractionMode.value = internalInteractionMode.value === 'navigate' ? 'annotate' : 'navigate';
    modeState.value = internalInteractionMode.value;
    updateControlsState(internalInteractionMode.value);
    console.log(`Switched to ${internalInteractionMode.value} mode`);
  }

  // Ctrl+Z for undo
  if (e.ctrlKey && !e.shiftKey && (e.key === 'z' || e.key === 'Z')) {
    if (canUndo()) {
      e.preventDefault();
      e.stopPropagation(); // Stop event propagation
      performUndo();
    }
  }

  // Shift+Ctrl+Z for redo
  if (e.ctrlKey && e.shiftKey && (e.key === 'z' || e.key === 'Z')) {
    if (canRedo()) {
      e.preventDefault();
      e.stopPropagation(); // Stop event propagation
      performRedo();
    }
  }
};

/**
 * Perform undo operation
 */
const performUndo = (): void => {
  if (!canUndo()) return;

  const undoneAction = undoSelection(removeMarker);

  if (undoneAction) {
    // Notify user
    showNotification(`Undid click ${undoneAction.clickPoint.objectIdx === 0 ? 'background' : 'object'}`);

    // Emit undo event
    emit('undo', undoneAction);
  }
};

/**
 * Perform redo operation
 */
const performRedo = (): void => {
  if (!canRedo()) return;

  const redoneAction = redoSelection(createMarkerForClick);

  if (redoneAction) {
    // Notify user
    showNotification(`Redid click ${redoneAction.clickPoint.objectIdx === 0 ? 'background' : 'object'}`);

    // Emit redo event
    emit('redo', redoneAction);
  }
};


const refreshMarkers = () => {
  if (clickedPoints.value.length > 0) {
    console.log('Refreshing markers');
    // Use the existing recreateMarkers function from useAnnotationMarkers
    recreateMarkers();
  }
};

const forceRenderUpdate = () => {
  console.log('Force rendering update requested');

  if (!threeContext.value) return;

  try {
    // Extract objects from context to avoid proxy issues
    const {scene, camera, renderer, pointCloud} = threeContext.value;

    if (!scene || !camera || !renderer || !pointCloud) {
      console.warn('Missing Three.js objects for rendering');
      return;
    }

    // Access geometry directly from the service to avoid proxy issues
    if (pointCloudData.value.geometry) {
      // Mark color buffer as needing update
      const colorAttrib = pointCloudData.value.geometry.attributes.color;
      if (colorAttrib) {
        colorAttrib.needsUpdate = true;
      }
    }

    // Use the service to trigger a render instead of calling it directly
    threeJsService.renderScene();

    console.log('Manual render completed');
  } catch (error) {
    console.error('Error during force render:', error);
  }
};

/**
 * Handle wheel event for zooming in annotation mode
 */
const onWheel = (event: WheelEvent): void => {
  if (internalInteractionMode.value === 'annotate' && threeContext.value?.camera) {
    event.preventDefault();

    const zoomSpeed = 0.1;
    const zoomDelta = -Math.sign(event.deltaY) * zoomSpeed;

    const direction = new THREE.Vector3(0, 0, 0);
    threeContext.value.camera.getWorldDirection(direction);

    if (threeContext.value.controls) {
      const distance = threeContext.value.camera.position.distanceTo(
          threeContext.value.controls.target
      );
      const scaleFactor = distance * zoomDelta;

      threeContext.value.camera.position.addScaledVector(direction, scaleFactor);
    }
  }
};

// Set up event handlers
onMounted(() => {
  if (!container.value) return;

  // Add event listeners
  container.value.addEventListener('mousedown', onMouseDown);
  container.value.addEventListener('mousemove', onMouseMove);
  container.value.addEventListener('mouseup', onMouseUp);
  container.value.addEventListener('wheel', onWheel, {passive: false});

  // Add keyboard event listener for undo/redo
  window.addEventListener('keydown', handleKeydown);
});

// Clean up event handlers
onBeforeUnmount(() => {
  if (!container.value) return;

  // Remove event listeners
  container.value.removeEventListener('mousedown', onMouseDown);
  container.value.removeEventListener('mousemove', onMouseMove);
  container.value.removeEventListener('mouseup', onMouseUp);
  container.value.removeEventListener('wheel', onWheel);

  // Remove keyboard event listener
  window.removeEventListener('keydown', handleKeydown);

  // Clear notification timer
  if (undoRedoNotificationTimer.value) {
    window.clearTimeout(undoRedoNotificationTimer.value);
  }
});

defineExpose({
  getClickDataForApi,
  performUndo,
  performRedo,
  canUndo,
  canRedo,
  refreshViewport,
  refreshMarkers,
  recreateMarkers,
  forceRenderUpdate
});
</script>

<style scoped>
.point-cloud-viewer {
  width: 100%;
  height: 100%;
  overflow: hidden;
  position: relative;
}

.undo-redo-notification {
  position: absolute;
  top: 70px;
  left: 50%;
  transform: translateX(-50%);
  background-color: rgba(0, 0, 0, 0.7);
  color: white;
  padding: 8px 16px;
  border-radius: 4px;
  font-size: 14px;
  z-index: 100;
  transition: opacity 0.3s ease;
  animation: fadeIn 0.3s, fadeOut 0.3s 1.7s;
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

@keyframes fadeOut {
  from {
    opacity: 1;
  }
  to {
    opacity: 0;
  }
}
</style>