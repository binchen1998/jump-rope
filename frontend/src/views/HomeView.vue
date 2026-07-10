<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import { api, type JumpVideo } from '../api/client'

const stats = ref({ public_count: 0, total_count: 0, today_count: 0 })
const featured = ref<JumpVideo[]>([])
const videos = ref<JumpVideo[]>([])
const sort = ref('latest')
const q = ref('')
const loading = ref(true)
const page = ref(1)
const total = ref(0)
const currentComp = ref<any>(null)

async function loadStats() {
  stats.value = await api.get('/api/videos/stats')
}

async function loadFeatured() {
  const res = await api.get('/api/featured/home', { limit: 8 })
  featured.value = res.items || []
}

async function loadPlaza() {
  loading.value = true
  try {
    const res = await api.get('/api/videos/public', {
      page: page.value,
      page_size: 24,
      sort: sort.value,
      q: q.value,
    })
    videos.value = res.items || []
    total.value = res.total || 0
  } finally {
    loading.value = false
  }
}

async function loadCurrentComp() {
  currentComp.value = await api.get('/api/competitions/current')
}

function setSort(s: string) {
  sort.value = s
  page.value = 1
  loadPlaza()
}

onMounted(async () => {
  await Promise.all([loadStats(), loadFeatured(), loadPlaza(), loadCurrentComp()])
})
</script>

<template>
  <div class="space-y-8 animate-pop-in">
    <section class="card overflow-hidden !p-0">
      <div class="bg-gradient-to-br from-brand-400 via-brand-500 to-candy px-6 py-10 text-white sm:px-10">
        <p class="text-sm font-bold uppercase tracking-widest text-white/80">Jump Rope</p>
        <h1 class="mt-2 text-3xl font-extrabold sm:text-4xl">跳绳广场</h1>
        <p class="mt-3 max-w-xl text-white/90">上传跳绳视频，AI 帮你数次数、算速度、识别花式，还能发布到广场和参加比赛。</p>
        <div class="mt-6 flex flex-wrap gap-3">
          <RouterLink to="/upload" class="btn bg-white text-brand-700 shadow-pop hover:bg-brand-50">上传视频</RouterLink>
          <RouterLink to="/competitions" class="btn bg-white/20 text-white hover:bg-white/30">去比赛</RouterLink>
        </div>
      </div>
      <div class="grid grid-cols-3 gap-2 px-4 py-4 text-center sm:px-8">
        <div>
          <div class="text-2xl font-extrabold text-brand-600">{{ stats.public_count }}</div>
          <div class="text-xs font-bold text-brand-700/70">公开作品</div>
        </div>
        <div>
          <div class="text-2xl font-extrabold text-brand-600">{{ stats.total_count }}</div>
          <div class="text-xs font-bold text-brand-700/70">全部上传</div>
        </div>
        <div>
          <div class="text-2xl font-extrabold text-candy">+{{ stats.today_count }}</div>
          <div class="text-xs font-bold text-brand-700/70">今日新增</div>
        </div>
      </div>
    </section>

    <section v-if="currentComp" class="card flex flex-wrap items-center justify-between gap-4">
      <div>
        <div class="chip bg-brand-100 text-brand-700">当前比赛</div>
        <h2 class="mt-2 text-xl font-extrabold text-brand-700">{{ currentComp.title }}</h2>
        <p class="text-sm text-brand-700/70">{{ currentComp.description || '快来投稿参赛吧' }}</p>
      </div>
      <RouterLink :to="`/competitions/${currentComp.id}`" class="btn-primary">查看比赛</RouterLink>
    </section>

    <section v-if="featured.length" class="space-y-3">
      <div class="flex items-center justify-between">
        <h2 class="text-xl font-extrabold text-brand-700">编辑推荐</h2>
        <RouterLink to="/featured" class="text-sm font-bold text-brand-600 hover:underline">全部</RouterLink>
      </div>
      <div class="flex gap-4 overflow-x-auto pb-2 no-scrollbar">
        <RouterLink
          v-for="v in featured"
          :key="v.id"
          :to="`/videos/${v.id}`"
          class="card min-w-[220px] max-w-[220px] !p-3 hover:scale-[1.02] transition"
        >
          <div class="aspect-video overflow-hidden rounded-2xl bg-brand-100">
            <img v-if="v.cover_url" :src="v.cover_url" class="h-full w-full object-cover" alt="" />
            <div v-else class="flex h-full items-center justify-center text-3xl">🪢</div>
          </div>
          <div class="mt-2 truncate font-bold text-brand-700">{{ v.title }}</div>
          <div class="text-xs text-brand-700/60">{{ v.jump_count ?? '-' }} 次 · {{ v.username }}</div>
        </RouterLink>
      </div>
    </section>

    <section class="space-y-4">
      <div class="flex flex-wrap items-center gap-2">
        <h2 class="mr-auto text-xl font-extrabold text-brand-700">项目广场</h2>
        <button
          v-for="s in [
            { k: 'latest', l: '最新' },
            { k: 'jumps', l: '次数' },
            { k: 'speed', l: '速度' },
            { k: 'score', l: '得分' },
          ]"
          :key="s.k"
          class="chip"
          :class="sort === s.k ? 'bg-brand-500 text-white' : 'bg-white/80 text-brand-700'"
          @click="setSort(s.k)"
        >
          {{ s.l }}
        </button>
      </div>
      <div class="flex gap-2">
        <input
          v-model="q"
          class="flex-1 rounded-2xl border border-brand-200 bg-white/90 px-4 py-3"
          placeholder="搜索标题 / 用户"
          @keyup.enter="page = 1; loadPlaza()"
        />
        <button class="btn-primary" @click="page = 1; loadPlaza()">搜索</button>
      </div>

      <div v-if="loading" class="text-center text-brand-700/60 py-10">加载中…</div>
      <div v-else-if="!videos.length" class="card text-center text-brand-700/70">还没有公开作品，去做第一个吧！</div>
      <div v-else class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        <RouterLink
          v-for="v in videos"
          :key="v.id"
          :to="`/videos/${v.id}`"
          class="card !p-3 hover:scale-[1.01] transition"
        >
          <div class="aspect-video overflow-hidden rounded-2xl bg-brand-100">
            <img v-if="v.cover_url" :src="v.cover_url" class="h-full w-full object-cover" alt="" />
            <div v-else class="flex h-full items-center justify-center text-4xl">🪢</div>
          </div>
          <div class="mt-3 truncate font-extrabold text-brand-700">{{ v.title }}</div>
          <div class="mt-1 flex flex-wrap gap-2 text-xs font-bold text-brand-700/70">
            <span class="chip bg-brand-100">{{ v.jump_count ?? '-' }} 次</span>
            <span class="chip bg-sky/20 text-sky-700">{{ v.speed_per_min ?? '-' }}/分</span>
            <span v-if="v.fancy_count" class="chip bg-candy/15 text-candy">花式 {{ v.fancy_count }}</span>
          </div>
          <div class="mt-2 text-xs text-brand-700/50">{{ v.username }}</div>
        </RouterLink>
      </div>

      <div v-if="total > 24" class="flex justify-center gap-3">
        <button class="btn-ghost" :disabled="page <= 1" @click="page--; loadPlaza()">上一页</button>
        <span class="chip bg-white/80">{{ page }}</span>
        <button class="btn-ghost" :disabled="page * 24 >= total" @click="page++; loadPlaza()">下一页</button>
      </div>
    </section>
  </div>
</template>
