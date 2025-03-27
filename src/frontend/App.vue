<template>
  <v-app>
    <v-app-bar app color="primary">
      <v-app-bar-title>interSeg3D-Studio - Interactive 3D Segmentation Studio</v-app-bar-title>
      <v-spacer></v-spacer>
      <v-btn icon @click="toggleInstructions">
        <v-icon>mdi-help-circle-outline</v-icon>
      </v-btn>
    </v-app-bar>

    <v-main>
      <v-container class="fill-height pa-0" fluid>
        <v-row class="fill-height" no-gutters>
          <!-- 3D Viewer takes up most of the space -->
          <v-col class="position-relative" cols="9">
            <PointCloudViewer
                ref="pointCloudViewer"
                @error="handleViewerError"
                @point-cloud-loaded="handlePointCloudLoaded"
                @create-object="handleCreateObjectFromMarker"
            />

            <!-- Floating interaction mode toggle -->
            <div class="interaction-toggle">
              <v-btn-toggle v-model="interactionMode" dense mandatory>
                <v-btn small value="navigate">
                  <v-icon small>mdi-rotate-3d</v-icon>
                  Navigate
                </v-btn>
                <v-btn small value="annotate">
                  <v-icon small>mdi-cursor-default-click</v-icon>
                  Annotate
                </v-btn>
              </v-btn-toggle>
            </div>

            <div v-if="apiStore.isProcessing || apiStore.isAnalyzing" class="loading-overlay">
              <v-progress-circular
                  color="primary"
                  indeterminate
                  size="64"
              ></v-progress-circular>
              <p class="mt-4">{{
                  apiStore.isAnalyzing ? 'Analyzing objects...' : apiStore.processingMessage ? 'Processing: ' + apiStore.processingMessage : 'Processing...'
                }}</p>
            </div>
          </v-col>

          <!-- Control Panel on the right -->
          <v-col class="pa-4" cols="3">
            <v-card class="mb-4" outlined>
              <v-card-title>File Upload</v-card-title>
              <v-card-text>
                <v-file-input
                    :disabled="apiStore.isProcessing || apiStore.operationLock"
                    accept=".ply"
                    label="Upload Point Cloud (.ply)"
                    prepend-icon="mdi-cloud-upload"
                    @change="handleFileUpload"
                ></v-file-input>
              </v-card-text>
            </v-card>

            <v-card class="mb-4" outlined>
              <v-card-title class="d-flex align-center">
                Objects
                <v-chip v-if="uiStore.currentObjectIdx" class="ml-2" x-small>
                  Current: {{
                    uiStore.currentObjectIdx ? uiStore.objects[uiStore.currentObjectIdx - 1]?.name || 'Unknown' : 'None'
                  }}
                </v-chip>

                <v-spacer></v-spacer>

                <v-tooltip bottom>
                  <template v-slot:activator="{ on, attrs }">
                    <v-btn
                        :disabled="!pointCloudStore.segmentedPointCloud || apiStore.isProcessing || apiStore.isAnalyzing || apiStore.operationLock"
                        color="info"
                        icon
                        v-bind="attrs"
                        x-small
                        @click="analyzeObjects"
                        v-on="on"
                    >
                      <v-icon small>mdi-brain</v-icon>
                    </v-btn>
                  </template>
                  <span>Analyze Objects</span>
                </v-tooltip>
              </v-card-title>
              <v-card-text>
                <v-text-field
                    v-model="uiStore.newObjectName"
                    :disabled="!pointCloudStore.pointCloudData.file"
                    label="New Object Name"
                    @keyup.enter="createNewObject"
                ></v-text-field>
                <v-btn
                    :disabled="!pointCloudStore.pointCloudData.file || !uiStore.newObjectName || apiStore.isProcessing || apiStore.operationLock"
                    block
                    color="primary"
                    @click="createNewObject"
                >
                  Create Object
                </v-btn>

                <v-list v-if="uiStore.objects.length > 0" class="mt-4 object-list" dense>
                  <v-list-item
                      v-for="(object, i) in uiStore.objects"
                      :key="i"
                      :class="{'selected-object': uiStore.selectedObjectIndex === i}"
                      :style="getObjectStyleClass(i+1)"
                      class="object-list-item"
                      @click="selectObject(i)"
                  >
                    <v-list-item-content>
                      <v-list-item-title class="d-flex align-center justify-space-between">
                        <span class="object-name">{{ object.name }}</span>
                        <v-btn
                            v-if="object.description"
                            class="info-button"
                            icon
                            title="Show description"
                            x-small
                            @click.stop="uiStore.showObjectDescription(object)"
                        >
                          <v-icon x-small>mdi-information-outline</v-icon>
                        </v-btn>
                      </v-list-item-title>
                      <v-list-item-subtitle v-if="object.description" class="text-truncate">
                        {{ truncateDescription(object.description, 30) }}
                      </v-list-item-subtitle>
                    </v-list-item-content>
                    <v-list-item-action v-if="uiStore.selectedObjectIndex === i">
                      <v-icon color="white">mdi-check</v-icon>
                    </v-list-item-action>
                  </v-list-item>
                </v-list>
              </v-card-text>
            </v-card>

            <v-card class="mb-4" outlined>
              <v-card-title>Annotation Mode</v-card-title>
              <v-card-text>
                <v-btn-toggle v-model="clickMode" mandatory>
                  <v-btn :disabled="!uiStore.currentObjectIdx" value="object">
                    <v-icon>mdi-shape</v-icon>
                    Object
                  </v-btn>
                  <v-btn value="background">
                    <v-icon>mdi-eraser</v-icon>
                    Background
                  </v-btn>
                </v-btn-toggle>

                <v-slider
                    v-model="cubeSize"
                    :disabled="!pointCloudStore.pointCloudData.file"
                    label="Selection Size"
                    max="0.1"
                    min="0.005"
                    step="0.005"
                    thumb-label
                ></v-slider>

                <v-switch
                    v-model="autoInfer"
                    label="Auto-infer on click"
                ></v-switch>
              </v-card-text>
            </v-card>

            <v-btn
                :disabled="!pointCloudStore.pointCloudData.file || !apiStore.hasClickData || apiStore.isProcessing || apiStore.operationLock"
                :loading="apiStore.isProcessing && !apiStore.isAnalyzing"
                block
                class="mt-4"
                color="primary"
                x-large
                @click="runSegmentation"
            >
              RUN SEGMENTATION
            </v-btn>

            <v-btn
                :disabled="!pointCloudStore.segmentedPointCloud || apiStore.isProcessing || apiStore.isAnalyzing || apiStore.operationLock"
                :loading="apiStore.isAnalyzing"
                block
                class="mt-4"
                color="info"
                @click="analyzeObjects"
            >
              ANALYZE OBJECTS
            </v-btn>

            <v-btn
                :disabled="!pointCloudStore.segmentedPointCloud || apiStore.isProcessing || apiStore.operationLock"
                :loading="apiStore.isDownloading"
                block
                class="mt-4"
                color="success"
                @click="downloadResults"
            >
              SAVE RESULTS
            </v-btn>
          </v-col>
        </v-row>
      </v-container>
    </v-main>

    <!-- Instructions Dialog -->
    <v-dialog v-model="uiStore.showInstructions" max-width="600">
      <v-card>
        <v-card-title>Instructions</v-card-title>
        <v-card-text>
          <v-list dense>
            <v-list-item>
              <v-list-item-icon>
                <v-icon color="blue">mdi-rotate-3d</v-icon>
              </v-list-item-icon>
              <v-list-item-content>
                <v-list-item-title>Navigation Mode</v-list-item-title>
                <v-list-item-subtitle>Select "Navigate" to rotate, pan, and zoom the view. Left-click + drag to rotate,
                  right-click + drag to pan, scroll to zoom.
                </v-list-item-subtitle>
              </v-list-item-content>
            </v-list-item>

            <v-list-item>
              <v-list-item-icon>
                <v-icon color="orange">mdi-cursor-default-click</v-icon>
              </v-list-item-icon>
              <v-list-item-content>
                <v-list-item-title>Annotation Mode</v-list-item-title>
                <v-list-item-subtitle>Select "Annotate" to start marking points. Click on points to mark them as objects
                  or background.
                </v-list-item-subtitle>
              </v-list-item-content>
            </v-list-item>

            <v-list-item>
              <v-list-item-icon>
                <v-icon color="blue">mdi-shape</v-icon>
              </v-list-item-icon>
              <v-list-item-content>
                <v-list-item-title>Object Selection</v-list-item-title>
                <v-list-item-subtitle>Click on an object from the list and then click on the point cloud to mark points
                  for that object
                </v-list-item-subtitle>
              </v-list-item-content>
            </v-list-item>

            <v-list-item>
              <v-list-item-icon>
                <v-icon color="red">mdi-eraser</v-icon>
              </v-list-item-icon>
              <v-list-item-content>
                <v-list-item-title>Background Selection</v-list-item-title>
                <v-list-item-subtitle>Switch to background mode and click on non-object areas</v-list-item-subtitle>
              </v-list-item-content>
            </v-list-item>

            <v-divider class="my-3"></v-divider>

            <v-list-item>
              <v-list-item-icon>
                <v-icon color="purple">mdi-brain</v-icon>
              </v-list-item-icon>
              <v-list-item-content>
                <v-list-item-title>Object Analysis</v-list-item-title>
                <v-list-item-subtitle>After segmentation, click "Analyze Objects" to use AI to identify and describe the
                  objects in your scene.
                </v-list-item-subtitle>
              </v-list-item-content>
            </v-list-item>

            <v-divider class="my-3"></v-divider>

            <v-list-item>
              <v-list-item-icon>
                <v-icon>mdi-keyboard-outline</v-icon>
              </v-list-item-icon>
              <v-list-item-content>
                <v-list-item-title>Keyboard Shortcuts</v-list-item-title>
                <v-list-item-subtitle>Press "A" to toggle between navigation and annotation modes</v-list-item-subtitle>
                <v-list-item-subtitle>Press "N" to create a new object with default name "new obj"
                </v-list-item-subtitle>
                <v-list-item-subtitle>Press "Ctrl+Z" to undo the last click</v-list-item-subtitle>
                <v-list-item-subtitle>Press "Shift+Ctrl+Z" to redo an undone click</v-list-item-subtitle>
              </v-list-item-content>
            </v-list-item>
          </v-list>
        </v-card-text>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn color="primary" text @click="uiStore.showInstructions = false">Close</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Object Description Dialog -->
    <v-dialog v-model="uiStore.showDescriptionDialog" max-width="600">
      <ObjectDescriptionCard
          :loading="false"
          :object="uiStore.selectedObjectForDescription"
          :show-actions="true"
          @close="uiStore.showDescriptionDialog = false"
      />
    </v-dialog>

    <!-- Object Analysis Dialog -->
    <ObjectAnalysisDialog
        v-model="uiStore.showAnalysisDialog"
        :loading="apiStore.isAnalyzing"
        :results="apiStore.analysisResults"
        @apply-label="applyAnalysisLabel"
        @apply-all="applyAllAnalysisResults"
        @view-object="viewAnalyzedObject"
    />

    <!-- Debug Panel -->
    <DebugPanel/>
  </v-app>
