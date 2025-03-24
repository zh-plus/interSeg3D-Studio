import * as THREE from 'three';

export interface PointCloudData {
    file: File | null;
    pointCount: number;
    positions: Float32Array | null;
    originalColors: Float32Array | null;
    currentColors: Float32Array | null;
    geometry: THREE.BufferGeometry | null;
    boundingBox: THREE.Box3 | null;
    pointSize: number;
}

export interface SegmentedPointCloud {
    segmentation: number[];
}

export interface PointCloudLoadOptions {
    useDefaultColors?: boolean;
    defaultColor?: THREE.Color;
    pointSize?: number;
    onProgress?: (percent: number) => void;
}

export interface PointCloudLoadResult {
    pointCount: number;
    boundingBox: THREE.Box3;
}