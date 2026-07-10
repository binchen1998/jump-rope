<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import { api, getUsername, type JumpVideo } from '../api/client'

const videos = ref<JumpVideo[]>([])
const error = ref('')
const loading = ref(true)

async function load() {
  if (!getUsername()) {
    error.value = '请先设置昵称'
    loading.value = false
    return
  }
  loading.value = true
  try {
    const res = await api.get('/api/videos/mine')
    videos.value = res.items || []
  } catch (err: any) {
    error.value = err.message || '加载失败'
  } finally {
    loading.value = false
  }
}

async function togglePublic(v: JumpVideo) {
  try {
    if (v.is_public) {
      Object.assign(v, await api.post(`/api/videos/${v.id}/unpublish`))
    } else {
      Object.assign(v, await api.post(`/api/videos/${v.id}/publish`))
    }
  } catch (err: any) {
    alert(err.message || '操作失败')
  }
}

async function remove(v: JumpVideo) {
  if (!confirm('确定删除？公开作品需先取消公开。')) return
  try {
    await api.del(`/api/videos/${v.id}`)
    videos.value = videos.value.filter((x) => x.id !== v.id)
  } catch (err: any) {
    alert(err.message || '删除失败')
  }
}

onMounted(load)
</script>

<template>
  <div class="space-y-6 animate-pop-in">
    <div class="flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 class="text-3xl font-extrabold text-brand-700">我的跳绳</h1>
        <p class="mt-1 text-brand-700/70">保存的视频、发布状态与分析结果</p>
      </div>
      <RouterLink to="/upload" class="btn-primary">上传新视频</RouterLink>
    </div>

    <p v-if="error" class="card text-candy">{{ error }}</p>
    <div v-else-if="loading" class="text-brand-700/60">加载中…</div>
    <div v-else-if="!videos.length" class="card text-center text-brand-700/70">还没有视频，去上传一个吧。</div>
    <div v-else class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <div v-for="v in videos" :key="v.id" class="card !p-3 space-y-3">
        <RouterLink :to="`/videos/${v.id}`">
          <div class="aspect-video overflow-hidden rounded-2xl bg-brand-100">
            <img v-if="v.cover_url" :src="v.cover_url" class="h-full w-full object-cover" alt="" />
            <div v-else class="flex h-full items-center justify-center text-4xl">🪢</div>
          </div>
          <div class="mt-2 truncate font-extrabold text-brand-700">{{ v.title }}</div>
        </RouterLink>
        <div class="flex flex-wrap gap-2 text-xs">
          <span class="chip" :class="v.is_public ? 'bg-mint/20 text-mint' : 'bg-brand-100 text-brand-700'">
            {{ v.is_public ? '已公开' : '私密' }}
          </span>
          <span class="chip bg-white text-brand-700">{{ v.score_status }}</span>
          <span v-if="v.jump_count != null" class="chip bg-brand-100">{{ v.jump_count }} 次</span>
        </div>
        <div class="flex flex-wrap gap-2">
          <button
            class="btn-ghost !px-3 !py-2 text-sm"
            :disabled="v.score_status !== 'done'"
            @click="togglePublic(v)"
          >
            {{ v.is_public ? '取消公开' : '发布到广场' }}
          </button>
          <button class="btn-ghost !px-3 !py-2 text-sm text-candy" @click="remove(v)">删除</button>
        </div>
      </div>
    </div>
  </div>
</template>