</template>

<script lang="ts" setup>
import {computed, onBeforeUnmount, onMounted, ref} from 'vue';
import PointCloudViewer from './components/viewer/PointCloudViewer.vue';
import DebugPanel from './components/DebugPanel.vue';
import ObjectDescriptionCard from './components/viewer/ObjectDescriptionCard.vue';
import ObjectAnalysisDialog from './components/viewer/ObjectAnalysisDialog.vue';
import {getCssColorFromIndex} from './utils/color.util';

// Import Pinia stores
import {useAnnotationStore, useApiStore, usePointCloudStore, useUiStore} from './stores';

// Store instances
const pointCloudStore = usePointCloudStore();
const annotationStore = useAnnotationStore();
const uiStore = useUiStore();
const apiStore = useApiStore();

// References
const pointCloudViewer = ref<InstanceType<typeof PointCloudViewer> | null>(null);

// Auto-infer timer
let autoInferTimer: number | null = null;

// Computed property for interaction mode with getter/setter
const interactionMode = computed({
  get: () => uiStore.interactionMode,
  set: (value) => {
    uiStore.setInteractionMode(value);
    console.log(`App.vue: Set interaction mode to ${value}`);
  }
});

// Computed property for click mode
const clickMode = computed({
  get: () => uiStore.clickMode,
  set: (value) => {
    uiStore.setClickMode(value);
    console.log(`App.vue: Set click mode to ${value}`);
  }
});

