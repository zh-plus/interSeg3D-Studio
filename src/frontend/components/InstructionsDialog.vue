<template>
  <v-dialog
      v-model="dialogModel"
      max-width="600"
  >
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
              <v-icon color="purple">mdi-cursor-pointer</v-icon>
            </v-list-item-icon>
            <v-list-item-content>
              <v-list-item-title>Select Mode</v-list-item-title>
              <v-list-item-subtitle>Switch to "Select" mode to click on segmented objects and edit their labels and
                descriptions.
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
              <v-list-item-subtitle>Press <kbd>A</kbd> to toggle between navigation and annotation modes
              </v-list-item-subtitle>
              <v-list-item-subtitle>Press <kbd>S</kbd> to activate select mode</v-list-item-subtitle>
              <v-list-item-subtitle>Press <kbd>Enter</kbd> to run segmentation</v-list-item-subtitle>
              <v-list-item-subtitle>Press <kbd>N</kbd> to create a new object with default name "new obj"
              </v-list-item-subtitle>
              <v-list-item-subtitle>Press <kbd>Ctrl+Z</kbd> to undo the last click</v-list-item-subtitle>
              <v-list-item-subtitle>Press <kbd>Shift+Ctrl+Z</kbd> to redo an undone click</v-list-item-subtitle>
              <v-list-item-subtitle>Press <kbd>Ctrl+S</kbd> to save object information</v-list-item-subtitle>
            </v-list-item-content>
          </v-list-item>
        </v-list>
      </v-card-text>
      <v-card-actions>
        <v-spacer></v-spacer>
        <v-btn color="primary" text @click="closeDialog">Close</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script lang="ts" setup>
import {computed} from 'vue';

/**
 * Props for the instructions dialog component
 */
const props = defineProps({
  /**
   * Controls the visibility of the dialog (v-model)
   */
  modelValue: {
    type: Boolean,
    required: true
  }
});

/**
 * Events emitted by the component
 */
const emit = defineEmits(['update:modelValue']);

/**
 * Computed property for v-model binding
 */
const dialogModel = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
});

/**
 * Close the dialog
 */
const closeDialog = () => {
  emit('update:modelValue', false);
};
</script>

<style scoped>
kbd {
  background-color: #f7f7f7;
  border: 1px solid #ccc;
  border-radius: 3px;
  box-shadow: 0 1px 0 rgba(0, 0, 0, 0.2);
  color: #333;
  display: inline-block;
  font-family: monospace;
  font-size: 0.85em;
  font-weight: 700;
  line-height: 1;
  padding: 2px 4px;
  white-space: nowrap;
}
</style>