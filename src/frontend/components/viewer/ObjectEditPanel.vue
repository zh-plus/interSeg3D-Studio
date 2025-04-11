```vue
<template>
  <div v-if="selectedObject" class="object-edit-panel" :style="panelStyle">
    <div class="panel-header">
      <h3>Edit Object</h3>
      <v-btn icon x-small @click="$emit('close')">
        <v-icon>mdi-close</v-icon>
      </v-btn>
    </div>

    <div class="panel-content">
      <v-text-field
          v-model="editedLabel"
          label="Object Label"
          dense
          outlined
      ></v-text-field>

      <v-textarea
          v-model="editedDescription"
          label="Description"
          dense
          outlined
          rows="4"
          auto-grow
      ></v-textarea>

      <div class="d-flex justify-end mt-2">
        <v-btn
            color="error"
            text
            class="mr-2"
            @click="$emit('close')"
        >
          Cancel
        </v-btn>
        <v-btn
            color="primary"
            @click="saveChanges"
        >
          Save
        </v-btn>
      </div>
    </div>
  </div>
</template>

<script lang="ts" setup>
import {computed, PropType, ref, watch} from 'vue';
import {ObjectData} from '@/stores';

// Props
const props = defineProps({
  selectedObject: {
    type: Object as PropType<ObjectData | null>,
    default: null
  },
  position: {
    type: Object as PropType<{ x: number, y: number }>,
    default: () => ({x: 0, y: 0})
  }
});

// Emits
const emit = defineEmits([
  'close',
  'save'
]);

// Local state for editing
const editedLabel = ref('');
const editedDescription = ref('');

// Compute panel position style
const panelStyle = computed(() => {
  // Get coordinates from props
  const {x, y} = props.position;

  console.log('Positioning edit panel at:', x, y);

  // Calculate panel position
  return {
    left: `${x}px`,
    top: `${y}px`,
    transform: 'translate(-50%, -50%)', // Center on cursor position
    border: '2px solid #1e88e5' // Add visible border to make it more noticeable
  };
});

// Watch for selected object changes
watch(() => props.selectedObject, (object) => {
  console.log('ObjectEditPanel: Selected object changed:', object);
  if (object) {
    editedLabel.value = object.name;
    editedDescription.value = object.description || '';
  }
}, {immediate: true});

// Save changes
const saveChanges = () => {
  if (!props.selectedObject) return;

  emit('save', {
    id: props.selectedObject.id,
    name: editedLabel.value,
    description: editedDescription.value
  });

  emit('close');
};
</script>

<style scoped>
.object-edit-panel {
  position: absolute;
  width: 320px;
  background-color: rgba(33, 33, 33, 0.95);
  border-radius: 8px;
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.3);
  z-index: 1000; /* Higher z-index to ensure visibility */
  overflow: hidden;
  color: white;
  pointer-events: auto; /* Ensure it can receive mouse events */
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
</style>
```