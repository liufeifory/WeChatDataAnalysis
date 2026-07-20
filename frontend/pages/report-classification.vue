<template>
  <div class="h-full min-h-0 flex flex-col overflow-hidden">
    <div class="border-b shrink-0 px-5 py-4" style="border-color: var(--sidebar-rail-border);">
      <div>
        <h1 class="text-[17px] font-semibold" style="color: var(--sidebar-rail-icon-active-color);">日报归类</h1>
        <p class="mt-0.5 text-[12px]" style="color: var(--sidebar-rail-icon-color);">
          手工维护哪些会话属于客户、内部工作或忽略，优先于 AI 判断
        </p>
      </div>
    </div>

    <div class="flex-1 overflow-y-auto px-5 py-4 space-y-6">
      <div v-if="loading" class="text-[13px]" style="color: var(--sidebar-rail-icon-color);">加载中...</div>
      <div v-else>
        <div v-if="errorMessage" class="rounded-lg border px-3 py-2 text-[12px]" style="border-color: #fecaca; background: #fef2f2; color: #b91c1c;">
          {{ errorMessage }}
        </div>
        <div v-if="successMessage" class="rounded-lg border px-3 py-2 text-[12px]" style="border-color: #bbf7d0; background: #f0fdf4; color: #166534;">
          {{ successMessage }}
        </div>

        <div class="rounded-xl border p-4" style="border-color: var(--sidebar-rail-border); background: var(--sidebar-rail-bg);">
          <div class="flex items-center justify-between mb-3">
            <h2 class="text-[14px] font-semibold" style="color: var(--sidebar-rail-icon-active-color);">客户列表</h2>
            <button
              type="button"
              class="rounded-lg px-3 py-1.5 text-[12px] font-medium text-white bg-[#07C160] hover:bg-[#06AD56] transition"
              @click="addCustomer"
            >新增客户</button>
          </div>
          <div class="space-y-2">
            <div v-for="item in customers" :key="item.id || item._tmpKey" class="flex items-center gap-2">
              <input
                v-model="item.name"
                type="text"
                class="flex-1 rounded border px-3 py-2 text-[13px] outline-none"
                :style="{ borderColor: 'var(--sidebar-rail-border)', color: 'var(--sidebar-rail-icon-active-color)', backgroundColor: 'white' }"
                placeholder="客户名称"
              />
              <button type="button" class="text-[12px] text-red-500" @click="removeCustomer(item.id || item._tmpKey)">删除</button>
            </div>
          </div>
          <div class="mt-3">
            <button
              type="button"
              class="rounded-lg px-3 py-1.5 text-[12px] font-medium text-white bg-[#07C160] hover:bg-[#06AD56] transition disabled:opacity-40"
              :disabled="savingCustomers"
              @click="saveCustomers"
            >{{ savingCustomers ? '保存中...' : '保存客户列表' }}</button>
          </div>
        </div>

        <div class="rounded-xl border p-4" style="border-color: var(--sidebar-rail-border); background: var(--sidebar-rail-bg);">
          <div class="flex items-center justify-between mb-3">
            <h2 class="text-[14px] font-semibold" style="color: var(--sidebar-rail-icon-active-color);">归类规则</h2>
            <div class="flex items-center gap-2">
              <span class="text-[11px]" style="color: var(--sidebar-rail-icon-color);">{{ rules.length }} 条</span>
            </div>
          </div>

          <!-- Batched Add -->
          <div class="rounded-lg border mb-3 p-3" :style="{ borderColor: 'var(--sidebar-rail-border)', background: 'var(--sidebar-rail-bg)' }">
            <div class="flex items-center justify-between mb-2">
              <span class="text-[12px] font-medium" style="color: var(--sidebar-rail-icon-active-color);">批量添加</span>
            </div>
            <div class="grid grid-cols-1 md:grid-cols-4 gap-2 mb-2">
              <div>
                <label class="block text-[11px] mb-0.5" style="color: var(--sidebar-rail-icon-color);">搜索关键词</label>
                <input
                  v-model="batchKeyword"
                  type="text"
                  class="w-full rounded border px-2 py-1.5 text-[12px] outline-none"
                  :style="{ borderColor: 'var(--sidebar-rail-border)', color: 'var(--sidebar-rail-icon-active-color)', backgroundColor: 'white' }"
                  placeholder="如: 医院 / 绍兴 / PACS"
                  @input="batchKeywordChanged"
                />
              </div>
              <div>
                <label class="block text-[11px] mb-0.5" style="color: var(--sidebar-rail-icon-color);">分类</label>
                <select
                  v-model="batchCategory"
                  class="w-full rounded border px-2 py-1.5 text-[12px] outline-none"
                  :style="{ borderColor: 'var(--sidebar-rail-border)', color: 'var(--sidebar-rail-icon-active-color)', backgroundColor: 'white' }"
                >
                  <option value="customer">客户</option>
                  <option value="internal">内部工作</option>
                  <option value="ignore">忽略</option>
                </select>
              </div>
              <div v-if="batchCategory === 'customer'">
                <label class="block text-[11px] mb-0.5" style="color: var(--sidebar-rail-icon-color);">绑定客户</label>
                <select
                  v-model="batchCustomerId"
                  class="w-full rounded border px-2 py-1.5 text-[12px] outline-none"
                  :style="{ borderColor: 'var(--sidebar-rail-border)', color: 'var(--sidebar-rail-icon-active-color)', backgroundColor: 'white' }"
                >
                  <option value="">请选择客户</option>
                  <option v-for="item in customers" :key="item.id || item._tmpKey" :value="item.id">{{ item.name }}</option>
                </select>
              </div>
            </div>
            <div v-if="batchKeyword.trim()" class="mb-2">
              <div class="rounded border max-h-[160px] overflow-y-auto" :style="{ borderColor: 'var(--sidebar-rail-border)' }">
                <div v-for="item in batchFilteredCandidates" :key="item.username"
                  class="flex items-center gap-2 px-2.5 py-1.5 text-[12px] border-b cursor-pointer transition"
                  :class="batchSelected[item.username] ? 'bg-[#e6f7e6]' : 'hover:bg-[#f5f5f5]'"
                  :style="{ borderColor: 'var(--sidebar-rail-border)', color: 'var(--sidebar-rail-icon-active-color)' }"
                  @click="toggleBatchItem(item.username)"
                >
                  <input type="checkbox" :checked="!!batchSelected[item.username]" class="shrink-0" />
                  <span class="truncate">{{ item.display_name }} ({{ item.username }})</span>
                </div>
              </div>
              <p class="mt-1 text-[11px]" style="color: var(--sidebar-rail-icon-color);">
                已选 {{ Object.keys(batchSelected).length }} / {{ batchFilteredCandidates.length }} 个
              </p>
            </div>
            <div>
              <button
                type="button"
                class="rounded-lg px-3 py-1.5 text-[12px] font-medium text-white bg-[#07C160] hover:bg-[#06AD56] transition disabled:opacity-40"
                :disabled="Object.keys(batchSelected).length === 0 || batchSaving"
                @click="batchAddRules"
              >{{ batchSaving ? '添加中...' : `批量添加所选 (${Object.keys(batchSelected).length})` }}</button>
            </div>
          </div>

          <div class="space-y-2">
            <div v-for="rule in rules" :key="rule.id" class="rounded-lg border px-3 py-2" :style="{ borderColor: 'var(--sidebar-rail-border)' }">
              <div class="flex items-center justify-between gap-2">
                <div class="flex items-center gap-2 min-w-0 flex-1">
                  <span class="text-[13px] truncate" :style="{ color: 'var(--sidebar-rail-icon-active-color)' }">
                    {{ rule.display_name || rule.match_value || '未选择会话' }}
                  </span>
                  <span class="shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium leading-none"
                    :class="categoryBadgeClass(rule.category)"
                  >{{ categoryLabel(rule.category) }}</span>
                  <span v-if="rule.category === 'customer' && rule.customer_name" class="text-[11px] shrink-0 text-amber-600">
                    → {{ rule.customer_name }}
                  </span>
                </div>
                <div class="flex items-center gap-1 shrink-0">
                  <button type="button" class="text-[11px] text-red-500 px-1" @click="removeRule(rule)">×</button>
                </div>
              </div>
            </div>
          </div>

          <!-- Edit Dialog -->
          <Teleport to="body">
            <div v-if="editingRule" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
              @click.self="editingRule = null">
              <div class="rounded-xl border p-5 w-[480px] max-w-full max-h-[90vh] overflow-y-auto" style="background: var(--sidebar-rail-bg, #fff); border-color: var(--sidebar-rail-border);">
                <h3 class="text-[14px] font-semibold mb-4" style="color: var(--sidebar-rail-icon-active-color);">编辑归类规则</h3>

                <div class="space-y-3">
                  <div>
                    <label class="block text-[11px] mb-1" style="color: var(--sidebar-rail-icon-color);">
                      会话（当前：{{ editingRule?.display_name || editingRule?.match_value || '无' }}）
                    </label>
                    <input
                      v-model="editSearch"
                      type="text"
                      class="w-full rounded border px-3 py-2 text-[13px] outline-none mb-1"
                      :style="{ borderColor: 'var(--sidebar-rail-border)', color: 'var(--sidebar-rail-icon-active-color)', backgroundColor: 'white' }"
                      placeholder="搜索会话名称..."
                    />
                    <div class="rounded border overflow-y-auto max-h-[200px]" :style="{ borderColor: 'var(--sidebar-rail-border)' }">
                      <div v-if="editFilteredCandidates.length === 0" class="px-3 py-3 text-[12px] text-center"
                        style="color: var(--sidebar-rail-icon-color);">
                        请在搜索框输入关键词
                      </div>
                      <div
                        v-for="item in editFilteredCandidates"
                        :key="item.username"
                        class="px-3 py-1.5 text-[13px] cursor-pointer transition hover:bg-[#f0f0f0]"
                        :class="editRuleMatchValue === item.username ? 'bg-[#e6f7e6] text-green-700' : ''"
                        :style="{ color: editRuleMatchValue === item.username ? '#166534' : 'var(--sidebar-rail-icon-active-color, #333)' }"
                        @click="editRuleMatchValue = item.username; editRuleDisplayName = item.display_name; editRuleIsGroup = item.is_group"
                      >
                        {{ item.display_name }} ({{ item.username }})
                      </div>
                    </div>
                    <p class="mt-1 text-[11px]" style="color: var(--sidebar-rail-icon-color);">
                      显示 {{ editFilteredCandidates.length }} / {{ candidates.length }} 个会话
                    </p>
                    <p v-if="editRuleMatchValue && ruleMatchExists(editRuleMatchValue, editingRule)" class="mt-1 text-[11px] text-amber-600">该会话已存在其他规则</p>
                  </div>

                  <div>
                    <label class="block text-[11px] mb-1" style="color: var(--sidebar-rail-icon-color);">分类</label>
                    <select
                      v-model="editRuleCategory"
                      class="w-full rounded border px-3 py-2 text-[13px] outline-none"
                      :style="{ borderColor: 'var(--sidebar-rail-border)', color: 'var(--sidebar-rail-icon-active-color)', backgroundColor: 'white' }"
                    >
                      <option value="customer">客户</option>
                      <option value="internal">内部工作</option>
                      <option value="ignore">忽略</option>
                    </select>
                  </div>

                  <div v-if="editRuleCategory === 'customer'">
                    <label class="block text-[11px] mb-1" style="color: var(--sidebar-rail-icon-color);">绑定客户</label>
                    <select
                      v-model="editRuleCustomerId"
                      class="w-full rounded border px-3 py-2 text-[13px] outline-none"
                      :style="{ borderColor: 'var(--sidebar-rail-border)', color: 'var(--sidebar-rail-icon-active-color)', backgroundColor: 'white' }"
                    >
                      <option value="">请选择客户</option>
                      <option v-for="item in customers" :key="item.id || item._tmpKey" :value="item.id">{{ item.name }}</option>
                    </select>
                  </div>

                  <div>
                    <label class="block text-[11px] mb-1" style="color: var(--sidebar-rail-icon-color);">备注</label>
                    <input
                      v-model="editRuleNote"
                      type="text"
                      class="w-full rounded border px-3 py-2 text-[13px] outline-none"
                      :style="{ borderColor: 'var(--sidebar-rail-border)', color: 'var(--sidebar-rail-icon-active-color)', backgroundColor: 'white' }"
                      placeholder="可选备注"
                    />
                  </div>
                </div>

                <div class="mt-4 flex items-center justify-end gap-2">
                  <button type="button" class="rounded-lg px-3 py-1.5 text-[12px] border"
                    :style="{ borderColor: 'var(--sidebar-rail-border)', color: 'var(--sidebar-rail-icon-active-color)' }"
                    @click="editingRule = null">取消</button>
                  <button type="button"
                    class="rounded-lg px-3 py-1.5 text-[12px] font-medium text-white bg-[#07C160] hover:bg-[#06AD56] transition disabled:opacity-40"
                    :disabled="!canSaveEditRule"
                    @click="applyEditRule">保存</button>
                </div>
              </div>
            </div>
          </Teleport>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useApi } from '~/composables/useApi'

