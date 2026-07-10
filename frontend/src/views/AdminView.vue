<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import { ADMIN_TOKEN_KEY, api } from '../api/client'

const route = useRoute()
const router = useRouter()

const tab = computed(() => (route.params.tab as string) || 'competitions')
const token = ref(localStorage.getItem(ADMIN_TOKEN_KEY) || '')
const username = ref('admin')
const password = ref('')
const loginError = ref('')

const competitions = ref<any[]>([])
const selectedCompId = ref<number | null>(null)
const entries = ref<any[]>([])
const videos = ref<any[]>([])
const submissions = ref<any[]>([])
const featured = ref<any[]>([])
const subStatus = ref('pending')

const form = ref({
  title: '',
  description: '',
  start_date: '',
  submission_deadline: '',
  end_date: '',
  is_published: true,
})

const isLoggedIn = computed(() => !!token.value)

async function login() {
  loginError.value = ''
  try {
    const res = await api.post('/api/admin/login', {
      username: username.value,
      password: password.value,
    })
    token.value = res.token
    localStorage.setItem(ADMIN_TOKEN_KEY, res.token)
  } catch (err: any) {
    loginError.value = err.message || '登录失败'
  }
}

function logout() {
  token.value = ''
  localStorage.removeItem(ADMIN_TOKEN_KEY)
}

function setTab(t: string) {
  router.push(`/admin/${t}`)
}

async function loadCompetitions() {
  const res = await api.get('/api/admin/competitions', undefined, true)
  competitions.value = res.items || []
}

async function createCompetition() {
  try {
    await api.post('/api/admin/competitions', form.value, true)
    form.value = {
      title: '',
      description: '',
      start_date: '',
      submission_deadline: '',
      end_date: '',
      is_published: true,
    }
    await loadCompetitions()
  } catch (err: any) {
    alert(err.message || '创建失败')
  }
}

async function togglePublish(c: any) {
  await api.put(`/api/admin/competitions/${c.id}`, { is_published: !c.is_published }, true)
  await loadCompetitions()
}

async function settle(c: any) {
  if (!confirm('确认立即结算？')) return
  await api.post(`/api/admin/competitions/${c.id}/settle`, {}, true)
  await loadCompetitions()
}

async function selectComp(id: number) {
  selectedCompId.value = id
  const res = await api.get(`/api/admin/competitions/${id}/entries`, undefined, true)
  entries.value = res.items || []
}

async function removeEntry(entryId: number) {
  const reason = prompt('移出原因') || ''
  await api.put(`/api/admin/competitions/entries/${entryId}/remove`, { reason }, true)
  if (selectedCompId.value) await selectComp(selectedCompId.value)
}

async function loadVideos() {
  const res = await api.get('/api/admin/videos', { page: 1, page_size: 50 }, true)
  videos.value = res.items || []
}

async function moderate(v: any, patch: any) {
  Object.assign(v, await api.put(`/api/admin/videos/${v.id}`, patch, true))
}

async function loadSubmissions() {
  const res = await api.get('/api/admin/featured-submissions', { status: subStatus.value }, true)
  submissions.value = res.items || []
}

async function review(subId: number, status: 'approved' | 'rejected') {
  let reject_reason = ''
  if (status === 'rejected') reject_reason = prompt('拒绝原因') || ''
  await api.put(`/api/admin/featured-submissions/${subId}/review`, { status, reject_reason }, true)
  await loadSubmissions()
  await loadFeatured()
}

async function loadFeatured() {
  const res = await api.get('/api/admin/featured', undefined, true)
  featured.value = res.items || []
}

async function addFeatured() {
  const raw = prompt('输入视频 ID')
  if (!raw) return
  try {
    await api.post('/api/admin/featured', { video_id: Number(raw) }, true)
    await loadFeatured()
  } catch (err: any) {
    alert(err.message || '添加失败')
  }
}

async function removeFeatured(id: number) {
  await api.del(`/api/admin/featured/${id}`, true)
  await loadFeatured()
}

