import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { ClickMode, InteractionMode } from '@/types/Selection';
import { threeJsService } from '@/services/ThreeJsService';

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

  // Actions
  const setInteractionMode = (mode: InteractionMode): void => {
    console.log(`Setting interaction mode to: ${mode}`);
    interactionMode.value = mode;
    updateControlsState(mode);
  };

  const toggleInteractionMode = (): void => {
    const newMode = isNavigateMode.value ? 'annotate' : 'navigate';
    console.log(`Toggling interaction mode from ${interactionMode.value} to ${newMode}`);
    interactionMode.value = newMode;
    updateControlsState(interactionMode.value);
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
      // Set cursor style for navigation mode
      cursorStyle.value = 'grab';
    } else {
      console.log('Disabling navigation controls');
      context.controls.enabled = false;
      context.controls.enableRotate = false;
      context.controls.enablePan = false;
      context.controls.enableZoom = false;
      // Set cursor style for annotation mode
      cursorStyle.value = 'crosshair';
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
  };

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

    // Computed
    currentObjectIdx,
    isNavigateMode,
    isAnnotateMode,

    // Actions
    setInteractionMode,
    toggleInteractionMode,
    setClickMode,
    selectObject,
    createNewObject,
    updateObjectInfo,
    showObjectDescription,
    updateControlsState,
    reset
  };
});