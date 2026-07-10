<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import { api, getUsername } from '../api/client'

const route = useRoute()
const comp = ref<any>(null)
const entries = ref<any[]>([])
const sort = ref('votes')
const error = ref('')
const showSubmit = ref(false)
const candidates = ref<any[]>([])
const selectedVideoId = ref<number | null>(null)
const votingId = ref<number | null>(null)

const statusLabel: Record<string, string> = {
  upcoming: '即将开始',
  live: '进行中',
  settling: '结算中',
  ended: '已结束',
}

const id = computed(() => Number(route.params.id))

async function loadComp() {
  comp.value = await api.get(`/api/competitions/${id.value}`)
}

async function loadEntries() {
  const res = await api.get(`/api/competitions/${id.value}/entries`, { sort: sort.value })
  entries.value = res.items || []
}

async function openSubmit() {
  if (!getUsername()) {
    alert('请先设置昵称')
    return
  }
  const res = await api.get(`/api/competitions/${id.value}/my-videos`)
  candidates.value = res.items || []
  showSubmit.value = true
}

async function submit() {
  if (!selectedVideoId.value) return
  try {
    await api.post(`/api/competitions/${id.value}/submit`, { video_id: selectedVideoId.value })
    showSubmit.value = false
    await loadEntries()
  } catch (err: any) {
    alert(err.message || '投稿失败')
  }
}

async function vote(entry: any) {
  if (!getUsername()) {
    alert('请先设置昵称')
    return
  }
  votingId.value = entry.id
  try {
    const res = await api.post(`/api/competitions/${id.value}/entries/${entry.id}/vote`)
    entry.my_voted = true
    entry.votes = res.votes
  } catch (err: any) {
    alert(err.message || '投票失败')
  } finally {
    votingId.value = null
  }
}

async function report(entry: any) {
  const reason = prompt('举报原因（可选）') || ''
  try {
    await api.post(`/api/competitions/${id.value}/entries/${entry.id}/report`, { reason })
    alert('已提交举报')
  } catch (err: any) {
    alert(err.message || '举报失败')
  }
}

onMounted(async () => {
  try {
    await loadComp()
    await loadEntries()
  } catch (err: any) {
    error.value = err.message || '加载失败'
  }
})
</script>

<template>
  <div v-if="error" class="card text-candy">{{ error }}</div>
  <div v-else-if="!comp" class="text-brand-700/60">加载中…</div>
  <div v-else class="space-y-6 animate-pop-in">
    <section class="card bg-gradient-to-br from-brand-400 to-candy text-white !border-0">
      <div class="flex flex-wrap items-start justify-between gap-4">
        <div>
          <span class="chip bg-white/20 text-white">{{ statusLabel[comp.status] || comp.status }}</span>
          <h1 class="mt-3 text-3xl font-extrabold">{{ comp.title }}</h1>
          <p class="mt-2 max-w-2xl text-white/90">{{ comp.description || '跳绳比赛' }}</p>
          <p class="mt-3 text-sm text-white/80">
            {{ comp.start_date }} → 投稿截止 {{ comp.submission_deadline }} → 结束 {{ comp.end_date }}
          </p>
        </div>
        <button v-if="comp.submission_open" class="btn bg-white text-brand-700" @click="openSubmit">投稿参赛</button>
      </div>
    </section>

    <div class="flex flex-wrap items-center gap-2">
      <h2 class="mr-auto text-xl font-extrabold text-brand-700">作品墙</h2>
      <template v-if="!comp.is_settled">
        <button
          class="chip"
          :class="sort === 'votes' ? 'bg-brand-500 text-white' : 'bg-white/80'"
          @click="sort = 'votes'; loadEntries()"
        >
          按票数
        </button>
        <button
          class="chip"
          :class="sort === 'latest' ? 'bg-brand-500 text-white' : 'bg-white/80'"
          @click="sort = 'latest'; loadEntries()"
        >
          按最新
        </button>
        <button
          class="chip"
          :class="sort === 'score' ? 'bg-brand-500 text-white' : 'bg-white/80'"
          @click="sort = 'score'; loadEntries()"
        >
          按得分
        </button>
      </template>
      <span v-else class="chip bg-brand-100">已结束，展示最终排名</span>
    </div>

    <div v-if="!entries.length" class="card text-center text-brand-700/70">还没有参赛作品</div>
    <div v-else class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <div v-for="e in entries" :key="e.id" class="card !p-3 space-y-3 relative">
        <div
          v-if="e.final_rank"
          class="absolute left-5 top-5 z-10 rounded-full bg-brand-500 px-3 py-1 text-sm font-extrabold text-white shadow-pop"
        >
          #{{ e.final_rank }}
        </div>
        <div class="aspect-video overflow-hidden rounded-2xl bg-brand-100">
          <video v-if="e.video?.video_url" :src="e.video.video_url" controls class="h-full w-full object-cover" />
          <img v-else-if="e.video?.cover_url" :src="e.video.cover_url" class="h-full w-full object-cover" alt="" />
          <div v-else class="flex h-full items-center justify-center text-4xl">🪢</div>
        </div>
        <div class="font-extrabold text-brand-700">{{ e.video?.title || e.username }}</div>
        <div class="flex flex-wrap gap-2 text-xs font-bold text-brand-700/70">
          <span class="chip bg-brand-100">{{ e.video?.jump_count ?? '-' }} 次</span>
          <span class="chip bg-white">票数 {{ e.votes }}</span>
          <span v-if="e.video?.ai_score != null" class="chip bg-candy/15 text-candy">分 {{ e.video.ai_score }}</span>
        </div>
        <div class="flex flex-wrap gap-2">
          <button
            class="btn-primary !px-3 !py-2 text-sm"
            :disabled="!comp.voting_open || e.my_voted || votingId === e.id"
            @click="vote(e)"
          >
            {{ e.my_voted ? '已投票' : votingId === e.id ? '投票中…' : '投票' }}
          </button>
          <button class="btn-ghost !px-3 !py-2 text-sm" @click="report(e)">举报</button>
        </div>
      </div>
    </div>

    <div v-if="showSubmit" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" @click.self="showSubmit = false">
      <div class="card max-h-[80vh] w-full max-w-lg overflow-y-auto space-y-3">
        <h2 class="text-xl font-extrabold text-brand-700">选择参赛视频</h2>
        <p class="text-sm text-brand-700/70">需已公开且分析完成，每场限 1 个</p>
        <label
          v-for="c in candidates"
          :key="c.id"
          class="flex cursor-pointer items-center gap-3 rounded-2xl border border-brand-100 p-3"
        >
          <input v-model="selectedVideoId" type="radio" :value="c.id" />
          <div class="min-w-0 flex-1">
            <div class="truncate font-bold text-brand-700">{{ c.title }}</div>
            <div class="text-xs text-brand-700/60">#{{ c.id }} · {{ c.jump_count }} 次</div>
          </div>
        </label>
        <div v-if="!candidates.length" class="text-sm text-brand-700/60">没有可投稿作品</div>
        <div class="flex justify-end gap-2">
          <button class="btn-ghost" @click="showSubmit = false">取消</button>
          <button class="btn-primary" :disabled="!selectedVideoId" @click="submit">确认投稿</button>
        </div>
      </div>
    </div>
  </div>
</template>
