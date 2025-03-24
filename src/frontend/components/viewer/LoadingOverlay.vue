<template>
  <div v-if="props.show" class="loading-overlay">
    <div class="loading-content">
      <slot>
        {{ props.message }}
        <div v-if="props.progress !== null" class="progress-indicator">
          {{ props.progress }}%
        </div>
      </slot>
    </div>
  </div>
</template>

<script lang="ts" setup>
// Define props with defineProps
const props = defineProps({
  show: {
    type: Boolean,
    default: false
  },
  message: {
    type: String,
    default: 'Loading...'
  },
  progress: {
    type: Number,
    default: null
  }
});
</script>

<style scoped>
.loading-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-color: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}

.loading-content {
  background-color: rgba(0, 0, 0, 0.8);
  color: white;
  padding: 20px;
  border-radius: 8px;
  text-align: center;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.progress-indicator {
  font-size: 1.5em;
  font-weight: bold;
}
</style>