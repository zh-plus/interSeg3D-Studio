// A simple and efficient spatial index for 3D point clouds using a grid-based approach
import {PerformanceLoggerUtil} from '@/utils/performanceLogger.util';

/**
 * Options for building the spatial index
 */
export interface SpatialIndexOptions {
    cellSize?: number;
    maxPointsPerCell?: number;
    logPerformance?: boolean;
}

/**
 * A grid-based spatial index for quickly finding points in 3D space
 */
export class GridSpatialIndexUtil {
    private cells: Map<string, number[]> = new Map();
    private cellSize: number;
    private pointCount: number = 0;
    private bounds: {
        min: [number, number, number];
        max: [number, number, number];
    } | null = null;

    /**
     * Create a new grid spatial index
     * @param cellSize Size of each grid cell (smaller = more precise but slower to build, larger = faster but less precise)
     */
    constructor(cellSize: number = 0.1) {
        this.cellSize = cellSize;
    }

    /**
     * Build the spatial index from a positions array
     * @param positions Float32Array of positions (x,y,z triples)
     * @param options Additional build options
     * @returns The number of points indexed
     */
    build(positions: Float32Array, options?: SpatialIndexOptions): number {
        const logPerformance = options?.logPerformance ?? true;

        if (logPerformance) {
            PerformanceLoggerUtil.start('build_spatial_index');
        }

        this.cells.clear();
        this.pointCount = positions.length / 3;

        // Calculate bounds
        this.calculateBounds(positions);

        // Process every point in the cloud
        for (let i = 0; i < positions.length; i += 3) {
            const x = positions[i];
            const y = positions[i + 1];
            const z = positions[i + 2];

            // Get cell key for this point
            const key = this.getCellKey(x, y, z);

            // Add to cell
            if (!this.cells.has(key)) {
                this.cells.set(key, []);
            }

            // Store the point index (divided by 3 since we're storing the index of the point, not the component)
            this.cells.get(key)!.push(i / 3);
        }

        if (logPerformance) {
            PerformanceLoggerUtil.end('build_spatial_index');
            console.log(`Built spatial index with ${this.cells.size} cells for ${this.pointCount} points`);
        }

        return this.pointCount;
    }

    /**
     * Get the calculated bounds of the indexed points
     * @returns The bounds object or null if not calculated
     */
    getBounds(): { min: [number, number, number]; max: [number, number, number] } | null {
        return this.bounds;
    }

    /**
     * Find all points within a cube centered at the specified position
     * @param position Center position [x,y,z]
     * @param size Half-width of the cube
     * @returns Array of point indices
     */
    findPointsInCube(position: number[], size: number): number[] {
        const result: number[] = [];

        // Calculate cell bounds
        const minX = Math.floor((position[0] - size) / this.cellSize);
        const maxX = Math.floor((position[0] + size) / this.cellSize);
        const minY = Math.floor((position[1] - size) / this.cellSize);
        const maxY = Math.floor((position[1] + size) / this.cellSize);
        const minZ = Math.floor((position[2] - size) / this.cellSize);
        const maxZ = Math.floor((position[2] + size) / this.cellSize);

        // Check each cell in the range
        for (let x = minX; x <= maxX; x++) {
            for (let y = minY; y <= maxY; y++) {
                for (let z = minZ; z <= maxZ; z++) {
                    const key = `${x},${y},${z}`;
                    const cellPoints = this.cells.get(key);

                    if (cellPoints) {
                        result.push(...cellPoints);
                    }
                }
            }
        }

        return result;
    }

    /**
     * Get the number of points in the index
     */
    getPointCount(): number {
        return this.pointCount;
    }

    /**
     * Get the number of cells in the index
     */
    getCellCount(): number {
        return this.cells.size;
    }

    /**
     * Get the cell size
     */
    getCellSize(): number {
        return this.cellSize;
    }

    /**
     * Calculate bounds of the point cloud
     * @param positions Float32Array of positions
     */
    private calculateBounds(positions: Float32Array): void {
        if (positions.length === 0) {
            this.bounds = {
                min: [0, 0, 0],
                max: [0, 0, 0]
            };
            return;
        }

        const min: [number, number, number] = [
            positions[0],
            positions[1],
            positions[2]
        ];

        const max: [number, number, number] = [
            positions[0],
            positions[1],
            positions[2]
        ];

        for (let i = 3; i < positions.length; i += 3) {
            min[0] = Math.min(min[0], positions[i]);
            min[1] = Math.min(min[1], positions[i + 1]);
            min[2] = Math.min(min[2], positions[i + 2]);

            max[0] = Math.max(max[0], positions[i]);
            max[1] = Math.max(max[1], positions[i + 1]);
            max[2] = Math.max(max[2], positions[i + 2]);
        }

        this.bounds = {min, max};
    }

    /**
     * Get the key for a given point
     * @param x X coordinate
     * @param y Y coordinate
     * @param z Z coordinate
     * @returns String key in the format "x,y,z"
     */
    private getCellKey(x: number, y: number, z: number): string {
        // Convert point to grid cell coordinates
        const cellX = Math.floor(x / this.cellSize);
        const cellY = Math.floor(y / this.cellSize);
        const cellZ = Math.floor(z / this.cellSize);

        return `${cellX},${cellY},${cellZ}`;
    }
}