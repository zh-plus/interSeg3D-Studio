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
<template>
  <v-app>
    <v-app-bar app color="primary">
      <v-app-bar-title>AGILE3D - Interactive Segmentation</v-app-bar-title>
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
                :clickMode="clickMode"
                :cubeSize="cubeSize"
                :currentObjectIdx="currentObjectIdx ?? undefined"
                :interactionMode="interactionMode"
                :objects="objects"
                :plyFile="currentPlyFile"
                :segmentedPointCloud="segmentedPointCloud"
                @error="handleViewerError"
                @redo="handleRedo"
                @undo="handleUndo"
                @point-clicked="handlePointClick"
                @point-cloud-loaded="handlePointCloudLoaded"
                @create-object="handleCreateObjectFromMarker"
                @select-object="selectObject"
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

            <div v-if="isProcessing || isAnalyzing" class="loading-overlay">
              <v-progress-circular
                  color="primary"
                  indeterminate
                  size="64"
              ></v-progress-circular>
              <p class="mt-4">{{
                  isAnalyzing ? 'Analyzing objects...' : processingMessage ? 'Processing: ' + processingMessage : 'Processing...'
                }}</p>
            </div>
          </v-col>

          <!-- Control Panel on the right -->
          <v-col class="pa-4" cols="3">
            <v-card class="mb-4" outlined>
              <v-card-title>File Upload</v-card-title>
              <v-card-text>
                <v-file-input
                    :disabled="isProcessing || operationLock"
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
                <v-chip v-if="currentObjectIdx" class="ml-2" x-small>
                  Current: {{ currentObjectIdx ? objects[currentObjectIdx - 1]?.name || 'Unknown' : 'None' }}
                </v-chip>

                <v-spacer></v-spacer>

                <v-tooltip bottom>
                  <template v-slot:activator="{ on, attrs }">
                    <v-btn
                        :disabled="!segmentedPointCloud || isProcessing || isAnalyzing || operationLock"
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
                    v-model="newObjectName"
                    :disabled="!currentPlyFile"
                    label="New Object Name"
                    @keyup.enter="createNewObject"
                ></v-text-field>
                <v-btn
                    :disabled="!currentPlyFile || !newObjectName || isProcessing || operationLock"
                    block
                    color="primary"
                    @click="createNewObject"
                >
                  Create Object
                </v-btn>

                <v-list v-if="objects.length > 0" class="mt-4 object-list" dense>
                  <v-list-item
                      v-for="(object, i) in objects"
                      :key="i"
                      :class="{'selected-object': selectedObjectIndex === i}"
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
                            @click.stop="showObjectDescription(object)"
                        >
                          <v-icon x-small>mdi-information-outline</v-icon>
                        </v-btn>
                      </v-list-item-title>
                      <v-list-item-subtitle v-if="object.description" class="text-truncate">
                        {{ truncateDescription(object.description, 30) }}
                      </v-list-item-subtitle>
                    </v-list-item-content>
                    <v-list-item-action v-if="selectedObjectIndex === i">
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
                  <v-btn :disabled="!currentObjectIdx" value="object">
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
                    :disabled="!currentPlyFile"
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
                :disabled="!currentPlyFile || totalClicks === 0 || isProcessing || operationLock"
                :loading="isProcessing && !isAnalyzing"
                block
                class="mt-4"
                color="primary"
                x-large
                @click="runSegmentation"
            >
              RUN SEGMENTATION
            </v-btn>

            <v-btn
                :disabled="!segmentedPointCloud || isProcessing || isAnalyzing || operationLock"
                :loading="isAnalyzing"
                block
                class="mt-4"
                color="info"
                @click="analyzeObjects"
            >
              ANALYZE OBJECTS
            </v-btn>

            <v-btn
                :disabled="!segmentedPointCloud || isProcessing || operationLock"
                :loading="isDownloading"
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
    <v-dialog v-model="showInstructions" max-width="600">
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
                <v-list-item-subtitle>Press "Ctrl+Z" to undo the last click</v-list-item-subtitle>
                <v-list-item-subtitle>Press "Shift+Ctrl+Z" to redo an undone click</v-list-item-subtitle>
              </v-list-item-content>
            </v-list-item>
          </v-list>
        </v-card-text>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn color="primary" text @click="showInstructions = false">Close</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Object Description Dialog -->
    <v-dialog v-model="showDescriptionDialog" max-width="600">
      <ObjectDescriptionCard
          :loading="false"
          :object="selectedObjectForDescription"
          :show-actions="true"
          @close="showDescriptionDialog = false"
      />
    </v-dialog>

    <!-- Object Analysis Dialog -->
    <ObjectAnalysisDialog
        v-model="showAnalysisDialog"
        :loading="isAnalyzing"
        :results="analysisResults"
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
import ObjectAnalysisDialog, {AnalysisResult} from './components/viewer/ObjectAnalysisDialog.vue';
import {apiService} from './services/ApiService';
import {getCssColorFromIndex} from './utils/color-utils';
import {SegmentedPointCloud} from '@/types/PointCloud';

