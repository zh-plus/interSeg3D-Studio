<template>
  <div ref="container" class="viewport-container">
    <!-- Pass through any content via slots -->
    <slot></slot>
  </div>
</template>

<script lang="ts" setup>
import {onBeforeUnmount, onMounted, ref, watch} from 'vue';
import * as THREE from 'three';
import {threeJsService} from '@/services/threeJs.service';
import {useThreeJsRenderer} from '@/composables/useThreeJsRenderer';
import {InteractionMode} from '@/types/selection.types';

// Props
const props = defineProps({
  interactionMode: {
    type: String as () => InteractionMode,
    default: 'navigate'
  },
  cursorStyle: {
    type: String,
    default: 'auto'
  }
});

// Emits
const emit = defineEmits([
  'scene-ready',
  'viewport-resize',
  'render-error'
]);

// DOM Container reference
const container = ref<HTMLElement | null>(null);

// Setup Three.js with the container
const {threeContext, refreshViewport, cleanup} = useThreeJsRenderer(container);

// Force a render of the scene
const renderScene = (): void => {
  try {
    threeJsService.renderScene();
  } catch (error) {
    console.error('Error rendering scene:', error);
    emit('render-error', error);
  }
};

// Update controls based on interaction mode
const updateControlsState = (mode: InteractionMode): void => {
  if (!threeContext.value?.controls) return;

  if (mode === 'navigate') {
    threeContext.value.controls.enabled = true;
    threeContext.value.controls.enableRotate = true;
    threeContext.value.controls.enablePan = true;
    threeContext.value.controls.enableZoom = true;
  } else {
    threeContext.value.controls.enabled = false;
    threeContext.value.controls.enableRotate = false;
    threeContext.value.controls.enablePan = false;
    threeContext.value.controls.enableZoom = false;
  }

  // Force a render to update the view
  renderScene();
};

// Watch for interactionMode changes to update controls
watch(() => props.interactionMode, (newMode) => {
  updateControlsState(newMode);
}, {immediate: true});

// Watch for cursorStyle changes
watch(() => props.cursorStyle, (newStyle) => {
  if (container.value) {
    container.value.style.cursor = newStyle;
  }
});

// Handle scene ready event
const handleSceneReady = (): void => {
  if (threeContext.value) {
    emit('scene-ready', threeContext.value);
  }
};

// Force a resize to ensure canvas fits properly
const forceResize = (): void => {
  if (!container.value) return;

  // *** FIX: Access the DOM element through container.value ***
  const rect = container.value.getBoundingClientRect();
  console.log(`Forcing resize: ${rect.width}x${rect.height}`);

  emit('viewport-resize', {
    width: rect.width,
    height: rect.height
  });

  threeJsService.updateViewport({
    width: rect.width,
    height: rect.height,
    pixelRatio: Math.min(window.devicePixelRatio, 2)
  });

  // Ensure canvas style is properly set
  if (threeContext.value?.renderer?.domElement) {
    const canvas = threeContext.value.renderer.domElement;
    canvas.style.width = '100%';
    canvas.style.height = '100%';
    canvas.style.display = 'block';
  }
};

// Setup on mount
onMounted(() => {
  if (container.value) {
    // Initialize cursor style
    container.value.style.cursor = props.cursorStyle;

    // Initialize viewport size
    const rect = container.value.getBoundingClientRect();
    emit('viewport-resize', {
      width: rect.width,
      height: rect.height
    });

    // Notify parent when scene is ready
    handleSceneReady();

    // Force a resize after a slight delay to ensure proper sizing
    setTimeout(forceResize, 100);
  }
});

// Clean up resources on unmount
onBeforeUnmount(() => {
  cleanup();
});

// Expose methods for the parent component
defineExpose({
  refreshViewport,
  renderScene,
  forceResize,
  getContainer: () => container.value,
  getContext: () => threeContext.value,
  updateMousePosition: (clientX: number, clientY: number) => {
    if (!container.value || !threeContext.value?.raycaster || !threeContext.value?.camera) return null;

    const rect = container.value.getBoundingClientRect();
    const x = ((clientX - rect.left) / rect.width) * 2 - 1;
    const y = -((clientY - rect.top) / rect.height) * 2 + 1;

    const mouseVec = new THREE.Vector2(x, y);
    threeContext.value.raycaster.setFromCamera(mouseVec, threeContext.value.camera);

    return mouseVec;
  },
  performRaycast: (threshold?: number) => {
    if (!threeContext.value?.raycaster || !threeContext.value?.pointCloud) return null;

    // Set threshold if provided
    if (threshold !== undefined) {
      threeContext.value.raycaster.params.Points = {threshold};
    }

    // Perform raycasting
    const intersects = threeContext.value.raycaster.intersectObject(threeContext.value.pointCloud, false);

    if (intersects.length > 0) {
      return {
        point: intersects[0].point,
        index: intersects[0].index,
        distance: intersects[0].distance
      };
    }

    return null;
  }
});
</script>

<style scoped>
.viewport-container {
  width: 100%;
  height: 100%;
  overflow: hidden;
  position: relative;
  display: flex;
  flex-direction: column;
}
</style>