// Computed property for cube size
const cubeSize = computed({
  get: () => uiStore.cubeSize,
  set: (value) => {
    uiStore.cubeSize = value;
  }
});

// Computed property for auto-infer
const autoInfer = computed({
  get: () => uiStore.autoInfer,
  set: (value) => {
    uiStore.autoInfer = value;
  }
});

/**
 * Function to get style for object list items
 */
function getObjectStyleClass(index: number) {
  // Generate a color based on the object index
  const isSelected = uiStore.selectedObjectIndex === index - 1;

  // If selected, make background color more intense
  const saturation = isSelected ? '100%' : '80%';
  const lightness = isSelected ? '40%' : '70%';

  return {
    backgroundColor: getCssColorFromIndex(index, parseInt(saturation), parseInt(lightness)),
    color: isSelected ? 'white' : 'black',
    cursor: 'pointer',
    fontWeight: isSelected ? 'bold' : 'normal',
  };
}

/**
 * Truncate description for display
 */
function truncateDescription(description: string, maxLength: number = 100): string {
  if (!description) return '';
  if (description.length <= maxLength) return description;
  return description.substring(0, maxLength) + '...';
}

/**
 * Handle file upload
 */
async function handleFileUpload(fileEvent: Event | File) {
  let file: File | null = null;

  // Check if the input is an event or a direct file
  if (fileEvent instanceof Event) {
    const input = fileEvent.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      file = input.files[0];
    }
  } else if (fileEvent instanceof File) {
    file = fileEvent;
  }

  if (!file) {
    console.error('No file selected');
    return;
  }

  // Validate file type more carefully
  if (!file.name.toLowerCase().endsWith('.ply')) {
    alert('Please upload a PLY file (.ply extension)');
    return;
  }

  try {
    // Upload to server via API store
    await apiStore.uploadPointCloud(file);

    // Load the file in the point cloud viewer
    await pointCloudStore.loadPointCloud(file);

    // Center camera on the loaded point cloud
    pointCloudStore.centerCamera();

  } catch (error: any) {
    alert(`Upload failed: ${error.message}`);
  }
}

