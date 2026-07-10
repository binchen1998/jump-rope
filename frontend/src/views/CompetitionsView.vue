<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import { api } from '../api/client'

const items = ref<any[]>([])
const status = ref('all')

const statusLabel: Record<string, string> = {
  upcoming: '即将开始',
  live: '进行中',
  settling: '结算中',
  ended: '已结束',
}

async function load() {
  const res = await api.get('/api/competitions', status.value === 'all' ? {} : { status: status.value })
  items.value = res.items || []
}

function setStatus(s: string) {
  status.value = s
  load()
}

onMounted(load)
</script>

<template>
  <div class="space-y-6 animate-pop-in">
    <div>
      <h1 class="text-3xl font-extrabold text-brand-700">跳绳比赛</h1>
      <p class="mt-1 text-brand-700/70">投稿参赛，同学投票，决出排名</p>
    </div>

    <div class="flex flex-wrap gap-2">
      <button
        v-for="s in [
          { k: 'all', l: '全部' },
          { k: 'live', l: '进行中' },
          { k: 'upcoming', l: '即将开始' },
          { k: 'ended', l: '已结束' },
        ]"
        :key="s.k"
        class="chip"
        :class="status === s.k ? 'bg-brand-500 text-white' : 'bg-white/80 text-brand-700'"
        @click="setStatus(s.k)"
      >
        {{ s.l }}
      </button>
    </div>

    <div v-if="!items.length" class="card text-center text-brand-700/70">暂无比赛</div>
    <div v-else class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <RouterLink
        v-for="c in items"
        :key="c.id"
        :to="`/competitions/${c.id}`"
        class="card hover:scale-[1.01] transition space-y-2"
      >
        <div class="flex items-center gap-2">
          <span class="chip bg-brand-100 text-brand-700">{{ statusLabel[c.status] || c.status }}</span>
          <span v-if="c.submission_open" class="chip bg-mint/20 text-mint">可投稿</span>
        </div>
        <h2 class="text-xl font-extrabold text-brand-700">{{ c.title }}</h2>
        <p class="line-clamp-2 text-sm text-brand-700/70">{{ c.description || '暂无说明' }}</p>
        <div class="text-xs font-bold text-brand-700/50">
          {{ c.start_date }} → {{ c.end_date }}
        </div>
      </RouterLink>
    </div>
  </div>
</template>
