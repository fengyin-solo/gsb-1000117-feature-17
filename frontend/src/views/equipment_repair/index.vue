<template>
  <section class="page" data-module="equipment_repair">
    <header class="page-head">
      <div>
        <h2>仪器维修管理</h2>
        <p class="page-desc">维护维修记录，围绕维修编号、仪器编号、故障描述、报修人做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记维修记录</button>
        <button class="btn" type="button" @click="exportRows">导出仪器维修清单</button>
      </div>
    </header>

    <div class="stat-row" :aria-busy="loading ? 'true' : 'false'" title="指标始终统计全部维修记录，不随筛选条件变化">
      <article v-for="item in statCards" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ loading ? '…' : item.value }}</strong>
      </article>
    </div>

    <!-- 维修状态为互斥单选项：同一时刻只能保留一个状态，再点一次可取消回到“全部” -->
    <div class="status-tabs" role="group" aria-label="维修状态筛选（单选）">
      <button
        v-for="tab in statusTabs"
        :key="tab.value"
        type="button"
        class="status-tab"
        :class="{ active: status === tab.value }"
        :aria-pressed="status === tab.value"
        @click="toggleStatus(tab.value)"
      >
        {{ tab.label }}<span class="tab-count">{{ tab.count }}</span>
      </button>
    </div>

    <form class="filter-bar" @submit.prevent="applyFilters">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="draftFilters[field]" :placeholder="`按${field}检索`" />
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetAll">重置</button>
    </form>

    <table class="data-table" :aria-busy="loading ? 'true' : 'false'">
      <thead>
        <tr>
          <th
            v-for="column in columns"
            :key="column.key"
            :class="{ sortable: column.sortable, sorted: sortBy === column.key }"
            :aria-sort="sortBy === column.key ? (order === 'asc' ? 'ascending' : 'descending') : 'none'"
          >
            <button
              v-if="column.sortable"
              type="button"
              class="sort-btn"
              :title="`按${column.label}排序`"
              @click="toggleSort(column.key)"
            >
              {{ column.label }}
              <span class="sort-icon" aria-hidden="true">{{ sortIcon(column.key) }}</span>
            </button>
            <span v-else>{{ column.label }}</span>
          </th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="errorMessage" class="error-row">
          <td :colspan="columns.length + 1" class="state-cell" role="alert">
            <span class="error-text">{{ errorMessage }}</span>
            <button class="btn" type="button" @click="reload()">重新加载</button>
          </td>
        </tr>
        <tr v-else-if="loading && !hasLoaded">
          <td :colspan="columns.length + 1" class="state-cell muted">正在加载维修记录…</td>
        </tr>
        <tr v-else-if="!rows.length">
          <td :colspan="columns.length + 1" class="state-cell">
            <div class="state-block">
              <strong>{{ hasActiveCondition ? '没有符合当前条件的维修记录' : '暂无仪器维修数据' }}</strong>
              <span class="muted">
                {{ hasActiveCondition ? '可放宽检索词、切换维修状态，或重置后查看全部记录。' : '可先登记维修记录。' }}
              </span>
              <button v-if="hasActiveCondition" class="btn" type="button" @click="resetAll">清空条件查看全部</button>
            </div>
          </td>
        </tr>
        <template v-else>
          <tr v-for="row in rows" :key="String(row.id)">
            <td v-for="column in columns" :key="column.key">{{ displayValue(row, column.key) }}</td>
            <td class="row-actions">
              <button
                v-for="action in actions"
                :key="action"
                class="link"
                type="button"
                @click="runAction(action, row)"
              >
                {{ action }}
              </button>
            </td>
          </tr>
        </template>
      </tbody>
    </table>

    <footer class="page-foot pager-bar">
      <span class="pager-total">共 {{ total }} 条仪器维修记录</span>
      <div class="pager-controls">
        <button class="btn" type="button" :disabled="loading || page <= 1" @click="goToPage(page - 1)">上一页</button>
        <span class="pager-position" aria-live="polite">第 {{ page }} / {{ totalPages || 1 }} 页</span>
        <button
          class="btn"
          type="button"
          :disabled="loading || rows.length === 0 || page >= totalPages"
          @click="goToPage(page + 1)"
        >
          下一页
        </button>
        <label class="page-size">
          每页
          <select v-model.number="size" @change="onSizeChange">
            <option :value="10">10</option>
            <option :value="20">20</option>
            <option :value="50">50</option>
          </select>
          条
        </label>
        <span v-if="hasLoaded && !errorMessage && total > 0 && page >= totalPages" class="last-page-hint">
          已是最后一页（共 {{ totalPages }} 页）
        </span>
      </div>
    </footer>

    <!-- 结果变化的确定性反馈：空结果、翻到最后一页、互斥状态切换都通过这里向读屏播报 -->
    <p class="sr-only" role="status" aria-live="polite">{{ notice }}</p>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>
