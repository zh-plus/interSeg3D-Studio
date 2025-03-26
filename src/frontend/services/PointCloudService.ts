import {markRaw} from 'vue';
import * as THREE from 'three';
import {OrbitControls} from 'three/examples/jsm/controls/OrbitControls';
import {PLYLoader} from 'three/examples/jsm/loaders/PLYLoader';
import {PointCloudData, PointCloudLoadOptions, SegmentedPointCloud} from '@/types/PointCloudTypes';
import {PerformanceLogger} from '@/utils/performance-logger';
import {GridSpatialIndex} from '@/utils/GridSpatialIndex';
import {getColorFromIndex} from '@/utils/color-utils';
import {threeJsService} from '@/services/ThreeJsService'

/**
 * Service for loading and managing point cloud data
 */
class PointCloudService {
    /**
     * Load a PLY file and return a Three.js Points object
     * @param file The PLY file to load
     * @param options Loading options
     * @returns Promise resolving to the loaded Points object
     */
    public async loadPLYFile(
        file: File,
        options?: PointCloudLoadOptions
    ): Promise<THREE.Points> {
        PerformanceLogger.start('load_ply_file');

        // Validate file
        if (!file.name.toLowerCase().endsWith('.ply')) {
            return Promise.reject(new Error('Invalid file type. Please upload a PLY file.'));
        }

        // Create file URL
        const fileURL = URL.createObjectURL(file);

        try {
            // Load geometry using PLYLoader
            const geometry = await this.loadGeometry(fileURL, (progress) => {
                if (options?.onProgress) {
                    options.onProgress(progress);
                }
            });

            // Mark the geometry as raw to prevent Vue from making it reactive
            markRaw(geometry);

            // Add color attribute if missing
            if (!geometry.hasAttribute('color') && options?.useDefaultColors !== false) {
                const colors = new Float32Array(geometry.attributes.position.count * 3);
                const defaultColor = options?.defaultColor || new THREE.Color(0.8, 0.8, 0.8);

                for (let i = 0; i < colors.length; i += 3) {
                    colors[i] = defaultColor.r;
                    colors[i + 1] = defaultColor.g;
                    colors[i + 2] = defaultColor.b;
                }

                geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
            }

            // Create material with appropriate point size
            const pointSize = options?.pointSize || 0.03;
            const material = new THREE.PointsMaterial({
                size: pointSize,
                vertexColors: true,
                sizeAttenuation: true,
                alphaTest: 0.5
            });

            // Create and return Points object, marked as raw
            const pointCloud = markRaw(new THREE.Points(geometry, material));

            PerformanceLogger.end('load_ply_file');
            return pointCloud;
        } finally {
            // Clean up URL
            URL.revokeObjectURL(fileURL);
        }
    }

    /**
     * Build a spatial index for a point cloud geometry
     * @param geometry The point cloud geometry
     * @param cellSize Optional cell size (calculated automatically if not provided)
     * @returns The built spatial index
     */
    public buildSpatialIndex(
        geometry: THREE.BufferGeometry,
        cellSize?: number
    ): GridSpatialIndex {
        PerformanceLogger.start('build_spatial_index');

        if (!geometry.attributes.position) {
            throw new Error('Geometry has no position attribute');
        }

        // Calculate optimal cell size if not provided
        if (!cellSize) {
            const boundingBox = new THREE.Box3().setFromBufferAttribute(
                geometry.attributes.position as THREE.BufferAttribute
            );

            const size = new THREE.Vector3();
            boundingBox.getSize(size);

            const maxDimension = Math.max(size.x, size.y, size.z);
            const pointCount = geometry.attributes.position.count;

            // Adjust cell size based on point count and dimensions
            if (pointCount > 1000000) {
                cellSize = maxDimension / 30;
            } else if (pointCount < 100000) {
                cellSize = maxDimension / 100;
            } else {
                cellSize = maxDimension / 50;
            }
        }

        // Create and build index
        const index = new GridSpatialIndex(cellSize);
        index.build(geometry.attributes.position.array as Float32Array);

        PerformanceLogger.end('build_spatial_index');
        return index;
    }

