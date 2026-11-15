import { createApp } from 'vue';
import { createRouter, createWebHistory } from 'vue-router';
import App from './App.vue';
import './style.css';

const paths = [
  '/', '/welcome', '/login', '/register', '/today',
  '/about',
  '/cycle', '/cycle/block/:blockId', '/cycle/week/:week', '/cycle/week/:week/day/:day', '/cycle/test',
  '/analysis', '/archive', '/archive/:cycleId', '/questionnaire',
  '/:pathMatch(.*)*',
];
const redirects = [
  { path: '/plan', redirect: '/cycle' },
  { path: '/plan/block/:blockId', redirect: to => `/cycle/block/${to.params.blockId}` },
  { path: '/plan/week/:week/day/:day', redirect: to => `/cycle/week/${to.params.week}/day/${to.params.day}` },
  { path: '/plan/week/:week', redirect: to => `/cycle/week/${to.params.week}` },
  { path: '/plan/test', redirect: '/cycle/test' },
  { path: '/settings', redirect: '/archive#account' },
];
const router = createRouter({
  history: createWebHistory(),
  routes: [...paths.filter(path => !path.startsWith('/:')).map(path => ({ path, component: { render: () => null } })), ...redirects, { path: '/:pathMatch(.*)*', component: { render: () => null } }],
});
createApp(App).use(router).mount('#app');