type SortOrder = 'asc' | 'desc'

interface Column {
  key: string
  label: string
  sortable: boolean
}

const ENDPOINT = '/api/equipment_repair'
const STORAGE_KEY = 'equipment_repair:list-state'
const columns: Column[] = [
  { key: '维修编号', label: '维修编号', sortable: true },
  { key: '仪器编号', label: '仪器编号', sortable: true },
  { key: '故障描述', label: '故障描述', sortable: true },
  { key: '报修人', label: '报修人', sortable: true },
  { key: '报修日期', label: '报修日期', sortable: false },
  { key: '维修单位', label: '维修单位', sortable: false },
  { key: '修复日期', label: '修复日期', sortable: false },
  { key: '维修状态', label: '维修状态', sortable: false },
]
const filterFields = ['维修编号', '仪器编号', '故障描述', '报修人']
const actions = ['派工维修', '确认修复', '标记报废']
const statusOptions = ['已报修', '维修中', '已修复', '无法修复']
const pageSizeOptions = [10, 20, 50]

interface ListState {
  filters: Record<string, string>
  status: string
  sortBy: string
  order: SortOrder
  page: number
  size: number
}

function createDraftFilters(): Record<string, string> {
  return Object.fromEntries(filterFields.map((field) => [field, '']))
}

function defaultState(): ListState {
  return { filters: {}, status: '', sortBy: '维修编号', order: 'asc', page: 1, size: 20 }
}

function restoreState(): ListState {
  const base = defaultState()
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    if (!raw) return base
    const saved = JSON.parse(raw) as Partial<ListState>
    if (saved.filters && typeof saved.filters === 'object') {
      base.filters = Object.fromEntries(
        filterFields
          .map((field) => [field, String(saved.filters?.[field] ?? '').trim()])
          .filter(([, value]) => value !== ''),
      )
    }
    if (typeof saved.status === 'string' && (saved.status === '' || statusOptions.includes(saved.status))) {
      base.status = saved.status
    }
    if (saved.sortBy && filterFields.includes(saved.sortBy)) base.sortBy = saved.sortBy
    if (saved.order === 'asc' || saved.order === 'desc') base.order = saved.order
    if (typeof saved.page === 'number' && saved.page >= 1) base.page = Math.floor(saved.page)
    if (pageSizeOptions.includes(Number(saved.size))) base.size = Number(saved.size)
  } catch {
    // 存储损坏时回落到默认条件，不影响列表可用。
  }
  return base
}

const initialState = restoreState()

// draftFilters 是输入框中的草稿；appliedFilters 是已提交并随请求生效的条件。
const draftFilters = reactive<Record<string, string>>(createDraftFilters())
const appliedFilters = ref<Record<string, string>>({})
const status = ref('')
const sortBy = ref('维修编号')
const order = ref<SortOrder>('asc')
const page = ref(1)
const size = ref(20)

Object.entries(initialState.filters).forEach(([field, value]) => {
  draftFilters[field] = value
})
appliedFilters.value = { ...initialState.filters }
status.value = initialState.status
sortBy.value = initialState.sortBy
order.value = initialState.order
page.value = initialState.page
size.value = initialState.size

