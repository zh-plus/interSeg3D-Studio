import * as THREE from 'three';

export type InteractionMode = 'navigate' | 'annotate' | 'select';
export type ClickMode = 'object' | 'background';

export interface ClickPoint {
    position: number[];
    objectIdx: number;
    timeIdx?: number;
    index?: number; // Added to store the actual point index in the point cloud
}

export interface ClickResult {
    position: number[];
    index?: number;
    distance?: number;
}

export interface SelectionOptions {
    cubeSize: number;
    mode: ClickMode;
    objectIdx: number | null;
}

export interface RaycastResult {
    point: THREE.Vector3;
    index?: number;
    distance?: number;
}