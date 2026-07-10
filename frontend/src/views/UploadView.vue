<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

import { api, getUsername, type JumpVideo, uploadForm } from '../api/client'

const router = useRouter()
const title = ref('')
const description = ref('')
const file = ref<File | null>(null)
const previewUrl = ref('')
const uploading = ref(false)
const error = ref('')
const video = ref<JumpVideo | null>(null)
const quota = ref<{ can_upload: boolean; today_video: JumpVideo | null } | null>(null)
let pollTimer: number | null = null

const analyzing = computed(() => {
  const v = video.value
  if (!v) return false
  return v.score_status === 'pending' || v.score_status === 'processing' || v.media_status === 'pending' || v.media_status === 'processing'
})

const done = computed(() => video.value?.score_status === 'done')

async function loadQuota() {
  if (!getUsername()) return
  try {
    quota.value = await api.get('/api/videos/upload-quota')
    if (quota.value?.today_video) {
      video.value = quota.value.today_video
      if (analyzing.value) startPoll(quota.value.today_video.id)
    }
  } catch {
    /* ignore */
  }
}

function onFileChange(e: Event) {
  const input = e.target as HTMLInputElement
  const f = input.files?.[0]
  if (!f) return
  file.value = f
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value)
  previewUrl.value = URL.createObjectURL(f)
}

function startPoll(id: number) {
  stopPoll()
  pollTimer = window.setInterval(async () => {
    try {
      const latest = await api.get(`/api/videos/${id}/score`)
      video.value = latest
      if (latest.score_status === 'done' || latest.score_status === 'failed') {
        stopPoll()
      }
    } catch (err: any) {
      error.value = err.message || '轮询失败'
    }
  }, 10000)
}

function stopPoll() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

async function submit() {
  error.value = ''
  if (!getUsername()) {
    error.value = '请先在右上角设置昵称'
    return
  }
  if (!file.value) {
    error.value = '请选择视频（最长 2 分钟）'
    return
  }
  uploading.value = true
  try {
    const form = new FormData()
    form.append('video', file.value)
    form.append('title', title.value)
    form.append('description', description.value)
    const res = await uploadForm('/api/videos/upload', form)
    video.value = res
    startPoll(res.id)
  } catch (err: any) {
    error.value = err.message || '上传失败'
  } finally {
    uploading.value = false
  }
}

async function publish() {
  if (!video.value) return
  try {
    video.value = await api.post(`/api/videos/${video.value.id}/publish`, {
      title: title.value || video.value.title,
      description: description.value || video.value.description,
    })
  } catch (err: any) {
    error.value = err.message || '发布失败'
  }
}

onMounted(loadQuota)
onBeforeUnmount(() => {
  stopPoll()
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value)
})
</script>

