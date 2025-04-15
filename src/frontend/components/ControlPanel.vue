<template>
  <div class="control-panel-container">
    <!-- File Upload Section -->
    <v-card class="mb-4 control-card" outlined>
      <v-card-title>File Upload</v-card-title>
      <v-card-text>
        <v-file-input
            :disabled="apiStore.isProcessing || apiStore.operationLock"
            accept=".ply"
            label="Upload Point Cloud (.ply)"
            prepend-icon="mdi-cloud-upload"
            @change="handleFileUpload"
        ></v-file-input>

        <v-file-input
            :disabled="!pointCloudStore.hasPointCloud || apiStore.isProcessing || apiStore.operationLock"
            accept=".json"
            label="Load Metadata (.json)"
            prepend-icon="mdi-file-document-outline"
            @change="handleMetadataLoad"
        ></v-file-input>
      </v-card-text>
    </v-card>

    <!-- Objects Section -->
    <v-card class="mb-4" outlined>
      <v-card-title class="d-flex align-center">
        Objects
        <v-chip v-if="uiStore.currentObjectIdx" class="ml-2" x-small>
          Current: {{
            uiStore.currentObjectIdx ? uiStore.objects[uiStore.currentObjectIdx - 1]?.name || 'Unknown' : 'None'
          }}
        </v-chip>

        <!-- Add SaveStatusIndicator -->
        <SaveStatusIndicator
            :status="saveStatus"
            :last-saved="uiStore.lastSaveTime"
        />

        <v-spacer></v-spacer>

        <v-tooltip bottom>
          <template v-slot:activator="{ on, attrs }">
            <v-btn
                :disabled="!uiStore.hasUnsavedChanges || apiStore.isProcessing || apiStore.operationLock"
                color="primary"
                icon
                v-bind="attrs"
                x-small
                @click="updateObjectInfo"
                v-on="on"
            >
              <v-icon small>mdi-content-save</v-icon>
            </v-btn>
          </template>
          <span>Save Object Information (Ctrl+S)</span>
        </v-tooltip>

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

    <!-- Annotation Mode Section -->
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

    <!-- Action Buttons -->
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
  </div>
</template>

<script lang="ts" setup>
import {computed} from 'vue';
import SaveStatusIndicator from '@/components/viewer/SaveStatusIndicator.vue';
import {getCssColorFromIndex} from '@/utils/color.util';
import {useAnnotationStore, useApiStore, usePointCloudStore, useUiStore} from '@/stores';

// Store instances
const pointCloudStore = usePointCloudStore();
const annotationStore = useAnnotationStore();
const uiStore = useUiStore();
const apiStore = useApiStore();

// Emits
const emit = defineEmits([
  'file-uploaded',
  'metadata-loaded',
  'object-created',
  'segmentation-run',
  'objects-analyzed',
  'results-downloaded'
]);

// Computed property for click mode
const clickMode = computed({
  get: () => uiStore.clickMode,
  set: (value) => {
    uiStore.setClickMode(value);
    console.log(`ControlPanel: Set click mode to ${value}`);
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

// Computed property for save status
const saveStatus = computed((): 'unsaved' | 'saving' | 'saved' => {
  if (uiStore.isSaving) {
    return 'saving';
  } else if (uiStore.hasUnsavedChanges) {
    return 'unsaved';
  } else {
    return 'saved';
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

    // Emit event to parent
    emit('file-uploaded', file);

  } catch (error: any) {
    alert(`Upload failed: ${error.message}`);
  }
}

/**
 * Handle metadata file loading
 */
async function handleMetadataLoad(fileEvent: Event | File) {
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

  try {
    // Read the file contents
    const fileContent = await file.text();
    const metadata = JSON.parse(fileContent);

    // Check if the file has the expected structure
    if (!metadata.objects || !Array.isArray(metadata.objects)) {
      alert('Invalid metadata file format: missing objects array');
      return;
    }

    // Clear existing objects and clicks
    uiStore.reset();
    annotationStore.reset();

    // Create objects from metadata
    for (const objData of metadata.objects) {
      if (typeof objData.id !== 'number' || !objData.label) {
        console.warn('Skipping invalid object entry:', objData);
        continue;
      }

      const newObj = uiStore.createNewObject(objData.label);
      if (newObj && objData.description) {
        uiStore.updateObjectInfo(newObj.id, {description: objData.description});
      }
    }

    // Create clicks from metadata if available
    if (metadata.click_data && Array.isArray(metadata.click_data)) {
      for (const clickData of metadata.click_data) {
        // Check if click has required fields
        if (!clickData.position || typeof clickData.obj_idx !== 'number') {
          console.warn('Skipping invalid click entry:', clickData);
          continue;
        }

        const position = clickData.position;
        const objectIdx = clickData.obj_idx;

        // Add click point
        const clickPoint = annotationStore.addClickPoint(
            position,
            objectIdx,
            clickData.id // Use id if available
        );

        // Create marker for this click
        const markerId = annotationStore.createMarkerForClick(
            position,
            objectIdx,
            clickData.time_idx || clickPoint.timeIdx || 0
        );

        // Apply selection if it's an object (not background)
        if (objectIdx !== 0) {
          annotationStore.applySelection(position, objectIdx);
        }
      }
    }

    alert('Metadata loaded successfully!');
    emit('metadata-loaded', metadata);
  } catch (error: any) {
    alert(`Error loading metadata: ${error.message}`);
    console.error('Error loading metadata:', error);
  }
}

/**
 * Create a new object
 */
function createNewObject() {
  if (!uiStore.newObjectName.trim()) return;

  // Create new object via UI store
  const newObject = uiStore.createNewObject(uiStore.newObjectName);
  uiStore.newObjectName = '';

  emit('object-created', newObject);
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
    emit('segmentation-run');
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
    emit('objects-analyzed');
  } catch (error: any) {
    alert(error.message);
  }
}

/**
 * Update object information on the server
 */
async function updateObjectInfo() {
  if (uiStore.objects.length === 0 || !uiStore.hasUnsavedChanges) {
    console.log('No objects to update or no changes');
    return;
  }

  try {
    // The startSaving and finishSaving calls are now handled in the apiStore
    await apiStore.updateObjects();
    // No need for alert - the status indicator will show success
  } catch (error: any) {
    // Only show alert for errors
    alert(`Failed to update object information: ${error.message}`);
  }
}

/**
 * Download results
 */
async function downloadResults() {
  try {
    // Note: apiStore.downloadResults now automatically calls updateObjects first
    await apiStore.downloadResults();
    emit('results-downloaded');
  } catch (error: any) {
    alert(error.message);
  }
}
</script>

<style scoped>
.control-panel-container {
  width: 100%;
  height: 100%;
  padding: 16px;
  overflow-y: auto;
}

.control-card {
  width: 100%;
  max-width: 100%;
  margin-bottom: 16px;
}

/* Add these styles to ensure the panel takes full width */
:deep(.v-card) {
  width: 100% !important;
  max-width: 100% !important;
}

:deep(.v-list) {
  width: 100% !important;
}

.object-list {
  max-height: 300px;
  overflow-y: auto;
  border: 1px solid rgba(0, 0, 0, 0.12);
  border-radius: 4px;
  width: 100%;
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