const rows = ref<Row[]>([])
const total = ref(0)
const stats = ref<Record<string, number>>({})
const loading = ref(false)
const hasLoaded = ref(false)
const errorMessage = ref('')
const notice = ref('')
let requestSeq = 0

const totalPages = computed(() => (total.value > 0 ? Math.ceil(total.value / size.value) : 0))
const hasActiveCondition = computed(
  () => Object.values(appliedFilters.value).some((value) => value.trim() !== '') || status.value !== '',
)

const statCards = computed(() => [
  { label: '待维修仪器', value: stats.value['待维修仪器'] ?? 0 },
  { label: '维修中仪器', value: stats.value['维修中仪器'] ?? 0 },
  { label: '本月修复', value: stats.value['本月修复'] ?? 0 },
  { label: '无法修复', value: stats.value['无法修复'] ?? 0 },
])

const statusTabs = computed(() => [
  {
    label: '全部',
    value: '',
    count: statusOptions.reduce((sum, value) => sum + (statusCount(value) ?? 0), 0),
  },
  ...statusOptions.map((value) => ({ label: value, value, count: statusCount(value) })),
])

function statusCount(statusValue: string): number {
  if (statusValue === '已报修') return stats.value['待维修仪器'] ?? 0
  if (statusValue === '维修中') return stats.value['维修中仪器'] ?? 0
  return stats.value[statusValue] ?? 0
}

function displayValue(row: Row, key: string): string {
  const value = row[key]
  return value === null || value === undefined || value === '' ? '—' : String(value)
}

function sortIcon(columnKey: string): string {
  if (sortBy.value !== columnKey) return '↕'
  return order.value === 'asc' ? '↑' : '↓'
}

function persistState() {
  try {
    sessionStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        filters: appliedFilters.value,
        status: status.value,
        sortBy: sortBy.value,
        order: order.value,
        page: page.value,
        size: size.value,
      }),
    )
  } catch {
    // 隐私模式等场景下存储不可用时不阻断浏览。
  }
}

async function reload(announce = true) {
  const seq = ++requestSeq
  loading.value = true
  errorMessage.value = ''
  const params = new URLSearchParams()
  Object.entries(appliedFilters.value).forEach(([field, value]) => {
    if (value.trim()) params.set(field, value.trim())
  })
  if (status.value) params.set('status', status.value)
  params.set('sort_by', sortBy.value)
  params.set('order', order.value)
  params.set('page', String(page.value))
  params.set('size', String(size.value))

  try {
    const response = await request(`${ENDPOINT}?${params.toString()}`)
    if (!response.ok) {
      throw new Error(`维修记录列表读取失败（接口返回 ${response.status}）`)
    }
    const payload = (await response.json()) as {
      items?: Row[]
      total?: number
      stats?: Record<string, number>
    }
    // 只接受最后一次请求的结果：快速切换条件时，先发出的旧响应会被丢弃，
    // 保证列表数据、总数与指标始终对应同一组条件，不会短暂错位。
    if (seq !== requestSeq) return

    const nextRows = payload.items ?? []
    rows.value = nextRows
    total.value = payload.total ?? nextRows.length
    stats.value = payload.stats ?? {}

    // 条件切换后若落在超出范围的页码（例如数据被其他操作删除），收敛到最后一页再取一次。
    const maxPage = Math.max(1, Math.ceil(total.value / size.value))
    if (total.value > 0 && page.value > maxPage) {
      page.value = maxPage
      persistState()
      loading.value = false
      await reload(announce)
      return
    }

    persistState()
    if (announce) {
      if (total.value === 0) {
        notice.value = '当前条件下没有匹配的维修记录'
      } else if (page.value >= maxPage) {
        notice.value = `已到最后一页，共 ${maxPage} 页 ${total.value} 条记录`
      } else {
        notice.value = `第 ${page.value} 页，显示 ${nextRows.length} 条，共 ${total.value} 条记录`
      }
    }
  } catch (error) {
    if (seq !== requestSeq) return
    errorMessage.value = error instanceof Error ? error.message : '仪器维修列表读取失败'
    notice.value = errorMessage.value
  } finally {
    if (seq === requestSeq) {
      loading.value = false
      hasLoaded.value = true
    }
  }
}

