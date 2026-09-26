import { defineStore } from 'pinia'

/** 仪器维修列表的查询条件：离开页面再回来时从这里恢复。 */
export interface RepairQueryState {
  filters: Record<string, string>
  sortField: string
  sortOrder: 'asc' | 'desc'
  page: number
  size: number
}

export const REPAIR_QUERY_DEFAULTS: RepairQueryState = {
  filters: {},
  sortField: '',
  sortOrder: 'asc',
  page: 1,
  size: 20,
}

export const useRepairQueryStore = defineStore('repairQuery', {
  state: (): RepairQueryState => ({
    filters: { ...REPAIR_QUERY_DEFAULTS.filters },
    sortField: REPAIR_QUERY_DEFAULTS.sortField,
    sortOrder: REPAIR_QUERY_DEFAULTS.sortOrder,
    page: REPAIR_QUERY_DEFAULTS.page,
    size: REPAIR_QUERY_DEFAULTS.size,
  }),
  actions: {
    save(snapshot: RepairQueryState) {
      this.filters = { ...snapshot.filters }
      this.sortField = snapshot.sortField
      this.sortOrder = snapshot.sortOrder
      this.page = snapshot.page
      this.size = snapshot.size
    },
  },
})
