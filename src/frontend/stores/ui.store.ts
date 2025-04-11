import {defineStore} from 'pinia';
import {computed, ref, watch} from 'vue';
import {ClickMode, InteractionMode} from '@/types/selection.types';
import {threeJsService} from '@/services/threeJs.service';

export interface ObjectData {
  id: number;
  name: string;
  description?: string;
}

export const useUiStore = defineStore('ui', () => {
  // State
  const interactionMode = ref<InteractionMode>('navigate');
  const clickMode = ref<ClickMode>('object');
  const selectedObjectIndex = ref<number | null>(null);
  const cubeSize = ref<number>(0.02);
  const autoInfer = ref<boolean>(false);
  const showInstructions = ref(true);
  const newObjectName = ref('');
  const objects = ref<ObjectData[]>([]);
  const cursorStyle = ref<string>('auto'); // Add cursor style state

  // Save status tracking
  const hasUnsavedChanges = ref(false);
  const isSaving = ref(false);
  const lastSaveTime = ref<number | null>(null);

  // Analysis dialog state
  const showAnalysisDialog = ref(false);
  const showDescriptionDialog = ref(false);
  const selectedObjectForDescription = ref<ObjectData | null>(null);

  // Computed
  const currentObjectIdx = computed<number | null>(() => {
    return selectedObjectIndex.value !== null
        ? selectedObjectIndex.value + 1
        : null;
  });

  const isNavigateMode = computed<boolean>(() => interactionMode.value === 'navigate');
  const isAnnotateMode = computed<boolean>(() => interactionMode.value === 'annotate');
  const isSelectMode = computed<boolean>(() => interactionMode.value === 'select');

  // Actions
  const setInteractionMode = (mode: InteractionMode): void => {
    console.log(`Setting interaction mode to: ${mode}`);
    interactionMode.value = mode;
    updateControlsState(mode);

    // Update cursor style based on the mode
    if (mode === 'navigate') {
      cursorStyle.value = 'grab';
    } else if (mode === 'annotate') {
      cursorStyle.value = 'crosshair';
    } else if (mode === 'select') {
      cursorStyle.value = 'pointer';
    }

    console.log(`setInteractionMode down.`)
  };

  const toggleInteractionMode = (): void => {
    // Now toggle between navigate and annotate only (S key handles select separately)
    let newMode: InteractionMode = interactionMode.value === 'navigate' ? 'annotate' : 'navigate';
    console.log(`Toggling interaction mode from ${interactionMode.value} to ${newMode}`);
    setInteractionMode(newMode);
    console.log(`toggleInteractionMode done`)
  };

  const setClickMode = (mode: ClickMode): void => {
    clickMode.value = mode;
  };

  const selectObject = (index: number): void => {
    selectedObjectIndex.value = index;
    clickMode.value = 'object';

    // If selecting an object, automatically switch to annotation mode
    if (interactionMode.value !== 'annotate') {
      setInteractionMode('annotate');
    }
  };

  const createNewObject = (name: string): ObjectData | null => {
    if (!name.trim()) return null;

    const newObjId = objects.value.length + 1;
    const newObj = {
      id: newObjId,
      name: name.trim()
    };

    objects.value.push(newObj);
    selectedObjectIndex.value = objects.value.length - 1;

    // Mark that we have unsaved changes
    hasUnsavedChanges.value = true;

    // Switch to annotation mode when creating a new object
    setInteractionMode('annotate');

    return newObj;
  };

  const updateObjectInfo = (id: number, data: Partial<ObjectData>): boolean => {
    const index = objects.value.findIndex(obj => obj.id === id);
    if (index === -1) return false;

    objects.value[index] = {
      ...objects.value[index],
      ...data
    };

    // Mark that we have unsaved changes
    hasUnsavedChanges.value = true;

    return true;
  };

  const showObjectDescription = (object: ObjectData): void => {
    selectedObjectForDescription.value = object;
    showDescriptionDialog.value = true;
  };

  const updateControlsState = (mode: InteractionMode): void => {
    console.log(`Updating ThreeJS controls for mode: ${mode}`);
    const context = threeJsService.getContext();
    if (!context.controls) {
      console.warn('ThreeJS controls not available yet');
      return;
    }

    if (mode === 'navigate') {
      console.log('Enabling navigation controls');
      context.controls.enabled = true;
      context.controls.enableRotate = true;
      context.controls.enablePan = true;
      context.controls.enableZoom = true;
    } else {
      // Both annotate and select modes disable navigation controls
      console.log('Disabling navigation controls');
      context.controls.enabled = false;
      context.controls.enableRotate = false;
      context.controls.enablePan = false;
      context.controls.enableZoom = false;
    }

    // Render a frame to update the view
    threeJsService.renderScene();
  };

  const reset = (): void => {
    objects.value = [];
    selectedObjectIndex.value = null;
    newObjectName.value = '';
    showAnalysisDialog.value = false;
    showDescriptionDialog.value = false;
    selectedObjectForDescription.value = null;

    // Reset save status
    hasUnsavedChanges.value = false;
    isSaving.value = false;
    lastSaveTime.value = null;
  };

  // Methods for save status management
  const startSaving = (): void => {
    isSaving.value = true;
  };

  const finishSaving = (success: boolean = true): void => {
    isSaving.value = false;
    if (success) {
      hasUnsavedChanges.value = false;
      lastSaveTime.value = Date.now();
    }
  };

  // Set up a watcher to detect changes to objects
  watch(
      objects,
      () => {
        // Only set unsaved changes if we have objects and we're not currently in the middle of a reset
        if (objects.value.length > 0) {
          hasUnsavedChanges.value = true;
        }
      },
      {deep: true} // Watch for nested changes
  );

  return {
    // State
    interactionMode,
    clickMode,
    selectedObjectIndex,
    cubeSize,
    autoInfer,
    showInstructions,
    newObjectName,
    objects,
    showAnalysisDialog,
    showDescriptionDialog,
    selectedObjectForDescription,
    cursorStyle, // Expose cursor style

    // Save status state
    hasUnsavedChanges,
    isSaving,
    lastSaveTime,

    // Computed
    currentObjectIdx,
    isNavigateMode,
    isAnnotateMode,
    isSelectMode,

    // Actions
    setInteractionMode,
    toggleInteractionMode,
    setClickMode,
    selectObject,
    createNewObject,
    updateObjectInfo,
    showObjectDescription,
    updateControlsState,
    startSaving,
    finishSaving,
    reset
  };
});