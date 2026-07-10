<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import { api, getUsername, type JumpVideo } from '../api/client'

const items = ref<JumpVideo[]>([])
const candidates = ref<(JumpVideo & { already_featured?: boolean })[]>([])
const canSubmit = ref(false)
const showDialog = ref(false)
const selectedId = ref<number | null>(null)
const msg = ref('')

async function load() {
  const res = await api.get('/api/featured', { page: 1, page_size: 48 })
  items.value = res.items || []
  if (getUsername()) {
    const st = await api.get('/api/featured/status')
    canSubmit.value = !!st.can_submit
  }
}

async function openSubmit() {
  if (!getUsername()) {
    alert('请先设置昵称')
    return
  }
  const res = await api.get('/api/featured/candidates')
  candidates.value = res.items || []
  showDialog.value = true
}

async function submit() {
  if (!selectedId.value) return
  try {
    await api.post('/api/featured/submissions', { video_id: selectedId.value })
    msg.value = '投稿成功，等待审核'
    showDialog.value = false
    canSubmit.value = false
  } catch (err: any) {
    alert(err.message || '投稿失败')
  }
}

onMounted(load)
</script>

<template>
  <div class="space-y-6 animate-pop-in">
    <div class="flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 class="text-3xl font-extrabold text-brand-700">编辑推荐</h1>
        <p class="mt-1 text-brand-700/70">精选跳绳作品，每 24 小时可投稿一次</p>
      </div>
      <button class="btn-candy" :disabled="!canSubmit" @click="openSubmit">投稿</button>
    </div>
    <p v-if="msg" class="chip bg-mint/20 text-mint">{{ msg }}</p>

    <div v-if="!items.length" class="card text-center text-brand-700/70">暂无编辑推荐</div>
    <div v-else class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      <RouterLink
        v-for="v in items"
        :key="v.id"
        :to="`/videos/${v.id}`"
        class="card !p-3 hover:scale-[1.01] transition"
      >
        <div class="aspect-video overflow-hidden rounded-2xl bg-brand-100">
          <img v-if="v.cover_url" :src="v.cover_url" class="h-full w-full object-cover" alt="" />
          <div v-else class="flex h-full items-center justify-center text-4xl">⭐</div>
        </div>
        <div class="mt-3 truncate font-extrabold text-brand-700">{{ v.title }}</div>
        <div class="text-xs text-brand-700/60">{{ v.jump_count ?? '-' }} 次 · {{ v.username }}</div>
      </RouterLink>
    </div>

    <div v-if="showDialog" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" @click.self="showDialog = false">
      <div class="card max-h-[80vh] w-full max-w-lg overflow-y-auto space-y-3">
        <h2 class="text-xl font-extrabold text-brand-700">选择要投稿的视频</h2>
        <p class="text-sm text-brand-700/70">需已公开且分析完成</p>
        <label
          v-for="c in candidates"
          :key="c.id"
          class="flex cursor-pointer items-center gap-3 rounded-2xl border border-brand-100 p-3"
          :class="c.already_featured ? 'opacity-50' : ''"
        >
          <input v-model="selectedId" type="radio" :value="c.id" :disabled="c.already_featured" />
          <div class="min-w-0 flex-1">
            <div class="truncate font-bold text-brand-700">{{ c.title }}</div>
            <div class="text-xs text-brand-700/60">
              #{{ c.id }} · {{ c.jump_count }} 次
              <span v-if="c.already_featured">（已在推荐）</span>
            </div>
          </div>
        </label>
        <div v-if="!candidates.length" class="text-sm text-brand-700/60">没有可投稿作品，请先发布到广场。</div>
        <div class="flex justify-end gap-2">
          <button class="btn-ghost" @click="showDialog = false">取消</button>
          <button class="btn-primary" :disabled="!selectedId" @click="submit">提交</button>
        </div>
      </div>
    </div>
  </div>
</template>
