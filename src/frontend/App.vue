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
                <v-btn small value="navigate" :color="interactionMode === 'navigate' ? 'primary' : undefined"
                       title="Navigate Mode (Rotate/Pan/Zoom)">
                  <v-icon small>mdi-rotate-3d</v-icon>
                  Navigate
                </v-btn>
                <v-btn small value="annotate" :color="interactionMode === 'annotate' ? 'warning' : undefined"
                       title="Annotate Mode (Add Points)">
                  <v-icon small>mdi-cursor-default-click</v-icon>
                  Annotate
                </v-btn>
                <v-btn small value="select" :color="interactionMode === 'select' ? 'purple' : undefined"
                       title="Select Mode (Edit Objects)">
                  <v-icon small>mdi-cursor-pointer</v-icon>
                  Select
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

              <!-- Add this progress indicator -->
              <v-progress-linear
                  v-if="apiStore.processingProgress !== null"
                  class="mt-2"
                  color="primary"
                  height="20"
                  :value="apiStore.processingProgress"
              >
                {{ apiStore.processingProgress }}%
              </v-progress-linear>
            </div>
          </v-col>

          <!-- Control Panel Component -->
          <ControlPanel
              @file-uploaded="handleFileUploaded"
              @metadata-loaded="handleMetadataLoaded"
              @object-created="handleObjectCreated"
              @segmentation-run="handleSegmentationRun"
              @objects-analyzed="handleObjectsAnalyzed"
              @results-downloaded="handleResultsDownloaded"
          />
        </v-row>
      </v-container>
    </v-main>

    <!-- Use the extracted InstructionsDialog component -->
    <InstructionsDialog v-model="uiStore.showInstructions"/>

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
  </v-app>
</template>

<script lang="ts" setup>
import {computed, onBeforeUnmount, onMounted, ref} from 'vue';
import PointCloudViewer from '@/components/viewer/PointCloudViewer.vue';
import ObjectDescriptionCard from '@/components/viewer/ObjectDescriptionCard.vue';
import ObjectAnalysisDialog from '@/components/viewer/ObjectAnalysisDialog.vue';
import InstructionsDialog from '@/components/InstructionsDialog.vue';
import ControlPanel from '@/components/ControlPanel.vue';

// Import Pinia stores
import {useAnnotationStore, useApiStore, usePointCloudStore, useUiStore} from '@/stores';

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

/**
 * Handle point cloud loaded event
 */
function handlePointCloudLoaded() {
  console.log('Point cloud loaded with', pointCloudStore.pointCloudData.pointCount, 'points');
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

// Event handlers for ControlPanel events
function handleFileUploaded(file: File) {
  console.log('File uploaded:', file.name);
}

function handleMetadataLoaded(metadata: any) {
  console.log('Metadata loaded with', metadata.objects.length, 'objects');
}

function handleObjectCreated(object: any) {
  console.log('New object created:', object?.name);
}

function handleSegmentationRun() {
  console.log('Segmentation completed successfully');
}

function handleObjectsAnalyzed() {
  console.log('Object analysis completed');
}

function handleResultsDownloaded() {
  console.log('Results downloaded successfully');
}

// Handle keyboard shortcuts - MODIFIED to address "A" key issue and add Ctrl+S
function handleKeydown(e: KeyboardEvent) {
  if (e.repeat) return;

  // Prevent handling if any input elements are focused
  if (e.target instanceof HTMLInputElement ||
      e.target instanceof HTMLTextAreaElement ||
      e.target instanceof HTMLSelectElement) {
    return;
  }

  // 'N' key to create a new object with default name
  if (e.key === 'n' || e.key === 'N') {
    e.preventDefault();
    uiStore.createNewObject("new obj");
    console.log(`App.vue: Keyboard shortcut - Created new object with default name`);
  }

  // Ctrl+S to update objects on the server
  if (e.ctrlKey && (e.key === 's' || e.key === 'S')) {
    e.preventDefault(); // Prevent browser save dialog
    apiStore.updateObjects();
  }

  // We're removing the "A" key handling from here since it's handled in PointCloudViewer.vue
  // The "A" key toggle is now exclusively handled in PointCloudViewer.vue
}

// Set up keyboard event listeners
onMounted(() => {
  // Add global keyboard event listener - but don't handle the "A" key here
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
  padding: 2rem;
}

.v-progress-linear {
  width: 300px;
  border-radius: 4px;
  overflow: hidden;
}
</style>