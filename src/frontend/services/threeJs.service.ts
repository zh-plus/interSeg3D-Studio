import * as THREE from 'three';
import {OrbitControls} from 'three/examples/jsm/controls/OrbitControls';
import {ThreeJsContext, ThreeJsInitOptions, ViewportOptions} from '@/types/threeJs.types';

/**
 * Service to manage Three.js setup and rendering
 * This replaces the original ThreeJsContext.ts
 */
class ThreeJsService {
    // Main Three.js objects
    private context: ThreeJsContext = {
        scene: null,
        camera: null,
        renderer: null,
        controls: null,
        raycaster: null,
        pointCloud: null,
        pointGeometry: null,
        clickSpheres: [],
        isAnimating: false,
        animationFrameId: 0
    };

    /**
     * Initialize the Three.js scene
     * @param options Initialization options
     * @returns The Three.js context
     */
    public init(options: ThreeJsInitOptions): ThreeJsContext {
        // Clean up any existing context first
        this.cleanup();

        const {
            container,
            antialias = true,
            backgroundColor = 0x111111,
            cameraPosition = new THREE.Vector3(5, -5, 5),
            cameraFov = 75,
            nearPlane = 0.1,
            farPlane = 1000
        } = options;

        // Create scene
        this.context.scene = new THREE.Scene();
        this.context.scene.background = backgroundColor instanceof THREE.Color
            ? backgroundColor
            : new THREE.Color(backgroundColor);

        // Create camera
        const width = container.clientWidth;
        const height = container.clientHeight;
        this.context.camera = new THREE.PerspectiveCamera(cameraFov, width / height, nearPlane, farPlane);
        this.context.camera.position.copy(cameraPosition);
        this.context.camera.up.set(0, 0, 1);

        // Create renderer
        this.context.renderer = new THREE.WebGLRenderer({
            antialias,
            powerPreference: 'high-performance',
            depth: true,
            logarithmicDepthBuffer: true
        });
        this.context.renderer.setSize(width, height);
        this.context.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        container.appendChild(this.context.renderer.domElement);

        // Create raycaster
        this.context.raycaster = new THREE.Raycaster();
        this.context.raycaster.params.Points = {threshold: 0.01};

        // Create controls
        this.context.controls = new OrbitControls(this.context.camera, this.context.renderer.domElement);
        this.context.controls.enableDamping = true;
        this.context.controls.dampingFactor = 0.25;
        this.context.controls.rotateSpeed = 0.5;
        this.context.controls.zoomSpeed = 1.2;
        this.context.controls.panSpeed = 0.8;

        // Initialize clickSpheres array
        this.context.clickSpheres = [];

        // Return the context
        return this.context;
    }

    /**
     * Start the animation loop
     */
    public startAnimation(): void {
        if (this.context.isAnimating) return;

        const animate = () => {
            this.context.animationFrameId = requestAnimationFrame(animate);

            try {
                if (this.context.controls && this.context.controls.enabled) {
                    this.context.controls.update();
                }

                if (this.context.renderer && this.context.camera && this.context.scene) {
                    this.context.renderer.render(this.context.scene, this.context.camera);
                }
            } catch (error) {
                console.error('Animation error:', error);
                this.stopAnimation();
            }
        };

        this.context.isAnimating = true;
        animate();
    }

    /**
     * Stop the animation loop
     */
    public stopAnimation(): void {
        if (this.context.animationFrameId) {
            cancelAnimationFrame(this.context.animationFrameId);
            this.context.animationFrameId = 0;
            this.context.isAnimating = false;
        }
    }

    /**
     * Set the point cloud
     * @param pointCloud The point cloud object
     */
    public setPointCloud(pointCloud: THREE.Points): void {
        if (this.context.pointCloud && this.context.scene) {
            this.context.scene.remove(this.context.pointCloud);
        }

        this.context.pointCloud = pointCloud;
        this.context.pointGeometry = pointCloud.geometry;

        // Ensure the material is correctly configured for color updates
        if (pointCloud.material instanceof THREE.PointsMaterial) {
            pointCloud.material.vertexColors = true;
            pointCloud.material.needsUpdate = true;
        }

        // Ensure the point cloud has identity transforms
        pointCloud.position.set(0, 0, 0);
        pointCloud.rotation.set(0, 0, 0);
        pointCloud.scale.set(1, 1, 1);
        pointCloud.updateMatrix();
        pointCloud.updateMatrixWorld();

        if (this.context.scene) {
            this.context.scene.add(pointCloud);
        }
    }

