<template>
  <v-dialog
      v-model="dialog"
      :fullscreen="display.xs"
      max-width="800px"
      persistent
      scrollable
  >
    <v-card>
      <v-card-title class="headline">
        Analysis Results
        <v-spacer></v-spacer>
        <v-btn icon @click="closeDialog">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>

      <v-divider></v-divider>

      <v-card-text class="analysis-content">
        <div v-if="loading" class="loading-container">
          <v-progress-circular
              color="primary"
              indeterminate
              size="64"
          ></v-progress-circular>
          <p class="mt-4">Analyzing objects, please wait...</p>
          <p class="text-caption">This may take a minute as the system renders and processes multiple views.</p>
        </div>

        <div v-else-if="analysisResults.length === 0" class="no-results">
          <v-icon color="grey lighten-1" x-large>mdi-alert-circle-outline</v-icon>
          <h3 class="mt-4">No analysis results available</h3>
          <p>Try running the analysis again with more defined object segments.</p>
        </div>

        <v-expansion-panels
            v-else
            v-model="openPanels"
            multiple
        >
          <v-expansion-panel
              v-for="(result, index) in analysisResults"
              :key="index"
          >
            <v-expansion-panel-header>
              <div class="d-flex align-center">
                <v-avatar
                    :color="getColorForIndex(index + 1)"
                    class="mr-3"
                    size="32"
                >
                  {{ index + 1 }}
                </v-avatar>
                <span class="font-weight-medium">{{ result.label }}</span>
              </div>
            </v-expansion-panel-header>

            <v-expansion-panel-content>
              <v-card flat>
                <v-card-text>
                  <v-row>
                    <v-col cols="12">
                      <div class="text-subtitle-1 font-weight-bold mb-2">Description:</div>
                      <p class="description-text">{{ result.description }}</p>
                    </v-col>

                    <v-col v-if="result.selected_views && result.selected_views.length > 0" cols="12" md="6">
                      <div class="text-subtitle-1 font-weight-bold mb-2">Best Views:</div>
                      <v-chip-group>
                        <v-chip
                            v-for="viewId in result.selected_views"
                            :key="viewId"
                            outlined
                            small
                        >
                          View {{ viewId }}
                        </v-chip>
                      </v-chip-group>
                    </v-col>

                    <v-col v-if="result.cost !== undefined" cols="12" md="6">
                      <div class="text-subtitle-1 font-weight-bold mb-2">Analysis Cost:</div>
                      <v-chip color="primary" outlined small>
                        ${{ result.cost.toFixed(4) }}
                      </v-chip>
                    </v-col>
                  </v-row>
                </v-card-text>

                <v-divider></v-divider>

                <v-card-actions class="action-buttons-compact">
                  <v-btn
                      :disabled="appliedResults.includes(index)"
                      color="success"
                      text
                      @click="applyLabel(result.label, index)"
                  >
                    <v-icon left>mdi-check</v-icon>
                    {{ appliedResults.includes(index) ? 'Applied' : 'Apply Label' }}
                  </v-btn>

                  <v-spacer></v-spacer>

                  <v-btn
                      color="info"
                      text
                      @click="viewObjectDetails(index)"
                  >
                    <v-icon left>mdi-eye</v-icon>
                    View Object
                  </v-btn>
                </v-card-actions>
              </v-card>
            </v-expansion-panel-content>
          </v-expansion-panel>
        </v-expansion-panels>
      </v-card-text>

      <v-divider></v-divider>

      <v-card-actions class="justify-end">
        <v-btn
            class="mr-2"
            color="error"
            dense
            text
            @click="closeDialog"
        >
          Cancel
        </v-btn>

        <v-btn
            :disabled="analysisResults.length === 0 || appliedResults.length === analysisResults.length"
            color="primary"
            dense
            @click="applyAllResults"
        >
          <v-icon left small>mdi-check-all</v-icon>
          Apply All Results
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script lang="ts">
import {computed, defineComponent, PropType, ref, watch} from 'vue';
import {getCssColorFromIndex} from '@/utils/color-utils';
import {useDisplay} from 'vuetify';

export interface AnalysisResult {
  selected_views: number[];
  description: string;
  label: string;
  cost?: number;
  obj_id?: number; // Optional object ID that may be provided by the backend or computed
}

export default defineComponent({
  name: 'ObjectAnalysisDialog',

  props: {
    modelValue: {
      type: Boolean,
      default: false
    },
    results: {
      type: Array as PropType<AnalysisResult[]>,
      default: () => []
    },
    loading: {
      type: Boolean,
      default: false
    }
  },

  emits: ['update:modelValue', 'apply-label', 'apply-all', 'view-object'],

  setup(props, {emit}) {
    const display = useDisplay();

    const dialog = computed({
      get: () => props.modelValue,
      set: (value) => emit('update:modelValue', value)
    });

    const openPanels = ref<number[]>([0]); // Open first panel by default
    const appliedResults = ref<number[]>([]);

    // Reset applied results when dialog opens
    watch(() => props.modelValue, (newVal) => {
      if (newVal) {
        appliedResults.value = [];
        // Open the first panel when dialog opens
        openPanels.value = props.results.length > 0 ? [0] : [];
      }
    });

    const analysisResults = computed(() => props.results);

    function closeDialog() {
      dialog.value = false;
    }

    function getColorForIndex(index: number) {
      return getCssColorFromIndex(index, 100, 50);
    }

    function applyLabel(label: string, resultIndex: number) {
      emit('apply-label', {label, index: resultIndex});
      appliedResults.value.push(resultIndex);
    }

    function applyAllResults() {
      emit('apply-all', props.results);
      appliedResults.value = props.results.map((_, i) => i);
    }

    function viewObjectDetails(index: number) {
      emit('view-object', index);
    }

    return {
      dialog,
      display,
      openPanels,
      appliedResults,
      analysisResults,
      closeDialog,
      getColorForIndex,
      applyLabel,
      applyAllResults,
      viewObjectDetails
    };
  }
});
</script>

<style scoped>
.analysis-content {
  min-height: 300px;
  overflow-y: auto; /* Keep this if you want scrolling for very large content */
  display: flex;
  flex-direction: column;
}

.loading-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 300px;
  text-align: center;
}

.no-results {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 300px;
  text-align: center;
  color: #757575;
}

.description-text {
  white-space: pre-line;
  line-height: 1.6;
}

.action-buttons-compact {
  padding: 8px 16px !important;
  min-height: auto !important;
}
</style>