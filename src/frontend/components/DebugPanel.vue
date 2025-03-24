<template>
  <div v-if="showDebug" class="debug-panel">
    <div class="debug-header" @click="togglePanel">
      <h3>API Debug Panel</h3>
      <v-btn icon size="small" @click.stop="togglePanel">
        <v-icon>{{ expanded ? 'mdi-chevron-down' : 'mdi-chevron-up' }}</v-icon>
      </v-btn>
    </div>

    <div v-if="expanded" class="debug-content">
      <div class="debug-section">
        <h4>Last Request</h4>
        <pre>{{ lastRequest }}</pre>
      </div>

      <div class="debug-section">
        <h4>Last Response</h4>
        <pre>{{ lastResponse }}</pre>
      </div>

      <div class="debug-section">
        <h4>Last Error</h4>
        <pre v-if="lastError">{{ lastError }}</pre>
        <p v-else>No errors</p>
      </div>

      <!-- Quick upload tool (migration from DebugUpload.vue) -->
      <div v-if="showDirectUploadTool" class="debug-section">
        <h4>Direct File Upload</h4>
        <div class="file-input">
          <input accept=".ply" type="file" @change="handleFileSelect"/>
          <v-btn
              :disabled="!selectedFile || isUploading"
              :loading="isUploading"
              color="primary"
              size="small"
              @click="uploadSelectedFile"
          >
            Upload Directly
          </v-btn>
        </div>
        <div v-if="uploadStatus" :class="['status', uploadStatus.success ? 'success' : 'error']">
          {{ uploadStatus.message }}
        </div>
        <pre v-if="uploadResponse">{{ uploadResponse }}</pre>
      </div>

      <div class="debug-actions">
        <v-btn color="error" @click="clearLogs">Clear Logs</v-btn>
        <v-btn class="ml-2" color="info" @click="toggleDirectUploadTool">
          {{ showDirectUploadTool ? 'Hide Upload Tool' : 'Show Upload Tool' }}
        </v-btn>
      </div>
    </div>
  </div>
</template>

<script lang="ts" setup>
import {onMounted, ref} from 'vue';
import {api} from '@/services/ApiService';
import {useDebugTools} from '@/composables/useDebugTools';

// Use our new debug tools composable
const debugTools = useDebugTools();
const logger = debugTools.createLogger('DebugPanel');

// State
const showDebug = ref(import.meta.env.DEV || false);
const expanded = ref(false);
const lastRequest = ref('No requests yet');
const lastResponse = ref('No responses yet');
const lastError = ref('');

// Direct upload tool state (migrated from DebugUpload.vue)
const showDirectUploadTool = ref(false);
const selectedFile = ref<File | null>(null);
const isUploading = ref(false);
const uploadStatus = ref<{ success: boolean; message: string } | null>(null);
const uploadResponse = ref<string | null>(null);

// Methods
const togglePanel = () => {
  expanded.value = !expanded.value;
  logger.log('Panel toggled:', expanded.value);
};

const clearLogs = () => {
  lastRequest.value = 'No requests yet';
  lastResponse.value = 'No responses yet';
  lastError.value = '';
  logger.log('Logs cleared');
};

const toggleDirectUploadTool = () => {
  showDirectUploadTool.value = !showDirectUploadTool.value;
};

// File upload methods (migrated from DebugUpload.vue)
const handleFileSelect = (event: Event) => {
  const input = event.target as HTMLInputElement;
  if (input.files && input.files.length > 0) {
    selectedFile.value = input.files[0];
    uploadStatus.value = null;
    uploadResponse.value = null;
    logger.log('File selected:', selectedFile.value.name);
  }
};

const uploadSelectedFile = async () => {
  if (!selectedFile.value) return;

  isUploading.value = true;
  uploadStatus.value = {success: false, message: 'Uploading...'};
  uploadResponse.value = null;

  try {
    logger.log('Starting direct upload');
    const result = await debugTools.uploadFile(selectedFile.value);

    isUploading.value = false;
    if (result.error) {
      uploadStatus.value = {
        success: false,
        message: `Upload failed: ${result.message || 'Unknown error'}`
      };
    } else {
      uploadStatus.value = {
        success: true,
        message: `Upload successful! Points: ${result.pointCount || 'unknown'}`
      };
      uploadResponse.value = JSON.stringify(result, null, 2);
    }
  } catch (error: any) {
    isUploading.value = false;
    uploadStatus.value = {
      success: false,
      message: `Upload error: ${error.message}`
    };
    logger.error('Upload error:', error);
  }
};

// Lifecycle hooks
onMounted(() => {
  // Add interceptors specifically for this debug panel
  const requestInterceptor = api.interceptors.request.use(
      config => {
        const requestData = {
          method: config.method?.toUpperCase(),
          url: config.url,
          headers: config.headers,
          data: config.data instanceof FormData
              ? 'FormData (files cannot be displayed in JSON)'
              : config.data
        };

        lastRequest.value = JSON.stringify(requestData, null, 2);
        return config;
      }
  );

  const responseInterceptor = api.interceptors.response.use(
      response => {
        lastResponse.value = JSON.stringify({
          status: response.status,
          statusText: response.statusText,
          headers: response.headers,
          data: response.data
        }, null, 2);
        lastError.value = '';
        return response;
      },
      error => {
        if (error.response) {
          lastError.value = JSON.stringify({
            status: error.response.status,
            statusText: error.response.statusText,
            headers: error.response.headers,
            data: error.response.data
          }, null, 2);
        } else if (error.request) {
          lastError.value = 'Request was made but no response was received';
        } else {
          lastError.value = error.message;
        }
        return Promise.reject(error);
      }
  );
});
</script>

<style scoped>
.debug-panel {
  position: fixed;
  bottom: 0;
  right: 0;
  width: 400px;
  background-color: rgba(0, 0, 0, 0.9);
  color: #00ff00;
  border-top-left-radius: 8px;
  font-family: monospace;
  z-index: 1000;
}

.debug-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  cursor: pointer;
}

.debug-content {
  padding: 8px 12px;
  max-height: 400px;
  overflow-y: auto;
}

.debug-section {
  margin-bottom: 12px;
}

.file-input {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 10px;
}

.status {
  margin: 10px 0;
  padding: 8px;
  border-radius: 4px;
  font-weight: bold;
}

.success {
  background-color: #4CAF50;
  color: white;
}

.error {
  background-color: #F44336;
  color: white;
}

pre {
  white-space: pre-wrap;
  word-break: break-all;
  background-color: rgba(0, 0, 0, 0.3);
  padding: 8px;
  border-radius: 4px;
  font-size: 12px;
  max-height: 150px;
  overflow-y: auto;
}

.debug-actions {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}
</style>