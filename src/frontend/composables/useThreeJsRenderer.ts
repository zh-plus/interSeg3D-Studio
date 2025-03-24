import {markRaw, onBeforeUnmount, onMounted, Ref, shallowRef} from 'vue';
import {ThreeJsContext} from '@/types/ThreeJs';
import {threeJsService} from '@/services/ThreeJsService';
import {debounce} from '@/utils/debounce';

export function useThreeJsRenderer(container: Ref<HTMLElement | null>) {
    // Use shallowRef instead of ref for Three.js objects to prevent deep reactivity
    const threeContext = shallowRef<ThreeJsContext | null>(null);
    let resizeObserver: ResizeObserver | null = null;

    const initThreeJs = (): void => {
        if (!container.value) return;

        // Initialize the Three.js scene and mark it as raw to prevent proxying
        threeContext.value = markRaw(threeJsService.init({
            container: container.value,
            backgroundColor: 0x111111,
            antialias: true
        }));

        // Add lighting
        threeJsService.addSceneLighting();

        // Start animation
        threeJsService.startAnimation();

        // Setup resize handler
        window.addEventListener('resize', handleResize);
        window.addEventListener('focus', handleFocus);
        setupResizeObserver();
        container.value.addEventListener('contextmenu', (e) => e.preventDefault());
    };

    // Setup ResizeObserver to track container size changes
    const setupResizeObserver = (): void => {
        if (!container.value) return;

        // Create new ResizeObserver
        resizeObserver = new ResizeObserver((entries) => {
            for (const entry of entries) {
                const {width, height} = entry.contentRect;
                console.debug(`Container resized via ResizeObserver: ${width}x${height}`);

                // Update viewport with the new dimensions
                threeJsService.updateViewport({
                    width,
                    height,
                    pixelRatio: Math.min(window.devicePixelRatio, 2)
                });
            }
        });

        // Start observing the container
        resizeObserver.observe(container.value);
    };

    // Handle window resize with both immediate and debounced updates
    const handleResize = () => {
        if (!container.value) return;

        // Immediate update for better responsiveness
        const {width, height} = container.value.getBoundingClientRect();
        console.debug(`Window resize detected: ${width}x${height}`);

        threeJsService.updateViewport({
            width: container.value.clientWidth,
            height: container.value.clientHeight,
            pixelRatio: Math.min(window.devicePixelRatio, 2)
        });

        // Debounced update for full recalculation
        debouncedResize();
    };

    // Handle window focus event
    const handleFocus = () => {
        if (!container.value) return;

        console.debug('Window focused, updating viewport');
        threeJsService.updateViewport({
            width: container.value.clientWidth,
            height: container.value.clientHeight,
            pixelRatio: Math.min(window.devicePixelRatio, 2)
        });
    };

    // Debounced resize handler for performance
    const debouncedResize = debounce(() => {
        if (!container.value) return;

        threeJsService.updateViewport({
            width: container.value.clientWidth,
            height: container.value.clientHeight,
            pixelRatio: Math.min(window.devicePixelRatio, 2)
        });
    }, 100);

    // Clean up resources
    const cleanup = (): void => {
        // Remove event listeners
        window.removeEventListener('resize', handleResize);
        window.removeEventListener('focus', handleFocus);

        if (container.value) {
            container.value.removeEventListener('contextmenu', (e) => e.preventDefault());
        }

        // Clean up ResizeObserver
        if (resizeObserver) {
            resizeObserver.disconnect();
            resizeObserver = null;
        }

        // Clean up Three.js
        threeJsService.cleanup();
        threeContext.value = null;
    };

    // Setup on mount, clean up on unmount
    onMounted(() => {
        initThreeJs();
    });

    onBeforeUnmount(() => {
        cleanup();
    });

    // Expose a manual refresh method for forcing viewport update
    const refreshViewport = () => {
        if (!container.value) return;

        console.debug('Manual viewport refresh requested');
        threeJsService.updateViewport({
            width: container.value.clientWidth,
            height: container.value.clientHeight,
            pixelRatio: Math.min(window.devicePixelRatio, 2)
        });
    };

    return {
        threeContext,
        initThreeJs,
        cleanup,
        refreshViewport
    };
}