function applyFilters() {
  // 以输入框草稿为准提交，提交后回到第 1 页；请求期间输入框不清空，当前条件始终可见。
  appliedFilters.value = Object.fromEntries(
    filterFields
      .map((field) => [field, draftFilters[field].trim()])
      .filter(([, value]) => value !== ''),
  )
  page.value = 1
  void reload()
}

function toggleStatus(value: string) {
  status.value = status.value === value ? '' : value
  page.value = 1
  notice.value = status.value ? `已切换为「${status.value}」状态，与其他状态互斥` : '已取消状态筛选，查看全部状态'
  void reload()
}

function toggleSort(columnKey: string) {
  if (sortBy.value === columnKey) {
    order.value = order.value === 'asc' ? 'desc' : 'asc'
  } else {
    // 排序列互斥：换列即放弃旧列，并默认从升序开始。
    sortBy.value = columnKey
    order.value = 'asc'
  }
  page.value = 1
  void reload()
}

function goToPage(target: number) {
  const maxPage = Math.max(1, totalPages.value)
  if (target < 1 || target > maxPage || target === page.value) return
  page.value = target
  void reload()
}

function onSizeChange() {
  if (!pageSizeOptions.includes(size.value)) size.value = 20
  page.value = 1
  void reload()
}

function resetAll() {
  // 重置后恢复默认：无条件、默认维修编号升序、第 1 页、每页 20 条。
  Object.keys(draftFilters).forEach((field) => {
    draftFilters[field] = ''
  })
  appliedFilters.value = {}
  status.value = ''
  sortBy.value = '维修编号'
  order.value = 'asc'
  page.value = 1
  size.value = 20
  notice.value = '已重置为默认条件：全部状态，按维修编号升序'
  try {
    sessionStorage.removeItem(STORAGE_KEY)
  } catch {
    // 忽略存储不可用。
  }
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  errorMessage.value = '维修记录登记入口尚未接入审批流'
  notice.value = errorMessage.value
}

async function runAction(action: string, row: Row) {
  notice.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    if (!response.ok) {
      throw new Error('仪器维修动作未生效，请稍后重试')
    }
    await reload(false)
    notice.value = `维修记录 ${row['维修编号'] ?? row.id} 已${action}`
  } catch (error) {
    const message = error instanceof Error ? error.message : '仪器维修操作失败'
    errorMessage.value = message
    notice.value = message
  }
}

onMounted(() => reload(false))
</script>

<style scoped>
.status-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.status-tab {
  border: 1px solid var(--border);
  background: #fff;
  border-radius: 999px;
  padding: 5px 14px;
  font-size: 13px;
  cursor: pointer;
  color: var(--muted);
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.status-tab .tab-count {
  font-size: 12px;
  background: #eef2f7;
  border-radius: 999px;
  padding: 0 7px;
  line-height: 18px;
}

.status-tab.active {
  background: var(--brand);
  border-color: var(--brand);
  color: #fff;
}

.status-tab.active .tab-count {
  background: rgba(255, 255, 255, 0.25);
}

.sort-btn {
  border: none;
  background: none;
  padding: 0;
  font: inherit;
  color: inherit;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

th.sorted .sort-btn {
  color: var(--brand);
  font-weight: 600;
}

.sort-icon {
  font-size: 12px;
  color: var(--muted);
}

th.sorted .sort-icon {
  color: var(--brand);
}

.state-cell {
  text-align: center;
  padding: 28px 12px;
}

.state-block {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.state-block .btn {
  margin-top: 4px;
}

.muted {
  color: var(--muted);
}

.error-row .state-cell {
  display: flex;
  gap: 12px;
  justify-content: center;
  align-items: center;
}

.pager-bar {
  align-items: center;
}

.pager-controls {
  display: flex;
  align-items: center;
  gap: 10px;
}

.pager-controls .btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.pager-position {
  min-width: 92px;
  text-align: center;
}

.page-size {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.page-size select {
  padding: 3px 4px;
}

.last-page-hint {
  color: var(--brand);
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
</style>
