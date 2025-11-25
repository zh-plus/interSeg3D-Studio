<template>
  <v-card class="object-description-card">
    <v-card-title class="d-flex align-center">
      <span class="object-title">{{ object?.name || 'Object' }}</span>
      <v-chip :color="chipColor" class="ml-2" dark x-small>ID: {{ object?.id }}</v-chip>
    </v-card-title>

    <v-card-text>
      <v-skeleton-loader
          v-if="loading"
          type="text@4"
      ></v-skeleton-loader>

      <div v-else-if="object?.description" class="description-content">
        <div class="subheading font-weight-bold mb-2">Description:</div>
        <p>{{ object.description }}</p>
      </div>

      <div v-else class="no-description">
        <v-icon color="grey lighten-1">mdi-text-box-remove-outline</v-icon>
        <p>No description available for this object.</p>
        <p class="hint-text">Run "Analyze Objects" to generate a description.</p>
      </div>
    </v-card-text>

    <v-card-actions v-if="showActions">
      <v-spacer></v-spacer>
      <v-btn color="primary" text @click="$emit('close')">Close</v-btn>
    </v-card-actions>
  </v-card>
</template>

<script lang="ts">
import {computed, defineComponent, PropType} from 'vue';

interface ObjectData {
  id: number;
  name: string;
  description?: string;
}

export default defineComponent({
  name: 'ObjectDescriptionCard',

  props: {
    object: {
      type: Object as PropType<ObjectData | null>,
      default: null
    },
    loading: {
      type: Boolean,
      default: false
    },
    showActions: {
      type: Boolean,
      default: true
    }
  },

  emits: ['close'],

  setup(props) {
    const chipColor = computed(() => {
      if (!props.object) return 'grey';
      const hue = (props.object.id * 50) % 360;
      return `hsl(${hue}, 80%, 40%)`;
    });

    return {
      chipColor
    };
  }
});
</script>

<style scoped>
.object-description-card {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.object-title {
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.description-content {
  white-space: pre-line;
  line-height: 1.6;
  max-height: 400px;
  overflow-y: auto;
}

.no-description {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 2rem;
  color: #757575;
  text-align: center;
}

.no-description .v-icon {
  font-size: 3rem;
  margin-bottom: 1rem;
}

.hint-text {
  font-size: 0.875rem;
  font-style: italic;
  margin-top: 0.5rem;
}
</style>