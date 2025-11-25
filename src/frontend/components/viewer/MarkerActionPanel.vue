<template>
  <div v-if="selectedMarker" class="marker-action-panel">
    <div class="panel-header">
      <h3>Marker Edit</h3>
      <v-btn icon x-small @click="$emit('close')">
        <v-icon>mdi-close</v-icon>
      </v-btn>
    </div>

    <div class="panel-content">
      <div class="marker-info">
        <div class="marker-position">
          <strong>Position:</strong> {{ formatPosition(selectedMarker.position) }}
        </div>
        <div class="marker-label">
          <strong>Current Label:</strong>
          <span :style="{ color: getLabelColor(selectedMarker.objectIdx) }">
            {{ getLabelName(selectedMarker.objectIdx) }}
          </span>
        </div>
      </div>

      <div class="marker-actions">
        <h4>Change Label</h4>

        <!-- Existing Labels -->
        <div class="existing-labels">
          <v-chip-group
              v-model="selectedLabelIndex"
              active-class="primary--text"
              column
              multiple
          >
            <v-chip
                v-for="(object, i) in objects"
                :key="i"
                :color="getCssColorFromIndex(object.id, 80, 90)"
                :value="i"
                label
                small
                @click="selectLabel(object.id)"
            >
              {{ object.name }}
            </v-chip>

            <v-chip
                color="grey darken-2"
                label
                small
                value="background"
                @click="selectLabel(0)"
            >
              Background
            </v-chip>
          </v-chip-group>
        </div>

        <!-- New Label Option -->
        <v-checkbox
            v-model="showNewLabelInput"
            class="mt-2"
            dense
            hide-details
            label="Create New Label"
        ></v-checkbox>

        <div v-if="showNewLabelInput" class="new-label-input mt-2">
          <v-text-field
              v-model="newLabelName"
              dense
              hide-details
              label="New Label Name"
              @keyup.enter="createNewLabel"
          ></v-text-field>
          <v-btn
              :disabled="!newLabelName"
              class="mt-2"
              color="primary"
              small
              @click="createNewLabel"
          >
            Create & Apply
          </v-btn>
        </div>

        <!-- Action Buttons -->
        <div class="action-buttons mt-4">
          <v-btn
              block
              color="error"
              @click="$emit('delete-marker', selectedMarker.id)"
          >
            Delete Marker
          </v-btn>
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts" setup>
import {PropType, ref, watch} from 'vue';
import {AnnotationMarker} from '@frontend/types/annotation.types';
import {getCssColorFromIndex} from '@frontend/utils/color.util';
import * as THREE from 'three';

// Props
const props = defineProps({
  selectedMarker: {
    type: Object as PropType<AnnotationMarker | null>,
    default: null
  },
  objects: {
    type: Array as PropType<{ id: number; name: string }[]>,
    default: () => []
  }
});

// Emits
const emit = defineEmits([
  'close',
  'delete-marker',
  'change-label',
  'create-label'
]);

// State
const selectedLabelIndex = ref<number | null>(null);
const showNewLabelInput = ref(false);
const newLabelName = ref('');

// When selected marker changes, update the selected label
watch(() => props.selectedMarker, (marker) => {
  if (marker) {
    // If it's a background marker (objectIdx = 0)
    if (marker.objectIdx === 0) {
      selectedLabelIndex.value = 'background';
    } else {
      // Find the index of the object in the objects array
      const index = props.objects.findIndex(obj => obj.id === marker.objectIdx);
      selectedLabelIndex.value = index >= 0 ? index : null;
    }
  } else {
    selectedLabelIndex.value = null;
  }
}, {immediate: true});

// Methods
const formatPosition = (position: THREE.Vector3) => {
  return `(${position.x.toFixed(2)}, ${position.y.toFixed(2)}, ${position.z.toFixed(2)})`;
};

const getLabelName = (objectIdx: number) => {
  if (objectIdx === 0) return 'Background';

  const object = props.objects.find(obj => obj.id === objectIdx);
  return object ? object.name : `Object ${objectIdx}`;
};

const getLabelColor = (objectIdx: number) => {
  if (objectIdx === 0) return '#666666'; // Background color
  return getCssColorFromIndex(objectIdx, 100, 50);
};

const selectLabel = (objectId: number) => {
  if (!props.selectedMarker) return;

  emit('change-label', {
    markerId: props.selectedMarker.id,
    newObjectIdx: objectId
  });
};

const createNewLabel = () => {
  if (!newLabelName.value.trim() || !props.selectedMarker) return;

  emit('create-label', {
    name: newLabelName.value.trim(),
    markerId: props.selectedMarker.id
  });

  // Reset state
  newLabelName.value = '';
  showNewLabelInput.value = false;
};
</script>

<style scoped>
.marker-action-panel {
  position: absolute;
  right: 20px;
  top: 80px;
  width: 280px;
  background-color: rgba(33, 33, 33, 0.9);
  border-radius: 8px;
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.3);
  z-index: 100;
  overflow: hidden;
  color: white;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 15px;
  background-color: rgba(0, 0, 0, 0.2);
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.panel-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 500;
}

.panel-content {
  padding: 15px;
}

.marker-info {
  margin-bottom: 15px;
  padding-bottom: 15px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.marker-position, .marker-label {
  margin-bottom: 8px;
  font-size: 14px;
}

.existing-labels {
  max-height: 150px;
  overflow-y: auto;
  margin: 8px 0;
}

.action-buttons {
  margin-top: 15px;
}

.new-label-input {
  margin-top: 10px;
  padding: 10px;
  background-color: rgba(255, 255, 255, 0.05);
  border-radius: 4px;
}
</style>