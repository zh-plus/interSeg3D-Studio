import * as THREE from 'three';

/**
 * Generate a color based on an object index
 * @param index The object index
 * @param saturation Saturation (0-1)
 * @param lightness Lightness (0-1)
 * @returns THREE.Color object
 */
export function getColorFromIndex(index: number, saturation = 1.0, lightness = 0.5): THREE.Color {
    // Use a consistent algorithm to generate colors (similar to the Python implementation)
    const hue = (index * 50) % 360;
    return new THREE.Color().setHSL(hue / 360, saturation, lightness);
}

/**
 * Generate a CSS color string based on an object index
 * @param index The object index
 * @param saturation Saturation (0-100)
 * @param lightness Lightness (0-100)
 * @param alpha Alpha (0-1)
 * @returns CSS color string (hsl or hsla)
 */
export function getCssColorFromIndex(
    index: number,
    saturation = 80,
    lightness = 60,
    alpha?: number
): string {
    const hue = (index * 50) % 360;

    return alpha !== undefined
        ? `hsla(${hue}, ${saturation}%, ${lightness}%, ${alpha})`
        : `hsl(${hue}, ${saturation}%, ${lightness}%)`;
}

/**
 * Get a selection color based on click mode and object index
 * @param mode Click mode ('object' or 'background')
 * @param objectIdx Object index
 * @returns THREE.Color object
 */
export function getSelectionColor(
    mode: 'object' | 'background',
    objectIdx: number | null
): THREE.Color {
    if (mode === 'background') {
        return new THREE.Color(0.1, 0.1, 0.1); // Dark gray for background
    } else if (objectIdx !== null) {
        return getColorFromIndex(objectIdx);
    }
    return new THREE.Color(1.0, 1.0, 1.0); // White fallback
}

/**
 * Apply color to a buffer at a specific position
 * @param buffer Float32Array of colors
 * @param index Index in the buffer
 * @param color THREE.Color to apply
 */
export function applyColorToBuffer(buffer: Float32Array, index: number, color: THREE.Color): void {
    buffer[index] = color.r;
    buffer[index + 1] = color.g;
    buffer[index + 2] = color.b;
}