    /**
     * Create a sphere marker at a clicked point
     * @param position Sphere position
     * @param color Sphere color
     * @param radius Sphere radius
     * @returns The created sphere mesh or null on failure
     */
    public createMarkerSphere(position: THREE.Vector3, color: THREE.Color, radius: number = 0.02): THREE.Mesh | null {
        if (!this.context.scene) {
            console.error("Cannot create sphere: scene is not initialized");
            return null;
        }

        try {
            // Use a higher-resolution sphere for better appearance
            const geometry = new THREE.SphereGeometry(radius, 16, 16);

            // Use MeshPhongMaterial for better appearance with lighting
            const material = new THREE.MeshPhongMaterial({
                color: color.clone(),
                emissive: color.clone().multiplyScalar(0.2),
                transparent: true,
                opacity: 0.8,
                shininess: 80,
                specular: new THREE.Color(0x111111)
            });

            const sphere = new THREE.Mesh(geometry, material);
            sphere.position.copy(position);
            sphere.name = 'click-sphere';

            // Set unique render order to prevent Z-fighting between markers
            sphere.renderOrder = Date.now() % 1000; // Use timestamp to ensure different render orders

            // Ensure the marker is visible for raycasting
            sphere.visible = true;
            sphere.userData = {type: 'marker'};

            // Add the sphere to the scene
            this.context.scene.add(sphere);
            this.context.clickSpheres.push(sphere);

            return sphere;
        } catch (error) {
            console.error("Error creating sphere:", error);
            return null;
        }
    }

    /**
     * Remove all marker spheres
     */
    public clearMarkerSpheres(): void {
        if (!this.context.scene) return;

        this.context.clickSpheres.forEach(sphere => {
            if (this.context.scene) {
                this.context.scene.remove(sphere);
            }
            if (sphere.geometry) {
                sphere.geometry.dispose();
            }
            if (sphere.material instanceof THREE.Material) {
                sphere.material.dispose();
            } else if (Array.isArray(sphere.material)) {
                sphere.material.forEach(m => m.dispose());
            }
        });

        this.context.clickSpheres = [];
    }

    /**
     * Add standard lighting to the scene
     */
    public addSceneLighting(): void {
        if (!this.context.scene) return;

        // Clear any existing lights
        const existingLights = this.context.scene.children.filter(child =>
            child instanceof THREE.AmbientLight ||
            child instanceof THREE.DirectionalLight ||
            child instanceof THREE.PointLight
        );
        existingLights.forEach(light => this.context.scene?.remove(light));

        // Add ambient light
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.5);
        this.context.scene.add(ambientLight);

        // Add directional light
        const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
        directionalLight.position.set(1, 1, 1).normalize();
        this.context.scene.add(directionalLight);

        // Add point lights for more dimension
        const pointLight1 = new THREE.PointLight(0xffffff, 0.5);
        pointLight1.position.set(5, 5, 5);
        this.context.scene.add(pointLight1);