interface ObjectData {
  id: number;
  name: string;
  description?: string; // Added field for AI-generated description
}

// References
const pointCloudViewer = ref<InstanceType<typeof PointCloudViewer> | null>(null);

// State variables
const currentPlyFile = ref<File | null>(null);
const segmentedPointCloud = ref<SegmentedPointCloud | null>(null);
const showInstructions = ref(true);
const clickMode = ref<'object' | 'background'>('object');
const objects = ref<Array<ObjectData>>([]);
const selectedObjectIndex = ref<number | null>(null);
const newObjectName = ref('');
const cubeSize = ref(0.02);
const autoInfer = ref(false);
const isProcessing = ref(false);
const processingMessage = ref('');
const isDownloading = ref(false);
const operationLock = ref(false);
const totalClicks = ref(0);
const isAnalyzing = ref(false);
const showDescriptionDialog = ref(false);
const selectedObjectForDescription = ref<ObjectData | null>(null);
const showAnalysisDialog = ref(false);
const analysisResults = ref<AnalysisResult[]>([]);
let autoInferTimer: number | null = null;

// NEW: Add interaction mode toggle (navigate or annotate)
const interactionMode = ref<'navigate' | 'annotate'>('navigate'); // Default to navigation mode

// Computed properties
const currentObjectIdx = computed(() => {
  return selectedObjectIndex.value !== null ? selectedObjectIndex.value + 1 : null;
});

// Improved error handling for API calls
const handleApiError = (error: any, defaultMessage: string): string => {
  console.error(defaultMessage, error);

  let errorMessage = defaultMessage;

  if (error.response) {
    console.error('Server error data:', error.response.data);

    // Extract error message from various possible response formats
    const data = error.response.data;
    if (typeof data === 'object' && data !== null) {
      errorMessage = `Server error ${error.response.status}: ${
          data.detail || data.message || JSON.stringify(data)
      }`;
    } else if (typeof data === 'string') {
      errorMessage = `Server error ${error.response.status}: ${data}`;
    } else {
      errorMessage = `Server error ${error.response.status}`;
    }
  } else if (error.request) {
    errorMessage = 'No response from server. Check your connection.';
  } else if (error.message) {
    errorMessage = `Error: ${error.message}`;
  }

  return errorMessage;
};

// Function to handle object selection
function selectObject(index: number) {
  selectedObjectIndex.value = index;
  clickMode.value = 'object';

  // If we're selecting an object, automatically switch to annotation mode
  interactionMode.value = 'annotate';

  console.log(`Selected object: ${objects.value[index].name} (ID: ${objects.value[index].id})`);
}

