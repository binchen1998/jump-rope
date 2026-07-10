import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'
import { USERNAME_KEY, setUsername } from './api/client'
import { applyColorTheme } from './theme'
import './style.css'

function syncUsernameFromUrl() {
  const params = new URLSearchParams(window.location.search)
  const u = params.get('username')
  if (u) setUsername(u)
  else if (!localStorage.getItem(USERNAME_KEY)) {
    // 开发默认游客名
  }
}

syncUsernameFromUrl()
applyColorTheme()

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')
