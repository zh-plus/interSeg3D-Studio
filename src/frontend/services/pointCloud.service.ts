import {markRaw} from 'vue';
import * as THREE from 'three';
import {OrbitControls} from 'three/examples/jsm/controls/OrbitControls';
import {PLYLoader} from 'three/examples/jsm/loaders/PLYLoader';
import {PointCloudData, PointCloudLoadOptions, SegmentedPointCloud} from '@/types/pointCloud.types';
import {PerformanceLoggerUtil} from '@/utils/performanceLogger.util';
import {GridSpatialIndexUtil} from '@/utils/gridSpatialIndex.util';
import {getColorFromIndex} from '@/utils/color.util';
import {threeJsService} from '@/services/threeJs.service'

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
        PerformanceLoggerUtil.start('load_ply_file');

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

            PerformanceLoggerUtil.end('load_ply_file');
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
    ): GridSpatialIndexUtil {
        PerformanceLoggerUtil.start('build_spatial_index');

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
        const index = new GridSpatialIndexUtil(cellSize);
        index.build(geometry.attributes.position.array as Float32Array);

        PerformanceLoggerUtil.end('build_spatial_index');
        return index;
    }

    /**
     * Apply segmentation data to point cloud colors
     * @param data Point cloud data
     * @param segmentation Segmentation data
     * @param onProgress Optional callback for progress updates
     * @param onComplete Optional callback when processing is complete
     */
    public applySegmentation(
        data: PointCloudData,
        segmentation: SegmentedPointCloud,
        onProgress?: (progress: number) => void,
        onComplete?: () => void
    ): void {
        PerformanceLoggerUtil.start('apply_segmentation');

        if (!data.geometry || !data.currentColors || !data.originalColors) {
            console.error('Missing required data for segmentation');
            PerformanceLoggerUtil.end('apply_segmentation');
            if (onComplete) onComplete();
            return;
        }

        // Validate segmentation data
        if (!segmentation.segmentation ||
            segmentation.segmentation.length !== data.pointCount) {
            console.error(`Segmentation size mismatch: got ${segmentation.segmentation?.length || 0}, expected ${data.pointCount}`);
            PerformanceLoggerUtil.end('apply_segmentation');
            if (onComplete) onComplete();
            return;
        }

        // Count unique labels more efficiently with sampling
        const uniqueLabels = new Set();
        const sampleSize = Math.min(10000, segmentation.segmentation.length);
        const step = Math.max(1, Math.floor(segmentation.segmentation.length / sampleSize));
        for (let i = 0; i < segmentation.segmentation.length; i += step) {
            uniqueLabels.add(segmentation.segmentation[i]);
        }

        console.log('Applying segmentation to point cloud:',
            segmentation.segmentation.length,
            'points,',
            uniqueLabels.size,
            'unique labels (estimated)');

        // Process in chunks to avoid blocking the main thread
        const chunkSize = 100000; // Process 100k points at a time
        let currentIndex = 0;
        let lastRenderTime = 0;

        const processNextChunk = () => {
            const startTime = performance.now();
            const endIndex = Math.min(currentIndex + chunkSize, data.pointCount);

            // Process this chunk
            for (let i = currentIndex; i < endIndex; i++) {
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

            // Update current index
            currentIndex = endIndex;

            // Calculate progress
            const progress = currentIndex / data.pointCount;
            if (onProgress) onProgress(progress);

            // Update buffer occasionally to show progress (but not too often)
            const now = Date.now();
            if (now - lastRenderTime > 500 || currentIndex === data.pointCount) {  // Max ~2 renders per second
                updateBuffer();
                lastRenderTime = now;
            }

            // Log performance for debugging
            const chunkTime = performance.now() - startTime;
            if (currentIndex % (chunkSize * 10) === 0 || currentIndex === data.pointCount) {
                console.log(`Processed ${currentIndex.toLocaleString()} / ${data.pointCount.toLocaleString()} points (${Math.round(progress * 100)}%) in ${chunkTime.toFixed(0)}ms`);
            }

            // Continue or finish
            if (currentIndex < data.pointCount) {
                // Schedule next chunk with a small delay to allow UI to update
                setTimeout(processNextChunk, 0);
            } else {
                // Final update and cleanup
                updateBuffer();
                PerformanceLoggerUtil.end('apply_segmentation');
                console.log('Segmentation application complete');
                if (onComplete) onComplete();
            }
        };

        // Helper to update the buffer
        const updateBuffer = () => {
            if (data.geometry && data.geometry.attributes.color) {
                const colorAttribute = data.geometry.attributes.color as THREE.BufferAttribute;
                colorAttribute.array.set(data.currentColors);
                colorAttribute.needsUpdate = true;

                // Force a render update to show progress
                threeJsService.renderScene();
            }
        };

        // Start processing
        processNextChunk();
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