// Function to get style for object list items
function getObjectStyleClass(index: number) {
  // Generate a color based on the object index
  const isSelected = selectedObjectIndex.value === index - 1;

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
 * Show full description in dialog
 */
function showObjectDescription(object: ObjectData) {
  selectedObjectForDescription.value = object;
  showDescriptionDialog.value = true;
}

/**
 * Truncate description for display
 */
function truncateDescription(description: string, maxLength: number = 100): string {
  if (!description) return '';
  if (description.length <= maxLength) return description;
  return description.substring(0, maxLength) + '...';
}

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

  // Check file size
  const MAX_SIZE_MB = 50;
  if (file.size > MAX_SIZE_MB * 1024 * 1024) {
    alert(`File too large. Maximum size is ${MAX_SIZE_MB}MB.`);
    return;
  }

  // Prevent concurrent operations
  if (operationLock.value || isProcessing.value) {
    alert('Operation in progress. Please wait.');
    return;
  }

  // Set the file for the PointCloudViewer to load directly
  currentPlyFile.value = file;

  isProcessing.value = true;
  operationLock.value = true;
  processingMessage.value = 'Uploading to server...';

  try {
    // Create FormData
    const formData = new FormData();
    formData.append('file', file);

    // Call API service
    const response = await apiService.uploadPointCloud(file);

    // Reset segmentation state
    segmentedPointCloud.value = null;
    objects.value = [];
    selectedObjectIndex.value = null;
    totalClicks.value = 0;
    analysisResults.value = [];

    processingMessage.value = 'Processing point cloud...';

  } catch (error: any) {
    console.error('Error uploading file:', error);
    alert(`Upload failed: ${error.message}`);
    isProcessing.value = false;
    operationLock.value = false;
  }
}

function handlePointCloudLoaded(data: { pointCount: number }) {
  console.log('Point cloud loaded with', data.pointCount, 'points');
  isProcessing.value = false;
  processingMessage.value = '';
  operationLock.value = false;
}

function createNewObject() {
  if (!newObjectName.value.trim()) return;

  // Prevent operation if locked
  if (operationLock.value || isProcessing.value) return;

  const newObjId = objects.value.length + 1;
  objects.value.push({
    id: newObjId,
    name: newObjectName.value.trim() // Ensure name is trimmed
  });

  selectedObjectIndex.value = objects.value.length - 1;
  newObjectName.value = '';

  // Switch to annotation mode when creating a new object
  interactionMode.value = 'annotate';
}

function handlePointClick(position: number[]) {
  if (operationLock.value || isProcessing.value) {
    return;
  }

  totalClicks.value++;

  // Throttle automatic inference to prevent rapid, repeated API calls
  if (autoInfer.value && !operationLock.value) {
    // Use setTimeout as a simple debounce mechanism
    const DEBOUNCE_MS = 500;
    if (autoInferTimer) clearTimeout(autoInferTimer);

    autoInferTimer = window.setTimeout(() => {
      runSegmentation();
    }, DEBOUNCE_MS);
  }
}

function runSegmentation() {
  if (totalClicks.value === 0) return;

  // Prevent concurrent operations
  if (operationLock.value || isProcessing.value) return;

  operationLock.value = true;
  isProcessing.value = true;
  processingMessage.value = 'Running segmentation';

  // Get click data from PointCloudViewer via the ref
  const clickData = pointCloudViewer.value?.getClickDataForApi() || {
    clickIdx: {'0': []},
    clickTimeIdx: {'0': []},
    clickPositions: {'0': []}
  };

  // Ensure all objects have entries in the click data
  objects.value.forEach((obj, idx) => {
    const objKey = (idx + 1).toString();
    if (!clickData.clickIdx[objKey]) {
      clickData.clickIdx[objKey] = [];
      clickData.clickTimeIdx[objKey] = [];
      clickData.clickPositions[objKey] = [];
    }
  });

  apiService.runInference({
    clickData: clickData,
    cubeSize: cubeSize.value,
    objectNames: objects.value.map(obj => obj.name)
  })
      .then(response => {
        if (!response.data || !response.data.segmentedPointCloud) {
          console.error('Invalid response format:', response.data);
          alert('Invalid response from server. Please try again.');
          return;
        }

        segmentedPointCloud.value = response.data.segmentedPointCloud;
      })
      .catch(error => {
        const errorMessage = handleApiError(error, 'Error running segmentation');
        alert(errorMessage);
      })
      .finally(() => {
        isProcessing.value = false;
        processingMessage.value = '';
        operationLock.value = false;
      });
}