const {
  getDailyReportClassification,
  updateDailyReportClassificationCustomers,
  createDailyReportClassificationRule,
  updateDailyReportClassificationRule,
  deleteDailyReportClassificationRule,
  listDailyReportClassificationCandidates,
} = useApi()

const loading = ref(true)
const savingCustomers = ref(false)
const customers = ref([])
const rules = ref([])
const candidates = ref([])
const errorMessage = ref('')
const successMessage = ref('')

const flashSuccess = (text) => {
  successMessage.value = text
  setTimeout(() => {
    if (successMessage.value === text) successMessage.value = ''
  }, 2500)
}

const clearMessages = () => {
  errorMessage.value = ''
  successMessage.value = ''
}

const normalizeCustomers = (list) => {
  return (Array.isArray(list) ? list : []).map((item, idx) => ({
    ...item,
    _tmpKey: item?.id || `cust_tmp_${idx}_${Date.now()}`,
  }))
}

const loadAll = async () => {
  loading.value = true
  clearMessages()
  try {
    const [cfg, cand] = await Promise.all([
      getDailyReportClassification(),
      listDailyReportClassificationCandidates({ limit: 300 }),
    ])
    customers.value = normalizeCustomers(cfg?.customers)
    rules.value = Array.isArray(cfg?.rules) ? cfg.rules.map(item => ({ ...item })) : []
    candidates.value = Array.isArray(cand?.items) ? cand.items : []
  } catch (e) {
    errorMessage.value = e?.message || '加载归类配置失败'
  } finally {
    loading.value = false
  }
}