/**
 * Handle point cloud loaded event
 */
function handlePointCloudLoaded() {
  console.log('Point cloud loaded with', pointCloudStore.pointCloudData.pointCount, 'points');
}

/**
 * Create a new object
 */
function createNewObject() {
  if (!uiStore.newObjectName.trim()) return;

  // Create new object via UI store
  uiStore.createNewObject(uiStore.newObjectName);
  uiStore.newObjectName = '';
}

/**
 * Select an object
 */
function selectObject(index: number) {
  uiStore.selectObject(index);
}

/**
 * Run segmentation
 */
async function runSegmentation() {
  try {
    await apiStore.runSegmentation();
  } catch (error: any) {
    alert(error.message);
  }
}

/**
 * Analyze objects
 */
async function analyzeObjects() {
  try {
    await apiStore.analyzeObjects();
  } catch (error: any) {
    alert(error.message);
  }
}

/**
 * Download results
 */
async function downloadResults() {
  try {
    await apiStore.downloadResults();
  } catch (error: any) {
    alert(error.message);
  }
}

/**
 * Toggle instructions dialog
 */
function toggleInstructions() {
  uiStore.showInstructions = !uiStore.showInstructions;
}

/**
 * Handle create object from marker
 */
function handleCreateObjectFromMarker(objectName: string) {
  if (!objectName.trim()) return;

  // Create new object via UI store
  const newObj = uiStore.createNewObject(objectName);

  return newObj?.id; // Return the new object ID
}