async function bootstrap() {
  if (!isLoggedIn.value) return
  if (tab.value === 'competitions') await loadCompetitions()
  if (tab.value === 'videos') await loadVideos()
  if (tab.value === 'featured') {
    await loadSubmissions()
    await loadFeatured()
  }
}

watch(tab, () => bootstrap())
onMounted(bootstrap)
</script>

<template>
  <div class="mx-auto max-w-6xl space-y-6">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <h1 class="text-3xl font-extrabold text-brand-700">Jump Rope 管理后台</h1>
      <div class="flex gap-2">
        <RouterLink to="/" class="btn-ghost">回前台</RouterLink>
        <button v-if="isLoggedIn" class="btn-ghost" @click="logout">退出</button>
      </div>
    </div>

    <div v-if="!isLoggedIn" class="card mx-auto max-w-md space-y-4">
      <h2 class="text-xl font-extrabold text-brand-700">管理员登录</h2>
      <label class="block">
        <span class="text-sm font-bold text-brand-700">用户名</span>
        <input v-model="username" class="mt-1 w-full rounded-2xl border border-brand-200 px-4 py-3" />
      </label>
      <label class="block">
        <span class="text-sm font-bold text-brand-700">密码</span>
        <input v-model="password" type="password" class="mt-1 w-full rounded-2xl border border-brand-200 px-4 py-3" @keyup.enter="login" />
      </label>
      <p v-if="loginError" class="text-sm text-candy">{{ loginError }}</p>
      <button class="btn-primary w-full" @click="login">登录</button>
      <p class="text-xs text-brand-700/50">默认 admin / coding61</p>
    </div>

    <template v-else>
      <div class="flex flex-wrap gap-2">
        <button
          v-for="t in [
            { k: 'competitions', l: '比赛' },
            { k: 'videos', l: '视频' },
            { k: 'featured', l: '编辑推荐' },
          ]"
          :key="t.k"
          class="chip"
          :class="tab === t.k ? 'bg-brand-500 text-white' : 'bg-white/80 text-brand-700'"
          @click="setTab(t.k)"
        >
          {{ t.l }}
        </button>
      </div>

      <div v-if="tab === 'competitions'" class="grid gap-6 lg:grid-cols-2">
        <div class="card space-y-3">
          <h2 class="text-lg font-extrabold text-brand-700">创建比赛</h2>
          <input v-model="form.title" class="w-full rounded-xl border border-brand-200 px-3 py-2" placeholder="标题" />
          <textarea v-model="form.description" rows="3" class="w-full rounded-xl border border-brand-200 px-3 py-2" placeholder="说明" />
          <label class="block text-sm">开始 <input v-model="form.start_date" type="date" class="ml-2 rounded-lg border px-2 py-1" /></label>
          <label class="block text-sm">投稿截止 <input v-model="form.submission_deadline" type="date" class="ml-2 rounded-lg border px-2 py-1" /></label>
          <label class="block text-sm">结束 <input v-model="form.end_date" type="date" class="ml-2 rounded-lg border px-2 py-1" /></label>
          <button class="btn-primary" @click="createCompetition">创建</button>
        </div>
        <div class="card space-y-3">
          <h2 class="text-lg font-extrabold text-brand-700">比赛列表</h2>
          <div v-for="c in competitions" :key="c.id" class="rounded-2xl border border-brand-100 p-3 space-y-2">
            <div class="font-extrabold text-brand-700">#{{ c.id }} {{ c.title }}</div>
            <div class="text-xs text-brand-700/60">{{ c.start_date }} → {{ c.end_date }} · {{ c.status }}</div>
            <div class="flex flex-wrap gap-2">
              <button class="btn-ghost !px-3 !py-1 text-sm" @click="selectComp(c.id)">参赛作品</button>
              <button class="btn-ghost !px-3 !py-1 text-sm" @click="togglePublish(c)">
                {{ c.is_published ? '下线' : '上线' }}
              </button>
              <button v-if="!c.is_settled" class="btn-ghost !px-3 !py-1 text-sm" @click="settle(c)">结算</button>
            </div>
          </div>
        </div>
        <div v-if="selectedCompId" class="card lg:col-span-2 space-y-3">
          <h2 class="text-lg font-extrabold text-brand-700">参赛作品 #{{ selectedCompId }}</h2>
          <div v-for="e in entries" :key="e.id" class="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-brand-100 p-3">
            <div>
              <div class="font-bold text-brand-700">{{ e.username }} · 视频 #{{ e.video_id }} · {{ e.status }}</div>
              <div class="text-xs text-brand-700/60">票数 {{ e.votes }} · {{ e.video?.title }}</div>
            </div>
            <button v-if="e.status === 'active'" class="btn-ghost !px-3 !py-1 text-sm text-candy" @click="removeEntry(e.id)">
              移出
            </button>
          </div>
        </div>
      </div>

      <div v-else-if="tab === 'videos'" class="card space-y-3">
        <h2 class="text-lg font-extrabold text-brand-700">全站视频</h2>
        <div v-for="v in videos" :key="v.id" class="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-brand-100 p-3">
          <div>
            <div class="font-bold text-brand-700">#{{ v.id }} {{ v.title }} · {{ v.username }}</div>
            <div class="text-xs text-brand-700/60">
              {{ v.score_status }} · {{ v.jump_count ?? '-' }} 次 ·
              {{ v.is_public ? '公开' : '私密' }} ·
              {{ v.is_approved ? '过审' : '下架' }}
            </div>
          </div>
          <div class="flex gap-2">
            <button class="btn-ghost !px-3 !py-1 text-sm" @click="moderate(v, { is_public: !v.is_public })">
              {{ v.is_public ? '取消公开' : '公开' }}
            </button>
            <button class="btn-ghost !px-3 !py-1 text-sm" @click="moderate(v, { is_approved: !v.is_approved })">
              {{ v.is_approved ? '下架' : '过审' }}
            </button>
          </div>
        </div>
      </div>

      <div v-else class="grid gap-6 lg:grid-cols-2">
        <div class="card space-y-3">
          <div class="flex items-center justify-between">
            <h2 class="text-lg font-extrabold text-brand-700">投稿审核</h2>
            <select v-model="subStatus" class="rounded-lg border px-2 py-1" @change="loadSubmissions">
              <option value="pending">待审核</option>
              <option value="approved">已通过</option>
              <option value="rejected">已拒绝</option>
            </select>
          </div>
          <div v-for="s in submissions" :key="s.id" class="rounded-xl border border-brand-100 p-3 space-y-2">
            <div class="font-bold text-brand-700">#{{ s.id }} 视频 {{ s.video_id }} · {{ s.username }}</div>
            <div class="text-xs text-brand-700/60">{{ s.video?.title }} · {{ s.status }}</div>
            <div v-if="s.status === 'pending'" class="flex gap-2">
              <button class="btn-primary !px-3 !py-1 text-sm" @click="review(s.id, 'approved')">通过</button>
              <button class="btn-ghost !px-3 !py-1 text-sm text-candy" @click="review(s.id, 'rejected')">拒绝</button>
            </div>
          </div>
          <div v-if="!submissions.length" class="text-sm text-brand-700/60">暂无</div>
        </div>
        <div class="card space-y-3">
          <div class="flex items-center justify-between">
            <h2 class="text-lg font-extrabold text-brand-700">当前编辑推荐</h2>
            <button class="btn-ghost !px-3 !py-1 text-sm" @click="addFeatured">手动添加</button>
          </div>
          <div v-for="f in featured" :key="f.featured_id" class="flex items-center justify-between rounded-xl border border-brand-100 p-3">
            <div>
              <div class="font-bold text-brand-700">#{{ f.id }} {{ f.title }}</div>
              <div class="text-xs text-brand-700/60">{{ f.username }} · {{ f.featured_source }}</div>
            </div>
            <button class="btn-ghost !px-3 !py-1 text-sm text-candy" @click="removeFeatured(f.featured_id)">移除</button>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
