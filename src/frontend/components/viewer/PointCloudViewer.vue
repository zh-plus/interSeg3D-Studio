// The file content remains largely the same, we only need to update the keyboard event handler

<template>
  <div class="point-cloud-viewer">
    <!-- Use the extracted viewport component -->
    <ViewportComponent
        ref="viewportComponent"
        :interaction-mode="uiStore.interactionMode"
        :cursor-style="uiStore.cursorStyle"
        @scene-ready="handleSceneReady"
        @viewport-resize="handleViewportResize"
        @render-error="handleRenderError"
    >
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
    </ViewportComponent>

    <!-- Object Edit Panel (outside ViewportComponent to avoid z-index issues) -->
    <ObjectEditPanel
        v-if="showObjectEditPanel"
        :selected-object="selectedObjectForEdit"
        :position="editPanelPosition"
        @close="showObjectEditPanel = false"
        @save="saveObjectChanges"
    />
  </div>
</template>

<script lang="ts" setup>
import {ref, watch, onMounted, onBeforeUnmount, computed} from 'vue';
import * as THREE from 'three';
import {PerformanceLoggerUtil} from '@/utils/performanceLogger.util';

// Components
import ViewportComponent from './ViewportComponent.vue';
import LoadingOverlay from './LoadingOverlay.vue';
import ModeIndicator from './ModeIndicator.vue';
import SelectionInfo from './SelectionInfo.vue';
import ObjectEditPanel from './ObjectEditPanel.vue';

// Composables
import {useRaycasting} from '@/composables/useRaycasting';

// Import Pinia stores
import {useAnnotationStore, useApiStore, usePointCloudStore, useUiStore} from '@/stores';

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
const apiStore = useApiStore();

// Component references
const viewportComponent = ref<InstanceType<typeof ViewportComponent> | null>(null);

// Debug settings
const showDebug = ref(import.meta.env.DEV || false);

// Mouse interaction state
const isSelecting = ref(false);
const isDragging = ref(false);
const startMousePosition = ref<{ x: number, y: number } | null>(null);
const editPanelPosition = ref<{ x: number, y: number }>({x: 0, y: 0});

// Object edit panel state
const showObjectEditPanel = ref(false);
const selectedObjectForEdit = ref(null);

// Undo/Redo notification
const showUndoRedoNotification = ref(false);
const undoRedoNotificationText = ref('');
const undoRedoNotificationTimer = ref<number | null>(null);

