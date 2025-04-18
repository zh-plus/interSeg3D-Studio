import {computed, ref, Ref, watch} from 'vue';
import {ClickMode, InteractionMode} from '@/types/Selection';
import {threeJsService} from '@/services/ThreeJsService';

interface UseInteractionModeOptions {
    // Optional initial mode
    initialMode?: InteractionMode;
    // Optional container for cursor style updates
    container?: Ref<HTMLElement | null>;
}

/**
 * Composable for handling interaction modes (navigate/annotate)
 */
export function useInteractionMode(options?: UseInteractionModeOptions) {
    // Current interaction mode
    const interactionMode = ref<InteractionMode>(options?.initialMode || 'navigate');

    // Annotation click mode
    const clickMode = ref<ClickMode>('object');

    // Selected object index
    const selectedObjectIndex = ref<number | null>(null);

    // Computed property for current object index (1-based for API compatibility)
    const currentObjectIdx = computed<number | null>(() => {
        return selectedObjectIndex.value !== null
            ? selectedObjectIndex.value + 1
            : null;
    });

    // Cube size for selection
    const cubeSize = ref<number>(0.02);

    // Computed to check if we're in navigation mode
    const isNavigateMode = computed<boolean>(() => interactionMode.value === 'navigate');

    // Computed to check if we're in annotation mode
    const isAnnotateMode = computed<boolean>(() => interactionMode.value === 'annotate');

    // Update controls based on mode
    const updateControlsState = (mode: InteractionMode): void => {
        const context = threeJsService.getContext();
        if (!context.controls) return;

        if (mode === 'navigate') {
            context.controls.enabled = true;
            context.controls.enableRotate = true;
            context.controls.enablePan = true;
            context.controls.enableZoom = true;

            // Update cursor
            if (options?.container?.value) {
                options.container.value.style.cursor = 'grab';
            }
        } else {
            context.controls.enabled = false;
            context.controls.enableRotate = false;
            context.controls.enablePan = false;
            context.controls.enableZoom = false;

            // Update cursor
            if (options?.container?.value) {
                options.container.value.style.cursor = 'crosshair';
            }
        }
    };

    // Switch to navigation mode
    const setNavigateMode = (): void => {
        interactionMode.value = 'navigate';
    };

    // Switch to annotation mode
    const setAnnotateMode = (): void => {
        interactionMode.value = 'annotate';
    };

    // Toggle between modes
    const toggleMode = (): void => {
        interactionMode.value = isNavigateMode.value ? 'annotate' : 'navigate';
    };

    // Set click mode
    const setClickMode = (mode: ClickMode): void => {
        clickMode.value = mode;
    };

    // Select an object by index
    const selectObject = (index: number): void => {
        selectedObjectIndex.value = index;
        clickMode.value = 'object';

        // If selecting an object, switch to annotation mode
        if (interactionMode.value !== 'annotate') {
            interactionMode.value = 'annotate';
        }
    };

    // Watch for mode changes
    watch(interactionMode, (newMode) => {
        updateControlsState(newMode);
        console.log(`Interaction mode changed to: ${newMode}`);
    });

    // Initial setup
    updateControlsState(interactionMode.value);

    return {
        // State
        interactionMode,
        clickMode,
        selectedObjectIndex,
        currentObjectIdx,
        cubeSize,
        isNavigateMode,
        isAnnotateMode,

        // Actions
        setNavigateMode,
        setAnnotateMode,
        toggleMode,
        setClickMode,
        selectObject,
        updateControlsState
    };
}