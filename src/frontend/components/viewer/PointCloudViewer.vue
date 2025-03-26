<template>
  <div ref="container" class="point-cloud-viewer">
    <!-- Loading overlay -->
    <LoadingOverlay
        :message="pointCloudStore.isLoading ? 'Loading point cloud...' : 'Processing...'"
        :progress="pointCloudStore.loadingProgress ?? undefined"
        :show="pointCloudStore.isLoading || annotationStore.isProcessingSelection"
    />

    <!-- Mode indicator -->
    <ModeIndicator
        :click-mode="uiStore.clickMode"
        :mode="uiStore.interactionMode"
    />

    <!-- Selection info -->
    <SelectionInfo
        :can-redo="annotationStore.canRedo"
        :can-undo="annotationStore.canUndo"
        :click-count="annotationStore.clickCount"
        :click-points="annotationStore.clickedPoints"
        :coordinate="annotationStore.selectedCoordinate"
        :is-processing-selection="annotationStore.isProcessingSelection"
        :point-count="pointCloudStore.pointCloudData.pointCount"
        :show-debug="showDebug"
    />

    <!-- Undo/Redo notification -->
    <div v-if="showUndoRedoNotification" class="undo-redo-notification">
      {{ undoRedoNotificationText }}
    </div>
  </div>
</template>

<script lang="ts" setup>
import {onBeforeUnmount, onMounted, ref, watch} from 'vue';
import * as THREE from 'three';
import {PerformanceLogger} from '@/utils/performance-logger';
import {threeJsService} from '@/services/ThreeJsService';

// Components
import LoadingOverlay from './LoadingOverlay.vue';
import ModeIndicator from './ModeIndicator.vue';
import SelectionInfo from './SelectionInfo.vue';

// Composables
import {useThreeJsRenderer} from '@/composables/useThreeJsRenderer';
import {useRaycasting} from '@/composables/useRaycasting';

// Import Pinia stores
import {useAnnotationStore, usePointCloudStore, useUiStore} from '@/stores';

// Define emits
const emit = defineEmits([
  'point-clicked',
  'point-cloud-loaded',
  'error',
  'create-object',
  'select-object'
]);

// Store instances
const pointCloudStore = usePointCloudStore();
const annotationStore = useAnnotationStore();
const uiStore = useUiStore();

// DOM Container reference
const container = ref<HTMLElement | null>(null);

// Debug settings
const showDebug = ref(import.meta.env.DEV || false);

// Mouse interaction state
const isSelecting = ref(false);
const isDragging = ref(false);
const startMousePosition = ref<{ x: number, y: number } | null>(null);

// Function to update cursor style - define before watch statements
const updateCursorStyle = () => {
  if (!container.value) return;

  console.log(`Setting cursor style to: ${uiStore.cursorStyle}`);
  container.value.style.cursor = uiStore.cursorStyle;

  // Also add active class for additional styling if needed
  if (uiStore.interactionMode === 'navigate') {
    container.value.classList.add('navigate-mode');
    container.value.classList.remove('annotate-mode');
  } else {
    container.value.classList.add('annotate-mode');
    container.value.classList.remove('navigate-mode');
  }
};

// Watch for interaction mode changes to update the controls
watch(() => uiStore.interactionMode, (newMode) => {
  console.log(`PointCloudViewer detected interaction mode change to: ${newMode}`);
  // Ensure ThreeJS controls are updated
  uiStore.updateControlsState(newMode);
  // Update cursor immediately
  updateCursorStyle();
}, {immediate: true});

// Watch for cursor style changes
watch(() => uiStore.cursorStyle, () => {
  updateCursorStyle();
});

// Undo/Redo notification
const showUndoRedoNotification = ref(false);
const undoRedoNotificationText = ref('');
const undoRedoNotificationTimer = ref<number | null>(null);

// Initialize Three.js
const {threeContext, refreshViewport} = useThreeJsRenderer(container);

// Raycasting for point selection
const {
  updateMousePosition,
  tryProgressiveRaycast,
  findNearestPoint
} = useRaycasting({
  spatialIndex: pointCloudStore.spatialIndex,
  pointCloudData: pointCloudStore.pointCloudData,
  cubeSize: uiStore.cubeSize,
  container
});

// Watch for file changes
watch(() => pointCloudStore.pointCloudData.file, async (newFile) => {
  if (!newFile || pointCloudStore.isLoading) return;

  // Clear any previous markers
  annotationStore.clearMarkers();

  // Emit loaded event
  emit('point-cloud-loaded', {
    pointCount: pointCloudStore.pointCloudData.pointCount
  });
});