/**
 * Handle viewer error
 */
function handleViewerError(errorMessage: string) {
  console.error('PointCloudViewer error:', errorMessage);
  alert(errorMessage);
}

/**
 * Apply analysis label to an object
 */
function applyAnalysisLabel(data: { label: string, index: number }) {
  apiStore.applyAnalysisLabel(data);
}

/**
 * Apply all analysis results
 */
function applyAllAnalysisResults() {
  const appliedCount = apiStore.applyAllAnalysisResults();

  if (appliedCount > 0) {
    // Notify the user that objects have been updated
    alert(`Applied ${appliedCount} object labels from analysis`);
  }
}

/**
 * View analyzed object details
 */
function viewAnalyzedObject(index: number) {
  const result = apiStore.analysisResults[index];

  // Extract object ID from the label
  const objIdMatch = /(\d+)/.exec(result.label);
  const objId = objIdMatch ? parseInt(objIdMatch[0], 10) : null;

  if (objId !== null) {
    // Find the object in our list
    const objIndex = uiStore.objects.findIndex(obj => obj.id === objId);

    if (objIndex !== -1) {
      // Show the object description dialog
      uiStore.selectedObjectForDescription = {
        id: objId,
        name: result.label,
        description: result.description
      };
      uiStore.showDescriptionDialog = true;
    }
  }
}

// Handle keyboard shortcuts
function handleKeydown(e: KeyboardEvent) {
  // Prevent handling if any input elements are focused
  if (e.target instanceof HTMLInputElement ||
      e.target instanceof HTMLTextAreaElement ||
      e.target instanceof HTMLSelectElement) {
    return;
  }

  // 'A' key to toggle between annotation and navigation modes
  if (e.key === 'a' || e.key === 'A') {
    uiStore.toggleInteractionMode();
    console.log(`App.vue: Keyboard shortcut - Switched to ${uiStore.interactionMode} mode`);
  }

  // 'N' key to create a new object with default name
  if (e.key === 'n' || e.key === 'N') {
    uiStore.createNewObject("new obj");
    console.log(`App.vue: Keyboard shortcut - Created new object with default name`);
  }
}

// Set up keyboard event listeners
onMounted(() => {
  // Add global keyboard event listener
  window.addEventListener('keydown', handleKeydown);
  console.log('App.vue: Mounted and keyboard listeners added');
});

// Clean up when unmounting
onBeforeUnmount(() => {
  if (autoInferTimer) {
    clearTimeout(autoInferTimer);
  }

  // Remove keyboard event listener
  window.removeEventListener('keydown', handleKeydown);
  console.log('App.vue: Unmounted and listeners removed');
});
</script>

<style scoped>
.position-relative {
  position: relative;
}

.loading-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.7);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  z-index: 100;
  color: white;
}

/* Object list styling */
.object-list {
  max-height: 300px;
  overflow-y: auto;
  border: 1px solid rgba(0, 0, 0, 0.12);
  border-radius: 4px;
}

.object-list-item {
  border-bottom: 1px solid rgba(0, 0, 0, 0.1);
  transition: all 0.2s ease;
  min-height: auto !important;
  padding: 8px 16px !important;
}

.object-list-item:hover {
  filter: brightness(1.1);
}

.selected-object {
  box-shadow: 0 0 0 2px white inset;
}

/* Interaction mode toggle */
.interaction-toggle {
  position: absolute;
  top: 10px;
  right: 10px;
  z-index: 50;
  background-color: rgba(0, 0, 0, 0.6);
  border-radius: 4px;
  padding: 5px;
}

.object-name {
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  display: inline-block;
}

.info-button {
  margin-left: auto;
  opacity: 0.7;
  transition: opacity 0.2s ease;
}

.info-button:hover {
  opacity: 1;
}
</style>