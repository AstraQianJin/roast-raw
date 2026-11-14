import { createApp } from 'vue';
import { createRouter, createWebHistory } from 'vue-router';
import App from './App.vue';
import './style.css';

const paths = ['/', '/welcome', '/today', '/plan', '/plan/block/:blockId', '/plan/week/:week', '/plan/week/:week/day/:day', '/plan/test', '/analysis', '/archive', '/archive/:cycleId', '/questionnaire', '/settings', '/:pathMatch(.*)*'];
const router = createRouter({
  history: createWebHistory(),
  routes: paths.map(path => ({ path, component: { render: () => null } })),
});
createApp(App).use(router).mount('#app');