const addCustomer = () => {
  customers.value.push({ id: '', name: '', _tmpKey: `cust_new_${Date.now()}_${Math.random()}` })
}

const removeCustomer = (idOrKey) => {
  customers.value = customers.value.filter(item => (item.id || item._tmpKey) !== idOrKey)
}

const saveCustomers = async () => {
  savingCustomers.value = true
  clearMessages()
  try {
    const payload = customers.value.map(({ id, name }) => ({ id, name }))
    const res = await updateDailyReportClassificationCustomers(payload)
    customers.value = normalizeCustomers(res?.customers)
    await loadAll()
    flashSuccess('客户列表已保存')
  } catch (e) {
    errorMessage.value = e?.message || '保存客户列表失败'
  } finally {
    savingCustomers.value = false
  }
}

const addRule = () => {
  rules.value.push({
    id: `tmp_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
    match_type: 'username',
    match_value: '',
    display_name: '',
    is_group: false,
    category: 'internal',
    enabled: true,
    customer_id: '',
    customer_name: '',
    note: '',
  })
}

const editingRule = ref(null)
const editSearch = ref('')
const editRuleMatchValue = ref('')
const editRuleDisplayName = ref('')
const editRuleIsGroup = ref(false)
const editRuleCategory = ref('internal')
const editRuleCustomerId = ref('')
const editRuleNote = ref('')

const batchKeyword = ref('')
const batchCategory = ref('customer')
const batchCustomerId = ref('')
const batchSelected = ref({})
const batchSaving = ref(false)

const batchFilteredCandidates = computed(() => {
  const q = batchKeyword.value.trim().toLowerCase()
  if (!q) return []
  return candidates.value.filter(item =>
    (item.display_name || '').toLowerCase().includes(q) ||
    (item.username || '').toLowerCase().includes(q)
  )
})

const toggleBatchItem = (username) => {
  if (batchSelected.value[username]) {
    const next = { ...batchSelected.value }
    delete next[username]
    batchSelected.value = next
  } else {
    batchSelected.value = { ...batchSelected.value, [username]: true }
  }
}

const batchKeywordChanged = () => {
  batchSelected.value = {}
}

const batchAddRules = async () => {
  clearMessages()
  const selected = batchFilteredCandidates.value.filter(item => batchSelected.value[item.username])
  if (!selected.length) return
  batchSaving.value = true
  try {
    let created = 0
    const customerMap = {}
    for (const item of customers.value) {
      customerMap[item.id] = item.name
    }
    for (const item of selected) {
      try {
        await createDailyReportClassificationRule({
          match_type: 'username',
          match_value: item.username,
          display_name: item.display_name,
          is_group: item.is_group,
          category: batchCategory.value,
          customer_id: batchCategory.value === 'customer' ? batchCustomerId.value : '',
          customer_name: batchCategory.value === 'customer' ? (customerMap[batchCustomerId.value] || '') : '',
          note: '',
        })
        created++
      } catch (e) {
        // skip duplicate rule errors
      }
    }
    await loadAll()
    batchSelected.value = {}
    flashSuccess(`成功添加 ${created} 条规则`)
  } catch (e) {
    errorMessage.value = e?.message || '批量添加失败'
  } finally {
    batchSaving.value = false
  }
}

const editFilteredCandidates = computed(() => {
  const q = editSearch.value.trim().toLowerCase()
  if (!q) return candidates.value
  return candidates.value.filter(item =>
    (item.display_name || '').toLowerCase().includes(q) ||
    (item.username || '').toLowerCase().includes(q)
  )
})

const ruleMatchExists = (matchValue, excludeRule) => {
  if (!matchValue) return false
  return rules.value.some(item =>
    item !== excludeRule && String(item?.match_value || '').trim() === matchValue
  )
}

const canSaveEditRule = computed(() => {
  if (!editRuleMatchValue.value) return false
  if (ruleMatchExists(editRuleMatchValue.value, editingRule.value)) return false
  if (editRuleCategory.value === 'customer' && !editRuleCustomerId.value) return false
  return true
})

const categoryLabel = (cat) => {
  if (cat === 'customer') return '客户'
  if (cat === 'internal') return '内部工作'
  if (cat === 'ignore') return '忽略'
  return '其他'
}

const categoryBadgeClass = (cat) => {
  if (cat === 'customer') return 'bg-green-100 text-green-700 border-green-200'
  if (cat === 'internal') return 'bg-blue-100 text-blue-700 border-blue-200'
  if (cat === 'ignore') return 'bg-gray-100 text-gray-500 border-gray-200'
  return 'bg-gray-100 text-gray-500 border-gray-200'
}

const editRule = (rule) => {
  editingRule.value = rule
  editSearch.value = ''
  editRuleMatchValue.value = (rule.match_value || '')
  editRuleDisplayName.value = (rule.display_name || '')
  editRuleIsGroup.value = !!rule.is_group
  editRuleCategory.value = (rule.category || 'internal')
  editRuleCustomerId.value = (rule.customer_id || '')
  editRuleNote.value = (rule.note || '')
}

const applyEditRule = async () => {
  clearMessages()
  try {
    const found = candidates.value.find(item => item.username === editRuleMatchValue.value)
    const payload = {
      match_type: 'username',
      match_value: editRuleMatchValue.value,
      display_name: editRuleDisplayName.value || (found?.display_name || editRuleMatchValue.value),
      is_group: found?.is_group ?? editRuleIsGroup.value,
      category: editRuleCategory.value,
      enabled: true,
      customer_id: editRuleCategory.value === 'customer' ? editRuleCustomerId.value : '',
      customer_name: '',
      note: editRuleNote.value,
    }
    if (String(editingRule.value?.id || '').startsWith('tmp_')) {
      const res = await createDailyReportClassificationRule(payload)
      const idx = rules.value.findIndex(item => item.id === editingRule.value?.id)
      if (idx >= 0) rules.value[idx] = { ...(res?.rule || payload) }
      await loadAll()
      flashSuccess('规则已新增')
    } else if (editingRule.value?.id) {
      const res = await updateDailyReportClassificationRule(editingRule.value.id, payload)
      const idx = rules.value.findIndex(item => item.id === editingRule.value?.id)
      if (idx >= 0) rules.value[idx] = { ...(res?.rule || payload) }
      await loadAll()
      flashSuccess('规则已保存')
    }
    editingRule.value = null
  } catch (e) {
    errorMessage.value = e?.message || '保存规则失败'
  }
}

const removeRule = async (rule) => {
  clearMessages()
  try {
    if (String(rule.id || '').startsWith('tmp_')) {
      rules.value = rules.value.filter(item => item.id !== rule.id)
      return
    }
    await deleteDailyReportClassificationRule(rule.id)
    rules.value = rules.value.filter(item => item.id !== rule.id)
    flashSuccess('规则已删除')
  } catch (e) {
    errorMessage.value = e?.message || '删除规则失败'
  }
}

onMounted(() => {
  void loadAll()
})
</script>
