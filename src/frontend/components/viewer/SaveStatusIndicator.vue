<template>
  <div class="save-status-indicator" :class="statusClass">
    <v-tooltip bottom>
      <template v-slot:activator="{ on, attrs }">
        <div class="status-icon" v-bind="attrs" v-on="on">
          <v-icon v-if="status === 'unsaved'" color="error" small>
            mdi-content-save-alert
          </v-icon>
          <v-progress-circular v-else-if="status === 'saving'"
                               indeterminate
                               color="info"
                               size="16"
                               width="2"
          ></v-progress-circular>
          <v-icon v-else-if="status === 'saved'" color="success" small>
            mdi-content-save-check
          </v-icon>
        </div>
      </template>
      <span>{{ statusMessage }}</span>
    </v-tooltip>
  </div>
</template>

<script lang="ts" setup>
import {computed} from 'vue';

// Props
const props = defineProps({
  status: {
    type: String as () => 'unsaved' | 'saving' | 'saved',
    required: true
  },
  lastSaved: {
    type: Number,
    default: null
  }
});

// Computed properties
const statusClass = computed(() => {
  return `status-${props.status}`;
});

const statusMessage = computed(() => {
  if (props.status === 'unsaved') {
    return 'Changes not saved. Press Ctrl+S to save.';
  } else if (props.status === 'saving') {
    return 'Saving changes...';
  } else if (props.status === 'saved') {
    if (props.lastSaved) {
      const date = new Date(props.lastSaved);
      return `Saved at ${date.toLocaleTimeString()}`;
    }
    return 'All changes saved';
  }
  return '';
});
</script>

<style scoped>
.save-status-indicator {
  display: inline-flex;
  align-items: center;
  padding: 4px 8px;
  border-radius: 4px;
  margin-left: 8px;
  transition: all 0.3s ease;
}

.status-icon {
  display: flex;
  align-items: center;
  justify-content: center;
}

.status-unsaved {
  animation: pulse 2s infinite;
}

.status-saving {
  opacity: 0.8;
}

.status-saved {
  opacity: 0.8;
}

@keyframes pulse {
  0% {
    opacity: 0.6;
  }
  50% {
    opacity: 1;
  }
  100% {
    opacity: 0.6;
  }
}
</style>