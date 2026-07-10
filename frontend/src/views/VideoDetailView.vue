<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import { api, getUsername, type JumpVideo } from '../api/client'

const route = useRoute()
const video = ref<JumpVideo | null>(null)
const error = ref('')
const featuredStatus = ref<{ can_submit: boolean } | null>(null)
const submitting = ref(false)

const isOwner = computed(() => video.value && getUsername() === video.value.username)
const segments = computed(() => video.value?.ai_score_detail?.fancy_segments || [])

async function load() {
  try {
    video.value = await api.get(`/api/videos/${route.params.id}`)
    if (getUsername()) {
      featuredStatus.value = await api.get('/api/featured/status')
    }
  } catch (err: any) {
    error.value = err.message || '加载失败'
  }
}

async function publish() {
  if (!video.value) return
  try {
    video.value = await api.post(`/api/videos/${video.value.id}/publish`)
  } catch (err: any) {
    alert(err.message || '发布失败')
  }
}

async function submitFeatured() {
  if (!video.value) return
  submitting.value = true
  try {
    await api.post('/api/featured/submissions', { video_id: video.value.id })
    alert('已投稿，等待编辑审核')
    featuredStatus.value = await api.get('/api/featured/status')
  } catch (err: any) {
    alert(err.message || '投稿失败')
  } finally {
    submitting.value = false
  }
}

onMounted(load)
</script>

<template>
  <div v-if="error" class="card text-candy">{{ error }}</div>
  <div v-else-if="!video" class="text-brand-700/60">加载中…</div>
  <div v-else class="mx-auto max-w-3xl space-y-6 animate-pop-in">
    <div>
      <h1 class="text-3xl font-extrabold text-brand-700">{{ video.title }}</h1>
      <p class="mt-1 text-brand-700/70">{{ video.username }} · {{ video.created_at?.slice(0, 10) }}</p>
    </div>

    <video v-if="video.video_url" :src="video.video_url" controls class="w-full rounded-3xl bg-black shadow-pop" />
    <div v-else class="card aspect-video flex items-center justify-center text-brand-700/50">视频处理中…</div>

    <div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
      <div class="card text-center !py-4">
        <div class="text-2xl font-extrabold text-brand-600">{{ video.jump_count ?? '-' }}</div>
        <div class="text-xs font-bold text-brand-700/60">总次数</div>
      </div>
      <div class="card text-center !py-4">
        <div class="text-2xl font-extrabold text-brand-600">{{ video.speed_per_min ?? '-' }}</div>
        <div class="text-xs font-bold text-brand-700/60">次/分钟</div>
      </div>
      <div class="card text-center !py-4">
        <div class="text-2xl font-extrabold text-candy">{{ video.fancy_count ?? '-' }}</div>
        <div class="text-xs font-bold text-brand-700/60">花式次数</div>
      </div>
      <div class="card text-center !py-4">
        <div class="text-2xl font-extrabold text-brand-600">{{ video.fancy_duration_sec ?? '-' }}s</div>
        <div class="text-xs font-bold text-brand-700/60">花式时长</div>
      </div>
    </div>

    <div class="card">
      <div class="text-lg font-extrabold text-brand-700">综合分 {{ video.ai_score ?? '-' }}</div>
      <p class="mt-2 whitespace-pre-wrap text-brand-700/80">{{ video.description || '暂无描述' }}</p>
    </div>

    <div v-if="segments.length" class="card space-y-2">
      <h2 class="font-extrabold text-brand-700">花式片段</h2>
      <div v-for="s in segments" :key="s.index" class="flex justify-between rounded-2xl bg-brand-50 px-4 py-2 text-sm">
        <span class="font-bold text-brand-700">{{ s.label }}</span>
        <span class="text-brand-700/60">{{ s.start_sec }}s – {{ s.end_sec }}s</span>
      </div>
    </div>

    <div v-if="isOwner" class="flex flex-wrap gap-3">
      <button v-if="!video.is_public && video.score_status === 'done'" class="btn-primary" @click="publish">
        发布到广场
      </button>
      <button
        v-if="video.is_public && featuredStatus?.can_submit"
        class="btn-candy"
        :disabled="submitting"
        @click="submitFeatured"
      >
        投稿编辑推荐
      </button>
      <span v-else-if="video.is_public && featuredStatus && !featuredStatus.can_submit" class="chip bg-brand-100">
        24h 内已投稿过
      </span>
    </div>
  </div>
</template>