// Watch for segmentation data changes
watch(() => pointCloudStore.segmentedPointCloud, async (newData) => {
  if (!newData || !pointCloudStore.pointCloudData.pointCount) return;

  // Recreate markers to keep them visible
  annotationStore.recreateMarkers();
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
 * Handle mouse down event
 */
const onMouseDown = (event: MouseEvent): void => {
  startMousePosition.value = {x: event.clientX, y: event.clientY};

  if (pointCloudStore.isLoading) return;

  // Update cursor for dragging in navigate mode
  if (uiStore.interactionMode === 'navigate' && event.button === 0 && container.value) {
    container.value.style.cursor = 'grabbing';
  }

  if (event.button === 2) {
    // Right-click: temporarily enable controls for panning
    event.preventDefault();
    if (uiStore.interactionMode === 'annotate' && threeContext.value?.controls) {
      threeContext.value.controls.enabled = true;
      threeContext.value.controls.enablePan = true;
      // Set panning cursor
      if (container.value) {
        container.value.style.cursor = 'move';
      }
    }
    return;
  }

  if (event.button === 0 && uiStore.interactionMode === 'annotate') {
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

    // Update cursor for dragging in navigate mode
    if (uiStore.interactionMode === 'navigate' && event.buttons === 1 && container.value) {
      container.value.style.cursor = 'grabbing';
    }
  }
};

/**
 * Handle mouse up event
 */
const onMouseUp = (event: MouseEvent): void => {
  const wasDragging = isDragging.value;
  isDragging.value = false;
  startMousePosition.value = null;

  // Reset cursor style
  updateCursorStyle();

  if (event.button === 2) {
    // Right-click: restore controls state
    if (uiStore.interactionMode === 'annotate' && threeContext.value?.controls) {
      threeContext.value.controls.enabled = false;
      threeContext.value.controls.enablePan = false;
    }
    return;
  }

  if (uiStore.interactionMode === 'annotate' && isSelecting.value && !wasDragging) {
    handleAnnotationClick(event);
  }

  isSelecting.value = false;
};

/**
 * Handle annotation click with improved viewport synchronization
 */
const handleAnnotationClick = (event: MouseEvent): void => {
  PerformanceLogger.start('total_click_processing');

  if (pointCloudStore.isLoading || !container.value) return;

  // Check valid click mode - if object mode requires currentObjectIdx, background mode doesn't
  if (uiStore.clickMode === 'object' && uiStore.currentObjectIdx === null) {
    console.warn('No object selected for labeling');
    return;
  }

  // Ensure the Three.js viewport is correctly sized and synchronized with the container
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
  annotationStore.isProcessingSelection = true;

  // Try to raycast
  const raycastResult = tryProgressiveRaycast();

  if (raycastResult && raycastResult.point) {
    // If we got a point, find the nearest actual point
    const nearestPoint = findNearestPoint(raycastResult.point);

    if (nearestPoint) {
      // Store the selected point
      annotationStore.selectedCoordinate = nearestPoint.position;

      // Create a marker at the point
      const marker = annotationStore.createCurrentSelectionMarker(nearestPoint.position);

      // Add the click point to our history
      const objectIdx = uiStore.clickMode === 'background' ? 0 : (uiStore.currentObjectIdx || 0);
      annotationStore.addClickPoint(nearestPoint.position, objectIdx, nearestPoint.index, marker?.id);  // Pass the marker ID

      // Apply selection coloring
      if (uiStore.clickMode === 'object') {
        annotationStore.applySelection(nearestPoint.position, objectIdx);
      }

      // Emit the click event
      emit('point-clicked', nearestPoint.position);
    } else {
      console.warn('No nearest point found');
    }
  } else {
    console.warn('No intersection found');
  }

  annotationStore.isProcessingSelection = false;
  PerformanceLogger.end('total_click_processing');
};

/**
 * Perform undo operation
 */
const performUndo = (): void => {
  if (!annotationStore.canUndo) return;

  const undoneAction = annotationStore.undo();

  if (undoneAction) {
    // Notify user
    showNotification(`Undid click ${undoneAction.clickPoint.objectIdx === 0 ? 'background' : 'object'}`);
  }
};

/**
 * Perform redo operation
 */
const performRedo = (): void => {
  if (!annotationStore.canRedo) return;

  const redoneAction = annotationStore.redo();

  if (redoneAction) {
    // Notify user
    showNotification(`Redid click ${redoneAction.clickPoint.objectIdx === 0 ? 'background' : 'object'}`);
  }
};

/**
 * Refresh markers
 */
const refreshMarkers = () => {
  if (annotationStore.clickCount > 0) {
    console.log('Refreshing markers');
    annotationStore.recreateMarkers();
  }
};

/**
 * Force render update
 */
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
    if (pointCloudStore.pointCloudData.geometry) {
      // Mark color buffer as needing update
      const colorAttrib = pointCloudStore.pointCloudData.geometry.attributes.color;
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
  if (uiStore.interactionMode === 'annotate' && threeContext.value?.camera) {
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

  // Initialize cursor style based on current mode
  updateCursorStyle();

  // Add keyboard event listener for undo/redo
  window.addEventListener('keydown', (e: KeyboardEvent) => {
    // Prevent handling if any input elements are focused
    if (e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement ||
        e.target instanceof HTMLSelectElement) {
      return;
    }

    // Ctrl+Z for undo
    if (e.ctrlKey && !e.shiftKey && (e.key === 'z' || e.key === 'Z')) {
      if (annotationStore.canUndo) {
        e.preventDefault();
        e.stopPropagation(); // Stop event propagation
        performUndo();
      }
    }

    // Shift+Ctrl+Z for redo
    if (e.ctrlKey && e.shiftKey && (e.key === 'z' || e.key === 'Z')) {
      if (annotationStore.canRedo) {
        e.preventDefault();
        e.stopPropagation(); // Stop event propagation
        performRedo();
      }
    }
  });

  console.log('PointCloudViewer: Mounted with mode', uiStore.interactionMode);
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

// Method to handle keyboard events
function handleKeydown(e: KeyboardEvent): void {
  // Implementation moved to the inline event listener above
}

defineExpose({
  performUndo,
  performRedo,
  refreshViewport,
  refreshMarkers,
  forceRenderUpdate,
  getClickDataForApi: () => annotationStore.clickDataForApi
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