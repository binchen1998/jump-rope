import { createRouter, createWebHistory } from 'vue-router'

import HomeView from '../views/HomeView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: HomeView },
    {
      path: '/upload',
      name: 'upload',
      component: () => import('../views/UploadView.vue'),
    },
    {
      path: '/mine',
      name: 'mine',
      component: () => import('../views/MyVideosView.vue'),
    },
    {
      path: '/videos/:id',
      name: 'video-detail',
      component: () => import('../views/VideoDetailView.vue'),
    },
    {
      path: '/featured',
      name: 'featured',
      component: () => import('../views/FeaturedView.vue'),
    },
    {
      path: '/competitions',
      name: 'competitions',
      component: () => import('../views/CompetitionsView.vue'),
    },
    {
      path: '/competitions/:id',
      name: 'competition-detail',
      component: () => import('../views/CompetitionDetailView.vue'),
    },
    {
      path: '/admin/:tab?',
      name: 'admin',
      component: () => import('../views/AdminView.vue'),
    },
  ],
  scrollBehavior() {
    return { top: 0 }
  },
})

export default router