    /**
     * Apply segmentation data to point cloud colors
     * @param data Point cloud data
     * @param segmentation Segmentation data
     * @returns Whether the operation succeeded
     */
    public applySegmentation(
        data: PointCloudData,
        segmentation: SegmentedPointCloud
    ): boolean {
        PerformanceLogger.start('apply_segmentation');

        if (!data.geometry || !data.currentColors || !data.originalColors) {
            console.error('Missing required data for segmentation');
            PerformanceLogger.end('apply_segmentation');
            return false;
        }

        // Validate segmentation data
        if (!segmentation.segmentation ||
            segmentation.segmentation.length !== data.pointCount) {
            console.error(`Segmentation size mismatch: got ${segmentation.segmentation?.length || 0}, expected ${data.pointCount}`);
            PerformanceLogger.end('apply_segmentation');
            return false;
        }

        console.log('Applying segmentation to point cloud:',
            segmentation.segmentation.length,
            'points,',
            [...new Set(segmentation.segmentation)].length,
            'unique labels');

        // Apply segmentation colors
        for (let i = 0; i < data.pointCount; i++) {
            const label = segmentation.segmentation[i];
            const colorIndex = i * 3;

            if (label !== 0) {
                // Object points get their object color
                const color = getColorFromIndex(label);

                data.currentColors[colorIndex] = color.r;
                data.currentColors[colorIndex + 1] = color.g;
                data.currentColors[colorIndex + 2] = color.b;
            } else {
                // Background points get original colors
                data.currentColors[colorIndex] = data.originalColors[colorIndex];
                data.currentColors[colorIndex + 1] = data.originalColors[colorIndex + 1];
                data.currentColors[colorIndex + 2] = data.originalColors[colorIndex + 2];
            }
        }

        // Update the geometry - add more verbose logging
        if (data.geometry.attributes.color) {
            const colorAttribute = data.geometry.attributes.color as THREE.BufferAttribute;
            colorAttribute.array.set(data.currentColors);
            colorAttribute.needsUpdate = true;

            // Add more detailed logging
            console.log('Color attribute updated:',
                colorAttribute.array.length,
                'color components updated,',
                'needsUpdate flag set');

            // Check geometry references
            const context = threeJsService.getContext();
            if (context.pointGeometry) {
                console.log('Checking geometry references:',
                    'Service geometry:', data.geometry.uuid,
                    'Context geometry:', context.pointGeometry.uuid,
                    'References equal:', data.geometry === context.pointGeometry);
            }
        }

        PerformanceLogger.end('apply_segmentation');
        return true;
    }

    /**
     * Reset point cloud colors to original state
     * @param data Point cloud data
     * @returns Whether the operation succeeded
     */
    public resetColors(data: PointCloudData): boolean {
        if (!data.geometry || !data.currentColors || !data.originalColors) {
            return false;
        }

        // Copy original colors back to current colors
        for (let i = 0; i < data.originalColors.length; i++) {
            data.currentColors[i] = data.originalColors[i];
        }

        // Update buffer
        if (data.geometry.attributes.color) {
            const colorAttribute = data.geometry.attributes.color as THREE.BufferAttribute;
            colorAttribute.array.set(data.currentColors);
            colorAttribute.needsUpdate = true;
            return true;
        }

        return false;
    }

    /**
     * Center camera on a point cloud
     * @param geometry The point cloud geometry
     * @param camera The camera to position
     * @param controls The OrbitControls instance
     * @returns The center and size of the bounding box
     */
    public centerCameraOnPointCloud(
        geometry: THREE.BufferGeometry,
        camera: THREE.PerspectiveCamera,
        controls: OrbitControls
    ): { center: THREE.Vector3, size: number } {
        geometry.computeBoundingBox();
        const boundingBox = geometry.boundingBox as THREE.Box3;
        const center = new THREE.Vector3();
        boundingBox.getCenter(center);

        // Calculate max dimension
        const size = new THREE.Vector3();
        boundingBox.getSize(size);
        const maxDim = Math.max(size.x, size.y, size.z);

        // Position camera
        camera.position.set(
            center.x + maxDim,
            center.y - maxDim,
            center.z + maxDim * 0.5
        );

        camera.lookAt(center);

        // Update controls
        controls.target.copy(center);
        controls.update();

        return {center, size: maxDim};
    }

    /**
     * Load a geometry from a PLY file URL
     * @param url The URL of the PLY file
     * @param onProgress Progress callback
     * @returns Promise resolving to the loaded geometry
     */
    private loadGeometry(
        url: string,
        onProgress?: (percent: number) => void
    ): Promise<THREE.BufferGeometry> {
        return new Promise((resolve, reject) => {
            const loader = new PLYLoader();

            loader.load(
                url,
                (geometry) => resolve(geometry),
                (xhr) => {
                    if (onProgress && xhr.lengthComputable) {
                        const percent = Math.round((xhr.loaded / xhr.total) * 100);
                        onProgress(percent);
                    }
                },
                (error) => reject(error)
            );
        });
    }
}

// Export singleton instance
export const pointCloudService = new PointCloudService();