/**
 * Analyze objects using mask object detection
 */
async function analyzeObjects() {
  if (!segmentedPointCloud.value) return;

  // Prevent concurrent operations
  if (operationLock.value || isProcessing.value) return;

  isAnalyzing.value = true;
  operationLock.value = true;
  showAnalysisDialog.value = true;
  analysisResults.value = [];

  try {
    const response = await apiService.runMaskObjectDetection(segmentedPointCloud.value.segmentation);

    if (response.data?.result && response.data.result.length > 0) {
      // Parse results and associate with object IDs if possible
      analysisResults.value = response.data.result.map((item, index) => {
        // Check if the backend provides an explicit object ID
        // If not, we'll try to determine it later
        let objId = null;

        // If the result includes an explicit obj_id field
        if ('obj_id' in item) {
          objId = item.obj_id;
        } else {
          // Try to extract from the label using regex
          const objIdMatch = /(\d+)/.exec(item.label);
          objId = objIdMatch ? parseInt(objIdMatch[0], 10) : null;

          // If still no ID, use index+1 (assuming 1-based IDs)
          if (objId === null) {
            objId = index + 1;
          }
        }

        // Return the result with added objId if found
        return {
          ...item,
          obj_id: objId
        };
      });

      console.log('Analysis results with object IDs:', analysisResults.value);
    } else {
      console.warn('No object analysis results returned');
    }
  } catch (error) {
    const errorMessage = handleApiError(error, 'Error analyzing objects');
    alert(errorMessage);
    showAnalysisDialog.value = false;
  } finally {
    isAnalyzing.value = false;
    operationLock.value = false;
  }
}

/**
 * Apply a single analysis label to an object
 */
function applyAnalysisLabel(data: { label: string, index: number }) {
  const result = analysisResults.value[data.index];

  // We need to determine which object this result corresponds to
  // The results should match the object indices in our segmentation
  // First try to extract object ID directly from the result
  let objId = null;

  // Option 1: The result may include an 'obj_id' property
  if ('obj_id' in result && typeof result.obj_id === 'number') {
    objId = result.obj_id;
  }
  // Option 2: Try to extract an ID from the label using regex
  else {
    const objIdMatch = /(\d+)/.exec(result.label);
    if (objIdMatch) {
      objId = parseInt(objIdMatch[0], 10);
    }

    // If no ID found but we have sequential objects and results
    if (objId === null && data.index < objects.value.length) {
      // Use the index+1 as ID (since object IDs typically start at 1)
      objId = data.index + 1;
    }
  }

  if (objId !== null) {
    // Find the object in our list
    const objIndex = objects.value.findIndex(obj => obj.id === objId);

    if (objIndex !== -1) {
      // Update object with the new information
      objects.value[objIndex].name = result.label;
      objects.value[objIndex].description = result.description;

      console.log(`Updated object ${objId} with label: ${result.label}`);
    } else {
      console.warn(`Cannot find object with ID ${objId} to apply label: ${result.label}`);
    }
  } else {
    console.warn(`Could not determine object ID for result at index ${data.index}`);
  }
}

/**
 * Apply all analysis results at once
 */
function applyAllAnalysisResults() {
  // If there are more results than objects, just apply what we can
  const resultCount = Math.min(analysisResults.value.length, objects.value.length);

  for (let i = 0; i < resultCount; i++) {
    applyAnalysisLabel({label: analysisResults.value[i].label, index: i});
  }

  if (analysisResults.value.length > 0) {
    // Notify the user that objects have been updated
    alert(`Applied ${resultCount} object labels from analysis`);
  }
}