        const pointLight2 = new THREE.PointLight(0xffffff, 0.3);
        pointLight2.position.set(-5, -5, -5);
        this.context.scene.add(pointLight2);
    }

    /**
     * Add axis helper to the scene
     * @param center Center point for the axis helper
     * @param size Size of the axis helper
     */
    public addAxisHelper(center: THREE.Vector3, size: number): void {
        if (!this.context.scene) return;

        // Remove existing axes
        const existingAxes = this.context.scene.children.filter(
            child => child.name === 'axisHelper' || child.name.startsWith('axisLabel')
        );
        existingAxes.forEach(axis => this.context.scene?.remove(axis));

        // Create axes helper
        const axesHelper = new THREE.AxesHelper(size);
        axesHelper.name = 'axisHelper';
        axesHelper.position.copy(center);
        this.context.scene.add(axesHelper);

        // Add grid helper
        const gridHelper = new THREE.GridHelper(size * 2, 10);
        gridHelper.rotation.x = Math.PI / 2; // Rotate to XZ plane
        gridHelper.position.copy(center);
        gridHelper.name = 'gridHelper';
        this.context.scene.add(gridHelper);
    }

    /**
     * Update viewport dimensions with improved handling for aspect ratio changes
     * @param options Viewport options
     */
    public updateViewport(options: ViewportOptions): void {
        if (!this.context.camera || !this.context.renderer) return;

        const {width, height, pixelRatio} = options;

        // Debug log the original dimensions
        const originalAspect = this.context.camera.aspect;
        const newAspect = width / height;
        console.debug(`Updating viewport: ${width.toFixed(0)}x${height.toFixed(0)}, aspect ratio: ${newAspect.toFixed(4)} (was ${originalAspect.toFixed(4)})`);

        // Update camera aspect ratio
        this.context.camera.aspect = newAspect;
        this.context.camera.updateProjectionMatrix();

        // Update renderer size (false preserves buffer size)
        this.context.renderer.setSize(width, height, false);

        // Ensure canvas size matches container size exactly
        const canvas = this.context.renderer.domElement;
        if (Math.abs(canvas.clientWidth - width) > 1 || Math.abs(canvas.clientHeight - height) > 1) {
            console.debug(`Canvas size mismatch: canvas(${canvas.clientWidth}x${canvas.clientHeight}) container(${width}x${height})`);
            canvas.style.width = `${width}px`;
            canvas.style.height = `${height}px`;
        }

        if (pixelRatio) {
            this.context.renderer.setPixelRatio(pixelRatio);
        }

        // Force an immediate render to apply changes
        if (this.context.scene) {
            this.context.renderer.render(this.context.scene, this.context.camera);
        }
    }

    /**
     * Update raycaster from mouse coordinates
     * @param mouseX Normalized mouse X (-1 to 1)
     * @param mouseY Normalized mouse Y (-1 to 1)
     */
    public updateRaycaster(mouseX: number, mouseY: number): void {
        if (!this.context.raycaster || !this.context.camera) return;

        const mouseVec = new THREE.Vector2(mouseX, mouseY);
        this.context.raycaster.setFromCamera(mouseVec, this.context.camera);
    }

    /**
     * Set raycaster threshold
     * @param threshold The threshold value
     */
    public setRaycasterThreshold(threshold: number): void {
        if (!this.context.raycaster) return;
        this.context.raycaster.params.Points = {threshold};
    }

    /**
     * Perform raycasting on the point cloud
     * @returns Intersection array
     */
    public raycastPointCloud(): THREE.Intersection[] {
        if (!this.context.raycaster || !this.context.pointCloud) {
            return [];
        }

        return this.context.raycaster.intersectObject(this.context.pointCloud, false);
    }

    /**
     * Clean up Three.js resources
     */
    public cleanup(): void {
        this.stopAnimation();
        this.clearMarkerSpheres();

        // Dispose renderer
        if (this.context.renderer) {
            this.context.renderer.dispose();
            this.context.renderer.forceContextLoss();
            const domElement = this.context.renderer.domElement;
            if (domElement && domElement.parentNode) {
                domElement.parentNode.removeChild(domElement);
            }
            this.context.renderer = null;
        }

        // Clean up point cloud
        if (this.context.pointCloud && this.context.scene) {
            this.context.scene.remove(this.context.pointCloud);

            // Dispose of geometry
            if (this.context.pointCloud.geometry) {
                this.context.pointCloud.geometry.dispose();
            }

            // Dispose of material(s)
            if (this.context.pointCloud.material) {
                if (Array.isArray(this.context.pointCloud.material)) {
                    this.context.pointCloud.material.forEach(m => m.dispose());
                } else {
                    this.context.pointCloud.material.dispose();
                }
            }

            // Clear references
            this.context.pointCloud = null;
        }

        // Clear scene with proper resource disposal
        if (this.context.scene) {
            this.disposeSceneResources(this.context.scene);
            this.context.scene = null;
        }

        // Clear other references
        this.context.camera = null;
        this.context.raycaster = null;
        this.context.controls = null;
        this.context.pointGeometry = null;
        this.context.isAnimating = false;
    }

    // New helper method to properly dispose scene resources
    private disposeSceneResources(scene: THREE.Scene): void {
        // Process all scene objects to ensure proper disposal
        scene.traverse((object) => {
            // Remove from parent
            if (object.parent) {
                object.parent.remove(object);
            }

            // Dispose geometry
            if (object instanceof THREE.Mesh || object instanceof THREE.Points) {
                if (object.geometry) {
                    object.geometry.dispose();
                }

                // Dispose material
                if (object.material) {
                    if (Array.isArray(object.material)) {
                        object.material.forEach(material => {
                            this.disposeMaterial(material);
                        });
                    } else {
                        this.disposeMaterial(object.material);
                    }
                }
            }
        });

        // Clear all children
        while (scene.children.length > 0) {
            scene.remove(scene.children[0]);
        }
    }

    // Helper to dispose material and its textures
    private disposeMaterial(material: THREE.Material): void {
        // Helper function for common textures that exist on multiple material types
        const disposeCommonTextures = (mat: THREE.Material & {
            map?: THREE.Texture | null;
            lightMap?: THREE.Texture | null;
            aoMap?: THREE.Texture | null;
            alphaMap?: THREE.Texture | null;
            envMap?: THREE.Texture | null;
        }) => {
            if (mat.map) mat.map.dispose();
            if (mat.lightMap) mat.lightMap.dispose();
            if (mat.aoMap) mat.aoMap.dispose();
            if (mat.alphaMap) mat.alphaMap.dispose();
            if (mat.envMap) mat.envMap.dispose();
        };

        // Handle MeshBasicMaterial
        if (material instanceof THREE.MeshBasicMaterial) {
            disposeCommonTextures(material);
            // BasicMaterial has no additional textures to dispose
        }

        // Handle MeshPhongMaterial
        if (material instanceof THREE.MeshPhongMaterial) {
            disposeCommonTextures(material);
            // Dispose Phong-specific textures
            if (material.emissiveMap) material.emissiveMap.dispose();
            if (material.bumpMap) material.bumpMap.dispose();
            if (material.normalMap) material.normalMap.dispose();
            if (material.displacementMap) material.displacementMap.dispose();
        }

        // Handle MeshStandardMaterial
        if (material instanceof THREE.MeshStandardMaterial) {
            disposeCommonTextures(material);
            // Dispose Standard-specific textures
            if (material.emissiveMap) material.emissiveMap.dispose();
            if (material.bumpMap) material.bumpMap.dispose();
            if (material.normalMap) material.normalMap.dispose();
            if (material.displacementMap) material.displacementMap.dispose();
            if (material.roughnessMap) material.roughnessMap.dispose();
            if (material.metalnessMap) material.metalnessMap.dispose();
        }

        // Handle PointsMaterial
        if (material instanceof THREE.PointsMaterial) {
            disposeCommonTextures(material);
            // PointsMaterial has no additional textures to dispose
        }

        // Dispose the material itself
        material.dispose();
    }

    /**
     * Get the current Three.js context
     * @returns The Three.js context
     */
    public getContext(): ThreeJsContext {
        return this.context;
    }

    /**
     * Explicitly render the scene once
     */
    public renderScene(): void {
        if (!this.context.renderer || !this.context.scene || !this.context.camera) {
            console.warn('Cannot render: missing renderer, scene or camera');
            return;
        }

        try {
            // Store the objects in local variables to avoid proxy issues
            const renderer = this.context.renderer;
            const scene = this.context.scene;
            const camera = this.context.camera;

            // Render one frame
            renderer.render(scene, camera);
        } catch (error) {
            console.error('Error rendering scene:', error);
        }
    }
}

// Export a singleton instance
export const threeJsService = new ThreeJsService();