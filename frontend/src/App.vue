<script setup lang="ts">
import { computed, ref } from 'vue'
import { RouterLink, RouterView, useRoute } from 'vue-router'

import { getUsername, setUsername } from './api/client'

const route = useRoute()
const isAdmin = computed(() => route.name === 'admin')
const username = ref(getUsername())
const editingName = ref(false)
const nameInput = ref(username.value)

function saveName() {
  const v = nameInput.value.trim().slice(0, 50)
  if (!v) return
  setUsername(v)
  username.value = v
  editingName.value = false
}
</script>

<template>
  <div class="app-shell">
    <div class="app-shell-inner">
      <header
        v-if="!isAdmin"
        class="sticky top-0 z-30 border-b border-brand-200/50 bg-white/55 backdrop-blur"
      >
        <div class="mx-auto flex max-w-[1400px] items-center gap-3 px-4 py-3 lg:px-6">
          <RouterLink to="/" class="flex items-center gap-2 text-lg font-extrabold text-brand-700">
            <span class="animate-float">🪢</span> Jump Rope
          </RouterLink>
          <nav class="ml-auto flex flex-wrap items-center gap-1 text-sm">
            <RouterLink
              to="/"
              class="rounded-xl px-3 py-2 font-bold text-brand-700 hover:bg-white/70"
              active-class="bg-white/80"
            >
              广场
            </RouterLink>
            <RouterLink
              to="/upload"
              class="rounded-xl px-3 py-2 font-bold text-brand-700 hover:bg-white/70"
              active-class="bg-white/80"
            >
              上传
            </RouterLink>
            <RouterLink
              to="/mine"
              class="rounded-xl px-3 py-2 font-bold text-brand-700 hover:bg-white/70"
              active-class="bg-white/80"
            >
              我的
            </RouterLink>
            <RouterLink
              to="/featured"
              class="rounded-xl px-3 py-2 font-bold text-brand-700 hover:bg-white/70"
              active-class="bg-white/80"
            >
              编辑推荐
            </RouterLink>
            <RouterLink
              to="/competitions"
              class="rounded-xl px-3 py-2 font-bold text-brand-700 hover:bg-white/70"
              active-class="bg-white/80"
            >
              比赛
            </RouterLink>
            <RouterLink
              to="/admin"
              class="rounded-xl px-3 py-2 font-bold text-brand-700/70 hover:bg-white/70"
            >
              管理
            </RouterLink>
          </nav>
          <div class="hidden items-center gap-2 sm:flex">
            <template v-if="!editingName">
              <button class="chip bg-white/80 text-brand-700" @click="editingName = true">
                {{ username || '设置昵称' }}
              </button>
            </template>
            <template v-else>
              <input
                v-model="nameInput"
                class="w-28 rounded-xl border border-brand-200 px-2 py-1 text-sm"
                placeholder="昵称"
                @keyup.enter="saveName"
              />
              <button class="btn-primary !px-3 !py-1 text-sm" @click="saveName">保存</button>
            </template>
          </div>
        </div>
      </header>

      <main class="mx-auto min-h-[70vh] max-w-[1400px] px-4 py-6 lg:px-6">
        <RouterView />
      </main>
    </div>
  </div>
</template>