/**
 * View an analyzed object's details
 */
function viewAnalyzedObject(index: number) {
  const result = analysisResults.value[index];

  // Extract object ID from the label
  const objIdMatch = /(\d+)/.exec(result.label);
  const objId = objIdMatch ? parseInt(objIdMatch[0], 10) : null;

  if (objId !== null) {
    // Find the object in our list
    const objIndex = objects.value.findIndex(obj => obj.id === objId);

    if (objIndex !== -1) {
      // Create a temporary object with the analysis results
      // Show the object description dialog
      selectedObjectForDescription.value = {
        id: objId,
        name: result.label,
        description: result.description
      };
      showDescriptionDialog.value = true;
    }
  }
}

function downloadResults() {
  if (!segmentedPointCloud.value) return;

  // Prevent concurrent operations
  if (operationLock.value || isProcessing.value) return;

  isDownloading.value = true;
  operationLock.value = true;

  apiService.downloadResults()
      .then(response => {
        const url = window.URL.createObjectURL(new Blob([response.data]));
        const link = document.createElement('a');
        link.href = url;
        link.setAttribute('download', `segmentation_result_${Date.now()}.ply`);
        document.body.appendChild(link);
        link.click();

        // Cleanup
        setTimeout(() => {
          window.URL.revokeObjectURL(url);
          link.remove();
        }, 100);
      })
      .catch(error => {
        console.error('Error downloading results:', error);
        alert('Error downloading results. Please try again.');
      })
      .finally(() => {
        isDownloading.value = false;
        operationLock.value = false;
      });
}

function toggleInstructions() {
  showInstructions.value = !showInstructions.value;
}

/**
 * Handle create object request from marker interaction
 */
function handleCreateObjectFromMarker(objectName: string) {
  if (!objectName.trim()) return;

  // Prevent operation if locked
  if (operationLock.value || isProcessing.value) return;

  const newObjId = objects.value.length + 1;
  objects.value.push({
    id: newObjId,
    name: objectName.trim()
  });

  selectedObjectIndex.value = objects.value.length - 1;

  // Automatically switch to object mode with the new object
  clickMode.value = 'object';

  // Also switch to annotation mode
  interactionMode.value = 'annotate';

  return newObjId; // Return the new object ID
}

function handleViewerError(errorMessage: string) {
  console.error('PointCloudViewer error:', errorMessage);
  alert(errorMessage);
  isProcessing.value = false;
  processingMessage.value = '';
  operationLock.value = false;
}

/**
 * Handle keyboard shortcuts
 */
function handleKeydown(e: KeyboardEvent) {
  // 'A' key to toggle between annotation and navigation modes
  if (e.key === 'a' || e.key === 'A') {
    interactionMode.value = interactionMode.value === 'navigate' ? 'annotate' : 'navigate';
    console.log(`Switched to ${interactionMode.value} mode`);
  }
}

/**
 * Handle undo event from the viewer
 */
function handleUndo(undoneAction: any) {
  console.log('Undid action:', undoneAction);
  totalClicks.value = Math.max(0, totalClicks.value - 1);
}

/**
 * Handle redo event from the viewer
 */
function handleRedo(redoneAction: any) {
  console.log('Redid action:', redoneAction);
  totalClicks.value++;
}

// Set up keyboard event listener
onMounted(() => {
  // Only add event listener for the 'A' key toggle
  // Let PointCloudViewer handle Ctrl+Z / Shift+Ctrl+Z
  window.addEventListener('keydown', handleKeydown);
});

// Clean up when unmounting
onBeforeUnmount(() => {
  if (autoInferTimer) {
    clearTimeout(autoInferTimer);
  }

  window.removeEventListener('keydown', handleKeydown);
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

/* Object description styling */
.object-description-content {
  white-space: pre-line;
  line-height: 1.5;
  max-height: 60vh;
  overflow-y: auto;
  padding: 10px;
  background-color: #f5f5f5;
  border-radius: 4px;
}
</style>