<template>
  <div class="selection-info">
    <div v-if="props.showPointCount && props.pointCount > 0" class="point-count">
      Points: {{ formattedPointCount }}
    </div>
    <div v-if="props.coordinate" class="coordinate">
      Selected: ({{ formatCoordinate(props.coordinate) }})
    </div>
    <div v-if="props.showClickCount" class="click-count">
      Clicks: {{ props.clickCount }}
      <span v-if="props.canUndo || props.canRedo" class="undo-redo-indicators">
        <span :class="['undo-indicator', { active: props.canUndo }]" title="Ctrl+Z to undo">
          <v-icon x-small>mdi-undo</v-icon>
        </span>
        <span :class="['redo-indicator', { active: props.canRedo }]" title="Shift+Ctrl+Z to redo">
          <v-icon x-small>mdi-redo</v-icon>
        </span>
      </span>
    </div>
    <div v-if="props.isProcessingSelection" class="processing-indicator">
      Processing selection...
    </div>
    <div v-if="props.showDebug" class="debug-panel">
      <h4>Click Points: {{ props.clickPoints.length }}</h4>
      <div v-for="(point, index) in props.clickPoints.slice(0, 3)" :key="index">
        Point {{ index + 1 }}: {{ point.objectIdx === 0 ? 'Background' : `Object ${point.objectIdx}` }}
      </div>
      <div v-if="props.clickPoints.length > 3">...</div>
      <div v-if="props.canUndo || props.canRedo" class="history-debug">
        <div v-if="props.canUndo">Undo available (Ctrl+Z)</div>
        <div v-if="props.canRedo">Redo available (Shift+Ctrl+Z)</div>
      </div>
    </div>
  </div>
</template>

<script lang="ts" setup>
import {computed} from 'vue';
import {ClickPoint} from '@/types/selection.types';

// Define props with defineProps
const props = defineProps({
  coordinate: {
    type: Array as () => number[] | null,
    default: null
  },
  pointCount: {
    type: Number,
    default: 0
  },
  clickCount: {
    type: Number,
    default: 0
  },
  showPointCount: {
    type: Boolean,
    default: true
  },
  showClickCount: {
    type: Boolean,
    default: true
  },
  showDebug: {
    type: Boolean,
    default: false
  },
  isProcessingSelection: {
    type: Boolean,
    default: false
  },
  clickPoints: {
    type: Array as () => ClickPoint[],
    default: () => []
  },
  // Add undo/redo status props
  canUndo: {
    type: Boolean,
    default: false
  },
  canRedo: {
    type: Boolean,
    default: false
  }
});

// Computed properties
const formattedPointCount = computed(() => {
  return props.pointCount.toLocaleString();
});

// Methods
const formatCoordinate = (coord: number[]) => {
  return coord.map(c => c.toFixed(2)).join(', ');
};
</script>

<style scoped>
.selection-info {
  position: absolute;
  top: 10px;
  left: 10px;
  background-color: rgba(0, 0, 0, 0.6);
  color: white;
  padding: 10px;
  border-radius: 4px;
  font-family: monospace;
  z-index: 50;
}

.debug-panel {
  margin-top: 10px;
  border-top: 1px solid rgba(255, 255, 255, 0.3);
  padding-top: 10px;
  font-size: 12px;
}

.processing-indicator {
  margin-top: 6px;
  font-weight: bold;
  color: #ffab00;
}

.undo-redo-indicators {
  margin-left: 8px;
  display: inline-flex;
  gap: 4px;
}

.undo-indicator, .redo-indicator {
  opacity: 0.3;
  cursor: default;
}

.undo-indicator.active, .redo-indicator.active {
  opacity: 1;
}

.history-debug {
  margin-top: 8px;
  font-size: 11px;
  color: #4caf50;
}
</style>