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

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="applyFilters">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="`按${field}检索`" />
      </label>
      <button class="btn" type="submit" :disabled="loading">查询</button>
      <button class="btn ghost" type="button" :disabled="loading" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table" :aria-busy="loading">
      <thead>
        <tr>
          <th
            v-for="column in columns"
            :key="column"
            :class="{ sortable: isSortable(column), sorted: sortField === column }"
            @click="isSortable(column) && toggleSort(column)"
          >
            {{ column }}
            <span v-if="sortField === column" class="sort-indicator">
              {{ sortOrder === 'asc' ? '▲' : '▼' }}
            </span>
          </th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
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
        <tr v-if="!rows.length && loading">
          <td :colspan="columns.length + 1" class="empty-state">加载中…</td>
        </tr>
        <tr v-else-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">
            <template v-if="hasActiveFilters">
              没有符合条件的维修记录，可
              <button class="link" type="button" @click="resetFilters">清除筛选条件</button>
              后重试
            </template>
            <template v-else>暂无仪器维修数据，可先登记维修记录</template>
          </td>
        </tr>
      </tbody>
    </table>

    <div class="pager">
      <button class="btn" type="button" :disabled="isFirstPage || loading" @click="goPage(-1)">上一页</button>
      <span class="pager-info">第 {{ page }} / {{ totalPages }} 页</span>
      <button class="btn" type="button" :disabled="isLastPage || loading" @click="goPage(1)">下一页</button>
      <span v-if="isLastPage && total > 0" class="pager-hint">已到最后一页</span>
      <label class="pager-size">
        每页
        <select v-model.number="size" :disabled="loading" @change="changeSize">
          <option v-for="option in sizeOptions" :key="option" :value="option">{{ option }}</option>
        </select>
        条
      </label>
      <span v-if="loading" class="pager-hint">加载中…</span>
    </div>

    <footer class="page-foot">
      <span>共 {{ total }} 条仪器维修记录</span>
      <span v-if="noticeMessage" class="notice-text">{{ noticeMessage }}</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'
import { REPAIR_QUERY_DEFAULTS, useRepairQueryStore } from '@/stores/repairQuery'

type Row = Record<string, string | number | null>
interface StatItem {
  label: string
  value: number
}
interface PagePayload {
  items?: Row[]
  total?: number
  page?: number
  stats?: StatItem[]
}

const ENDPOINT = '/api/equipment_repair'
const columns = ["维修编号", "仪器编号", "故障描述", "报修人", "报修日期", "维修单位", "修复日期", "维修状态"]
const actions = ["派工维修", "确认修复", "标记报废"]
const statuses = ["已报修", "维修中", "已修复", "无法修复"]
const sortableFields = ["维修编号", "仪器编号", "故障描述", "报修人"]
const filterFields = sortableFields
const FILTER_PARAM_MAP: Record<string, string> = {
  维修编号: 'repair_no',
  仪器编号: 'instrument_no',
  故障描述: 'fault',
  报修人: 'reporter',
}
const sizeOptions = [10, 20, 50]

const queryStore = useRepairQueryStore()

const rows = ref<Row[]>([])
const total = ref(0)
const stats = ref<StatItem[]>([
  { label: '待维修仪器', value: 0 },
  { label: '维修中仪器', value: 0 },
  { label: '本月修复', value: 0 },
])
const loading = ref(false)
const errorMessage = ref('')
const noticeMessage = ref('')
// 从会话里的查询条件恢复，离开页面再回来时列表保持原样
const filters = ref<Record<string, string>>({ ...queryStore.filters })
const sortField = ref(queryStore.sortField)
const sortOrder = ref<'asc' | 'desc'>(queryStore.sortOrder)
const page = ref(queryStore.page)
const size = ref(queryStore.size)

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / size.value)))
const isFirstPage = computed(() => page.value <= 1)
const isLastPage = computed(() => page.value >= totalPages.value)
const hasActiveFilters = computed(() =>
  filterFields.some((field) => (filters.value[field] ?? '').trim().length > 0),
)

function isSortable(column: string) {
  return sortableFields.includes(column)
}

function persistQuery() {
  queryStore.save({
    filters: { ...filters.value },
    sortField: sortField.value,
    sortOrder: sortOrder.value,
    page: page.value,
    size: size.value,
  })
}

function toggleSort(field: string) {
  // 排序字段互斥：新字段从升序开始，同字段升→降→取消
  if (sortField.value !== field) {
    sortField.value = field
    sortOrder.value = 'asc'
  } else if (sortOrder.value === 'asc') {
    sortOrder.value = 'desc'
  } else {
    sortField.value = ''
    sortOrder.value = 'asc'
  }
  page.value = 1
  noticeMessage.value = ''
  void reload()
}

function applyFilters() {
  page.value = 1
  noticeMessage.value = ''
  void reload()
}

function resetFilters() {
  filters.value = { ...REPAIR_QUERY_DEFAULTS.filters }
  sortField.value = REPAIR_QUERY_DEFAULTS.sortField
  sortOrder.value = REPAIR_QUERY_DEFAULTS.sortOrder
  page.value = REPAIR_QUERY_DEFAULTS.page
  size.value = REPAIR_QUERY_DEFAULTS.size
  noticeMessage.value = ''
  void reload()
}

function goPage(delta: number) {
  const next = page.value + delta
  if (next < 1 || next > totalPages.value || loading.value) {
    return
  }
  page.value = next
  noticeMessage.value = ''
  void reload()
}

function changeSize() {
  page.value = 1
  noticeMessage.value = ''
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  errorMessage.value = '维修记录登记入口尚未接入审批流'
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    if (!response.ok) {
      throw new Error('仪器维修动作未生效，请稍后重试')
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '仪器维修操作失败'
  }
}

async function readDetail(response: Response): Promise<string | null> {
  try {
    const body: unknown = await response.json()
    if (body && typeof body === 'object' && 'detail' in body && typeof body.detail === 'string') {
      return body.detail
    }
  } catch {
    // 非 JSON 响应，走默认提示
  }
  return null
}

// 请求序号：只有最新一次请求允许写回列表与指标，避免条件快速切换时新旧数据错位
let requestSeq = 0

async function reload() {
  const seq = ++requestSeq
  loading.value = true
  errorMessage.value = ''
  const params = new URLSearchParams()
  for (const field of filterFields) {
    const value = (filters.value[field] ?? '').trim()
    if (value) {
      params.set(FILTER_PARAM_MAP[field], value)
    }
  }
  if (sortField.value) {
    params.set('sort', sortField.value)
    params.set('order', sortOrder.value)
  }
  params.set('page', String(page.value))
  params.set('size', String(size.value))
  try {
    const response = await request(`${ENDPOINT}?${params.toString()}`)
    if (!response.ok) {
      const detail = await readDetail(response)
      throw new Error(detail ?? '维修记录列表读取失败')
    }
    const payload = (await response.json()) as PagePayload
    if (seq !== requestSeq) {
      return
    }
    // 列表、总数、统计卡片来自同一次响应，一起替换，不会短暂错位
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
    stats.value = payload.stats ?? stats.value
    if (typeof payload.page === 'number' && payload.page !== page.value) {
      page.value = payload.page
      noticeMessage.value = `页码超出范围，已回到第 ${payload.page} 页`
    }
    persistQuery()
  } catch (error) {
    if (seq !== requestSeq) {
      return
    }
    errorMessage.value = error instanceof Error ? error.message : '仪器维修列表读取失败'
  } finally {
    if (seq === requestSeq) {
      loading.value = false
    }
  }
}

onMounted(reload)
</script>
