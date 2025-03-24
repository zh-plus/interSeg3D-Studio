import {createApp} from 'vue';
import App from './App.vue';
import {createPinia} from 'pinia';
import {createVuetify} from 'vuetify';
import * as components from 'vuetify/components';
import * as directives from 'vuetify/directives';
import 'vuetify/styles';
import '@mdi/font/css/materialdesignicons.css';

// Create Vuetify instance
const vuetify = createVuetify({
    components,
    directives,
    theme: {
        defaultTheme: 'dark',
        themes: {
            dark: {
                colors: {
                    primary: '#00B0FF',
                    secondary: '#B2FF59',
                    error: '#FF5252',
                    warning: '#FB8C00',
                    info: '#2196F3',
                    success: '#4CAF50',
                    background: '#121212',
                    surface: '#212121',
                }
            }
        }
    }
});

// Create Pinia store
const pinia = createPinia();

// Create and mount the app
createApp(App)
    .use(vuetify)
    .use(pinia)
    .mount('#app');