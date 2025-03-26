import * as THREE from 'three';
import {OrbitControls} from 'three/examples/jsm/controls/OrbitControls';

export interface ThreeJsContext {
    scene: THREE.Scene | null;
    camera: THREE.PerspectiveCamera | null;
    renderer: THREE.WebGLRenderer | null;
    controls: OrbitControls | null;
    raycaster: THREE.Raycaster | null;
    pointCloud: THREE.Points | null;
    pointGeometry: THREE.BufferGeometry | null;
    clickSpheres: THREE.Mesh[];
    isAnimating: boolean;
    animationFrameId: number;
}

export interface ThreeJsInitOptions {
    container: HTMLElement;
    antialias?: boolean;
    backgroundColor?: THREE.Color | string | number;
    cameraPosition?: THREE.Vector3;
    cameraFov?: number;
    nearPlane?: number;
    farPlane?: number;
}

export interface ViewportOptions {
    width: number;
    height: number;
    pixelRatio?: number;
}