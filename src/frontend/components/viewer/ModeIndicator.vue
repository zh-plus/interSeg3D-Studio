<template>
  <div :class="['mode-indicator', props.mode.toLowerCase()]">
    <slot>
      {{ displayText }}
    </slot>
  </div>
</template>

<script lang="ts" setup>
import {computed} from 'vue';
import {InteractionMode} from '@/types/selection.types';

// Define props with defineProps
const props = defineProps({
  mode: {
    type: String as () => InteractionMode,
    required: true,
    validator: (value: string) => ['navigate', 'annotate'].includes(value)
  },
  clickMode: {
    type: String,
    default: ''
  }
});

// Computed properties
const displayText = computed(() => {
  if (props.mode === 'navigate') {
    return 'NAVIGATE MODE';
  } else {
    return props.clickMode
        ? `ANNOTATE MODE: ${props.clickMode.toUpperCase()}`
        : 'ANNOTATE MODE';
  }
});
</script>

<style scoped>
.mode-indicator {
  position: absolute;
  top: 80px;
  right: 15px;
  padding: 5px 10px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: bold;
  opacity: 0.7;
  z-index: 50;
  pointer-events: none;
}

.navigate {
  background-color: #1E88E5;
  color: white;
}

.annotate {
  background-color: #FF8F00;
  color: white;
}
</style>