// Get raycasting functionality
const {
  updateMousePosition,
  tryProgressiveRaycast,
  findNearestPoint
} = useRaycasting({
  spatialIndex: pointCloudStore.spatialIndex,
  pointCloudData: pointCloudStore.pointCloudData,
  cubeSize: computed(() => uiStore.cubeSize)
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
 * Save object changes
 */
const saveObjectChanges = (updatedObject: any): void => {
  uiStore.updateObjectInfo(updatedObject.id, {
    name: updatedObject.name,
    description: updatedObject.description
  });

  showNotification(`Updated object: ${updatedObject.name}`);
};

/**
 * Handle scene ready event
 */
const handleSceneReady = (context: any): void => {
  console.log('Three.js scene is ready');

  // Emit loaded event if point cloud is already available
  if (pointCloudStore.pointCloudData.file) {
    emit('point-cloud-loaded', {
      pointCount: pointCloudStore.pointCloudData.pointCount
    });
  }
};

/**
 * Handle viewport resize
 */
const handleViewportResize = ({width, height}: { width: number, height: number }): void => {
  console.debug(`Viewport resized: ${width}x${height}`);
};

/**
 * Run segmentation
 */
const runSegmentation = async (): Promise<void> => {
  if (!apiStore.hasClickData || apiStore.isProcessing || apiStore.operationLock) {
    return;
  }

  try {
    showNotification('Running segmentation...');
    await apiStore.runSegmentation();
    showNotification('Segmentation complete!');
  } catch (error: any) {
    console.error('Error running segmentation:', error);
    showNotification(`Error: ${error.message}`);
  }
};

/**
 * Handle render errors
 */
const handleRenderError = (error: any): void => {
  console.error('Render error:', error);
  emit('error', `Rendering error: ${error.message || 'Unknown error'}`);
};

/**
 * Select an object at the clicked position
 */
const selectObject = (event: MouseEvent): void => {
  console.log('selectObject called in SELECT mode');

  if (!pointCloudStore.segmentedPointCloud || !pointCloudStore.pointCloudData.positions) {
    console.log('No segmented point cloud or positions available');
    return;
  }

  // Update mouse position for raycasting
  const container = viewportComponent.value?.getContainer();
  if (!container) {
    console.log('No container reference available');
    return;
  }

  const rect = container.getBoundingClientRect();
  updateMousePosition(event.clientX, event.clientY, rect);

  // Perform raycasting
  const raycastResult = tryProgressiveRaycast();
  if (!raycastResult || !raycastResult.point) {
    console.log('Raycasting failed to find intersection');
    return;
  }

  // Find the nearest point to the raycast hit
  const nearestPoint = findNearestPoint(raycastResult.point);
  if (!nearestPoint || nearestPoint.index === undefined) {
    console.log('No nearest point found');
    return;
  }

  // Get the object ID from the segmentation mask
  const segmentation = pointCloudStore.segmentedPointCloud.segmentation;
  const objId = segmentation[nearestPoint.index];
  console.log('Found object ID:', objId);

  // Only proceed if we clicked on an actual object (not background)
  if (objId <= 0) {
    console.log('Clicked on background (objId <= 0)');
    return;
  }

  // Find the object in the UI store
  const selectedObject = uiStore.objects.find(obj => obj.id === objId);
  if (!selectedObject) {
    console.log('No matching object found in UI store');
    return;
  }

  console.log('Selected object for edit:', selectedObject);

  // Set up the edit panel
  selectedObjectForEdit.value = selectedObject;

  // Position panel near cursor - using clientX/Y since panel is a direct child of point-cloud-viewer
  editPanelPosition.value = {
    x: Math.min(Math.max(event.clientX, 160), window.innerWidth - 160),
    y: Math.min(Math.max(event.clientY, 150), window.innerHeight - 150)
  };

  console.log('Edit panel position:', editPanelPosition.value);
  showObjectEditPanel.value = true;
  console.log('showObjectEditPanel set to true');

  // Show notification about the selected object
  showNotification(`Selected object: ${selectedObject.name}`);

  // Also highlight the object in the right panel list
  const objIndex = uiStore.objects.findIndex(obj => obj.id === objId);
  if (objIndex !== -1) {
    uiStore.selectedObjectIndex = objIndex;
  }
};

/**
 * Handle mouse down event
 */
const onMouseDown = (event: MouseEvent): void => {
  startMousePosition.value = {x: event.clientX, y: event.clientY};

  if (pointCloudStore.isLoading) return;

  if (event.button === 2) {
    // Right-click: temporarily enable controls for panning
    event.preventDefault();
    if ((uiStore.interactionMode === 'annotate' || uiStore.interactionMode === 'select') &&
        viewportComponent.value?.getContext()?.controls) {
      const controls = viewportComponent.value.getContext()?.controls;
      if (controls) {
        controls.enabled = true;
        controls.enablePan = true;
      }
      // Set panning cursor
      const container = viewportComponent.value?.getContainer();
      if (container) {
        container.style.cursor = 'move';
      }
    }
    return;
  }

  if (event.button === 0) {
    if (uiStore.interactionMode === 'annotate') {
      isSelecting.value = true;
      event.preventDefault();
    }
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
  console.log('Mouse up event, button:', event.button, 'mode:', uiStore.interactionMode);

  const wasDragging = isDragging.value;
  isDragging.value = false;
  startMousePosition.value = null;

  // Reset cursor style
  const container = viewportComponent.value?.getContainer();
  if (container) {
    container.style.cursor = uiStore.cursorStyle;
  }

  if (event.button === 2) {
    // Right-click: restore controls state
    if ((uiStore.interactionMode === 'annotate' || uiStore.interactionMode === 'select') &&
        viewportComponent.value?.getContext()?.controls) {
      const controls = viewportComponent.value.getContext()?.controls;
      if (controls) {
        controls.enabled = false;
        controls.enablePan = false;
      }
    }
    return;
  }

  // LEFT BUTTON CLICK
  if (event.button === 0 && !wasDragging) {
    if (uiStore.interactionMode === 'select') {
      // In select mode, handle object selection
      console.log('In SELECT mode, handling object selection');
      selectObject(event);
    } else if (uiStore.interactionMode === 'annotate' && isSelecting.value) {
      // In annotate mode, handle point annotation
      console.log('In ANNOTATE mode, handling annotation');
      handleAnnotationClick(event);
    }
  }

  isSelecting.value = false;
};

/**
 * Handle annotation click with improved viewport synchronization
 */
const handleAnnotationClick = (event: MouseEvent): void => {
  PerformanceLoggerUtil.start('total_click_processing');

  const container = viewportComponent.value?.getContainer();
  if (pointCloudStore.isLoading || !container) return;

  // Check valid click mode - if object mode requires currentObjectIdx, background mode doesn't
  if (uiStore.clickMode === 'object' && uiStore.currentObjectIdx === null) {
    console.warn('No object selected for labeling');
    return;
  }

  // Get the latest container rect
  const rect = container.getBoundingClientRect();

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
  PerformanceLoggerUtil.end('total_click_processing');
};

/**
 * Handle wheel event for zooming in annotation mode
 */
const onWheel = (event: WheelEvent): void => {
  if ((uiStore.interactionMode === 'annotate' || uiStore.interactionMode === 'select') &&
      viewportComponent.value?.getContext()?.camera) {
    event.preventDefault();

    const context = viewportComponent.value.getContext();
    if (!context || !context.camera) return;

    const zoomSpeed = 0.1;
    const zoomDelta = -Math.sign(event.deltaY) * zoomSpeed;

    const direction = new THREE.Vector3(0, 0, 0);
    context.camera.getWorldDirection(direction);

    if (context.controls) {
      const distance = context.camera.position.distanceTo(
          context.controls.target
      );
      const scaleFactor = distance * zoomDelta;

      context.camera.position.addScaledVector(direction, scaleFactor);
    }

    // Force render update
    viewportComponent.value.renderScene();
  }
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

  if (!viewportComponent.value) return;

  try {
    // Access geometry directly from the store to avoid proxy issues
    if (pointCloudStore.pointCloudData.geometry) {
      // Mark color buffer as needing update
      const colorAttrib = pointCloudStore.pointCloudData.geometry.attributes.color;
      if (colorAttrib) {
        colorAttrib.needsUpdate = true;
      }
    }

    // Use the viewport component to trigger a render
    viewportComponent.value.renderScene();
    console.log('Manual render completed');
  } catch (error) {
    console.error('Error during force render:', error);
    handleRenderError(error);
  }
};

// Handle keyboard events directly (modified to fix the "A" key issue)
const handleKeyboardShortcuts = (e: KeyboardEvent): void => {
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

  // A key to toggle between navigate and annotate modes
  if (e.key === 'a' || e.key === 'A') {
    e.preventDefault();
    e.stopPropagation(); // Stop event propagation to prevent App.vue from handling it again
    // Toggle only between navigate and annotate
    const newMode = uiStore.isNavigateMode ? 'annotate' : 'navigate';
    uiStore.setInteractionMode(newMode);
    showNotification(`Switched to ${newMode.toUpperCase()} mode`);
  }

  // S key to activate select mode
  if (e.key === 's' || e.key === 'S') {
    e.preventDefault();
    e.stopPropagation(); // Stop event propagation
    uiStore.setInteractionMode('select');
    showNotification('Switched to SELECT mode');
  }

  // Enter key to run segmentation
  if (e.key === 'Enter') {
    e.preventDefault();
    e.stopPropagation(); // Stop event propagation
    // Only run if we have click data and we're not already processing
    if (apiStore.hasClickData && !apiStore.isProcessing && !apiStore.operationLock) {
      runSegmentation();
    }
  }
};

// Set up event handlers
onMounted(() => {
  const container = viewportComponent.value?.getContainer();
  if (!container) return;

  // Add event listeners
  container.addEventListener('mousedown', onMouseDown);
  container.addEventListener('mousemove', onMouseMove);
  container.addEventListener('mouseup', onMouseUp);
  container.addEventListener('wheel', onWheel, {passive: false});

  // Add keyboard event listener for shortcuts
  window.addEventListener('keydown', handleKeyboardShortcuts);

  console.log('PointCloudViewer: Mounted with mode', uiStore.interactionMode);
});

// Clean up event handlers
onBeforeUnmount(() => {
  const container = viewportComponent.value?.getContainer();
  if (container) {
    // Remove event listeners
    container.removeEventListener('mousedown', onMouseDown);
    container.removeEventListener('mousemove', onMouseMove);
    container.removeEventListener('mouseup', onMouseUp);
    container.removeEventListener('wheel', onWheel);
  }

  // Remove keyboard event listener
  window.removeEventListener('keydown', handleKeyboardShortcuts);

  // Clear notification timer
  if (undoRedoNotificationTimer.value) {
    window.clearTimeout(undoRedoNotificationTimer.value);
  }
});

// Expose methods to parent
defineExpose({
  performUndo,
  performRedo,
  refreshViewport: () => viewportComponent.value?.refreshViewport(),
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