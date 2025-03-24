import * as THREE from 'three';

/**
 * Represents a 3D marker for clicked points
 */
export interface AnnotationMarker {
    /** Unique identifier for the marker */
    id: string;

    /** 3D position of the marker */
    position: THREE.Vector3;

    /** Mesh object representing the marker in the scene */
    mesh: THREE.Mesh | null;

    /** Object index this marker belongs to (0 for background) */
    objectIdx: number;

    /** Visual radius of the marker */
    radius: number;

    /** Color of the marker */
    color: THREE.Color;

    /** Whether the marker is currently visible */
    visible: boolean;

    /** Custom metadata for the marker */
    metadata?: Record<string, any>;

    /** Index of the corresponding click point (for syncing) */
    clickPointIndex?: number;

    /** Time index of when the marker was created */
    timeIdx?: number;
}

/**
 * Options for creating annotation markers
 */
export interface MarkerOptions {
    /** Position for the marker */
    position: number[] | THREE.Vector3;

    /** Object index for the marker (0 for background) */
    objectIdx: number;

    /** Optional color override */
    color?: THREE.Color;

    /** Optional radius override */
    radius?: number;

    /** Whether to make the marker visible immediately */
    visible?: boolean;

    /** Optional metadata */
    metadata?: Record<string, any>;
}

/**
 * Data structure for a click action in the scene
 */
export interface ClickAction {
    /** Position of the click in 3D space */
    position: number[];

    /** Object index for this click (0 for background) */
    objectIdx: number;

    /** Timestamp when the click occurred */
    timestamp: number;

    /** Sequential index of this click in the session */
    sequenceIdx: number;

    /** Size of the selection cube for this click */
    selectionSize: number;

    /** Whether this click created a marker */
    hasMarker: boolean;

    /** ID of the associated marker if created */
    markerId?: string;
}

/**
 * Click data formatted for API requests
 */
export interface ApiClickData {
    /** Map of object indices to clicked point indices */
    clickIdx: Record<string, number[]>;

    /** Map of object indices to click time indices */
    clickTimeIdx: Record<string, number[]>;

    /** Map of object indices to click positions */
    clickPositions: Record<string, number[][]>;
}