<template>
  <div class="mx-auto max-w-2xl space-y-6 animate-pop-in">
    <div>
      <h1 class="text-3xl font-extrabold text-brand-700">上传跳绳视频</h1>
      <p class="mt-2 text-brand-700/70">每天限 1 个，最长 2 分钟。上传后后台 AI 分析，前端每 10 秒自动刷新结果。</p>
    </div>

    <div v-if="quota && !quota.can_upload && !analyzing && !done" class="card border-candy/30 bg-candy/10">
      今日已上传过视频
      <RouterLink v-if="quota.today_video" :to="`/videos/${quota.today_video.id}`" class="ml-2 font-bold text-brand-600 underline">
        查看 #{{ quota.today_video.id }}
      </RouterLink>
    </div>

    <div v-if="!video || analyzing" class="card space-y-4">
      <label class="block">
        <span class="mb-1 block text-sm font-bold text-brand-700">标题</span>
        <input v-model="title" class="w-full rounded-2xl border border-brand-200 px-4 py-3" placeholder="我的跳绳挑战" />
      </label>
      <label class="block">
        <span class="mb-1 block text-sm font-bold text-brand-700">描述</span>
        <textarea v-model="description" rows="3" class="w-full rounded-2xl border border-brand-200 px-4 py-3" placeholder="可选" />
      </label>
      <label class="block">
        <span class="mb-1 block text-sm font-bold text-brand-700">视频文件</span>
        <input type="file" accept="video/*" class="w-full" :disabled="!!video" @change="onFileChange" />
      </label>
      <video v-if="previewUrl" :src="previewUrl" controls class="w-full rounded-2xl bg-black" />
      <p v-if="error" class="text-sm font-bold text-candy">{{ error }}</p>
      <button
        v-if="!video"
        class="btn-candy w-full"
        :disabled="uploading || (quota && !quota.can_upload)"
        @click="submit"
      >
        {{ uploading ? '上传中…' : '上传并开始分析' }}
      </button>
    </div>

    <div v-if="video" class="card space-y-4">
      <div class="flex items-center justify-between gap-2">
        <h2 class="text-xl font-extrabold text-brand-700">分析进度 #{{ video.id }}</h2>
        <span class="chip bg-brand-100 text-brand-700">
          {{ analyzing ? '分析中…' : video.score_status === 'done' ? '已完成' : video.score_status }}
        </span>
      </div>
      <div class="grid grid-cols-2 gap-3 text-sm">
        <div class="rounded-2xl bg-brand-50 p-3">
          <div class="text-brand-700/60">转码</div>
          <div class="font-extrabold text-brand-700">{{ video.media_status }}</div>
        </div>
        <div class="rounded-2xl bg-brand-50 p-3">
          <div class="text-brand-700/60">打分</div>
          <div class="font-extrabold text-brand-700">{{ video.score_status }}</div>
        </div>
      </div>
      <p v-if="analyzing" class="text-sm text-brand-700/70">后台正在处理，每 10 秒自动刷新…</p>
      <p v-if="video.media_error" class="text-sm text-candy">转码错误：{{ video.media_error }}</p>
      <p v-if="video.score_error" class="text-sm text-candy">分析错误：{{ video.score_error }}</p>

      <div v-if="done" class="space-y-4">
        <div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div class="rounded-2xl bg-white p-3 text-center shadow-sm">
            <div class="text-2xl font-extrabold text-brand-600">{{ video.jump_count }}</div>
            <div class="text-xs font-bold text-brand-700/60">总次数</div>
          </div>
          <div class="rounded-2xl bg-white p-3 text-center shadow-sm">
            <div class="text-2xl font-extrabold text-brand-600">{{ video.speed_per_min }}</div>
            <div class="text-xs font-bold text-brand-700/60">次/分钟</div>
          </div>
          <div class="rounded-2xl bg-white p-3 text-center shadow-sm">
            <div class="text-2xl font-extrabold text-candy">{{ video.fancy_count }}</div>
            <div class="text-xs font-bold text-brand-700/60">花式次数</div>
          </div>
          <div class="rounded-2xl bg-white p-3 text-center shadow-sm">
            <div class="text-2xl font-extrabold text-brand-600">{{ video.fancy_duration_sec }}s</div>
            <div class="text-xs font-bold text-brand-700/60">花式时长</div>
          </div>
        </div>
        <div class="text-center text-lg font-extrabold text-brand-700">综合分 {{ video.ai_score }}</div>
        <video v-if="video.video_url" :src="video.video_url" controls class="w-full rounded-2xl bg-black" />
        <div class="flex flex-wrap gap-3">
          <button v-if="!video.is_public" class="btn-primary" @click="publish">发布到广场</button>
          <span v-else class="chip bg-mint/20 text-mint">已公开</span>
          <RouterLink :to="`/videos/${video.id}`" class="btn-ghost">查看详情</RouterLink>
          <button class="btn-ghost" @click="router.push('/featured')">投稿编辑推荐</button>
        </div>
      </div>
    </div>
  </div>
</template>
