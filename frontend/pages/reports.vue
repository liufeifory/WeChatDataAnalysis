<template>
  <div class="h-full min-h-0 flex flex-col overflow-hidden">
    <!-- header -->
    <div class="border-b shrink-0 px-5 py-4" style="border-color: var(--sidebar-rail-border);">
      <div class="flex items-center justify-between gap-4">
        <div>
          <h1 class="text-[17px] font-semibold" style="color: var(--sidebar-rail-icon-active-color);">AI 日报</h1>
          <p class="mt-0.5 text-[12px]" style="color: var(--sidebar-rail-icon-color);">每日 AI 分析聊天记录，识别客户沟通</p>
        </div>
        <div class="flex items-center gap-2 shrink-0">
          <button
            type="button"
            class="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[12px] font-medium border transition disabled:cursor-not-allowed disabled:opacity-40"
            :class="batchGenerating
              ? 'text-white bg-red-500 border-red-500 cursor-pointer'
              : ''"
            :style="!batchGenerating ? { borderColor: 'var(--sidebar-rail-border)', color: 'var(--sidebar-rail-icon-active-color)' } : {}"
            :disabled="false"
            @click="batchGenerating ? cancelBatchGenerate() : (showBatchPanel = !showBatchPanel)"
          >
            <svg v-if="batchGenerating" class="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
              <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
            </svg>
            <svg v-else class="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
              <path d="M4 4a2 2 0 00-2 2v1h16V6a2 2 0 00-2-2H4z" />
              <path fill-rule="evenodd" d="M18 9H2v5a2 2 0 002 2h12a2 2 0 002-2V9zM4 13a1 1 0 011-1h1a1 1 0 110 2H5a1 1 0 01-1-1zm5-1a1 1 0 100 2h1a1 1 0 100-2H9z" clip-rule="evenodd" />
            </svg>
            <span>{{ batchGenerating ? '停止' : '批量生成' }}</span>
          </button>
          <button
            type="button"
            class="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[12px] font-medium border transition disabled:cursor-not-allowed disabled:opacity-40"
            :class="generating
              ? 'text-white bg-blue-500 border-blue-500 cursor-wait'
              : 'text-white bg-[#07C160] border-[#07C160] hover:bg-[#06AD56]'"
            :disabled="isNaN(dateTs) || generating"
            @click="triggerGenerate"
          >
            <svg v-if="generating" class="h-3.5 w-3.5 animate-spin" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            <svg v-else class="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
              <path d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z" />
            </svg>
            <span>{{ generating ? '生成中...' : '立即生成' }}</span>
          </button>
        </div>
      </div>
    </div>

    <!-- date navigation -->
    <div class="border-b shrink-0" style="border-color: var(--sidebar-rail-border);">
      <div class="flex items-center justify-between px-5 py-2.5">
        <div class="flex items-center gap-2">
          <button
            type="button"
            class="rounded p-1 transition hover:opacity-70 disabled:opacity-30"
            style="color: var(--sidebar-rail-icon-color);"
            :disabled="generating"
            @click="goPrevDay"
          >
            <svg class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
              <path fill-rule="evenodd" d="M12.707 5.293a1 1 0 010 1.414L9.414 10l3.293 3.293a1 1 0 01-1.414 1.414l-4-4a1 1 0 010-1.414l4-4a1 1 0 011.414 0z" clip-rule="evenodd" />
            </svg>
          </button>
          <input
            type="date"
            :value="displayDate"
            :max="todayStr"
            class="rounded border px-2 py-1 text-[13px] outline-none"
            :style="{ backgroundColor: 'var(--sidebar-rail-bg)', borderColor: 'var(--sidebar-rail-border)', color: 'var(--sidebar-rail-icon-active-color)' }"
            @change="goDate($event.target.value)"
          />
          <button
            v-if="!isToday"
            type="button"
            class="rounded p-1 transition hover:opacity-70"
            style="color: var(--sidebar-rail-icon-color);"
            :disabled="generating"
            @click="goNextDay"
          >
            <svg class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
              <path fill-rule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clip-rule="evenodd" />
            </svg>
          </button>
          <span class="text-[13px] font-medium ml-1" style="color: var(--sidebar-rail-icon-active-color);">
            {{ displayLabel }}
          </span>
        </div>
        <div v-if="report" class="flex items-center gap-3 text-[11px]" style="color: var(--sidebar-rail-icon-color);">
          <span v-if="report.llm_model">模型: {{ report.llm_model }}</span>
          <span v-if="report.generated_at">生成于 {{ formatTime(report.generated_at) }}</span>
        </div>
      </div>
    </div>

    <!-- batch generate panel -->
    <div
      v-if="showBatchPanel"
      class="shrink-0 border-b px-5 py-3"
      style="border-color: var(--sidebar-rail-border); background: var(--sidebar-rail-bg);"
    >
      <div class="flex items-center gap-3">
        <div>
          <label class="block text-[11px] mb-0.5" style="color: var(--sidebar-rail-icon-color);">开始日期</label>
          <input
            v-model="batchStartDate"
            type="date"
            :max="batchEndDate || todayStr"
            :disabled="batchGenerating"
            class="rounded border px-2 py-1 text-[12px] outline-none disabled:opacity-40"
            :style="{ borderColor: 'var(--sidebar-rail-border)', color: 'var(--sidebar-rail-icon-active-color)', backgroundColor: 'white' }"
          />
        </div>
        <span class="mt-5" style="color: var(--sidebar-rail-icon-color);">→</span>
        <div>
          <label class="block text-[11px] mb-0.5" style="color: var(--sidebar-rail-icon-color);">结束日期</label>
          <input
            v-model="batchEndDate"
            type="date"
            :min="batchStartDate || ''"
            :max="todayStr"
            :disabled="batchGenerating"
            class="rounded border px-2 py-1 text-[12px] outline-none disabled:opacity-40"
            :style="{ borderColor: 'var(--sidebar-rail-border)', color: 'var(--sidebar-rail-icon-active-color)', backgroundColor: 'white' }"
          />
        </div>
        <div class="mt-5 flex items-center gap-2">
          <button
            type="button"
            class="rounded-lg px-3 py-1.5 text-[12px] font-medium text-white bg-[#07C160] hover:bg-[#06AD56] transition disabled:opacity-40"
            :disabled="batchGenerating || !batchStartDate || !batchEndDate"
            @click="startBatchGenerate"
          >
            {{ batchGenerating ? '生成中...' : '开始生成' }}
          </button>
          <span v-if="batchProgress" class="text-[11px]" style="color: var(--sidebar-rail-icon-color);">
            {{ batchProgress }}
          </span>
          <button
            type="button"
            :disabled="batchGenerating"
            class="rounded-lg px-2 py-1.5 text-[11px] transition disabled:opacity-30"
            style="color: var(--sidebar-rail-icon-color);"
            @click="showBatchPanel = false"
          >
            收起
          </button>
        </div>
      </div>
    </div>

    <!-- body -->
    <div class="flex-1 overflow-y-auto px-5 py-4">
      <!-- loading state -->
      <div v-if="loading" class="flex items-center justify-center py-20">
        <div class="flex flex-col items-center gap-3">
          <svg class="h-6 w-6 animate-spin" style="color: var(--sidebar-rail-icon-color);" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          <span class="text-[13px]" style="color: var(--sidebar-rail-icon-color);">加载中...</span>
        </div>
      </div>

      <!-- error state -->
      <div v-else-if="error" class="flex flex-col items-center justify-center py-20 gap-3">
        <svg class="h-10 w-10" style="color: var(--sidebar-rail-icon-color);" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
        </svg>
        <span class="text-[13px]" style="color: var(--sidebar-rail-icon-color);">{{ error }}</span>
        <button
          v-if="!report"
          type="button"
          class="rounded-lg px-4 py-2 text-[12px] font-medium text-white bg-[#07C160] hover:bg-[#06AD56] transition"
          :disabled="generating"
          @click="triggerGenerate"
        >
          {{ generating ? '生成中...' : '立即生成今日日报' }}
        </button>
      </div>

      <!-- empty / not generated -->
      <div v-else-if="!report" class="flex flex-col items-center justify-center py-20 gap-3">
        <svg class="h-10 w-10" style="color: var(--sidebar-rail-icon-color);" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
        <span class="text-[13px]" style="color: var(--sidebar-rail-icon-color);">
          该日日报尚未生成
        </span>
        <button
          type="button"
          class="rounded-lg px-4 py-2 text-[12px] font-medium text-white bg-[#07C160] hover:bg-[#06AD56] transition"
          :disabled="generating"
          @click="triggerGenerate"
        >
          {{ generating ? '生成中...' : '立即生成日报' }}
        </button>
      </div>

      <!-- report content -->
      <template v-else>
        <!-- summary stats -->
        <div class="mb-4 grid grid-cols-3 gap-3">
          <div class="rounded-lg border px-3.5 py-2.5" style="border-color: var(--sidebar-rail-border); background: var(--sidebar-rail-bg);">
            <div class="text-[20px] font-bold" style="color: var(--sidebar-rail-icon-active-color);">{{ localEntries.length }}</div>
            <div class="text-[11px] mt-0.5" style="color: var(--sidebar-rail-icon-color);">总对话</div>
          </div>
          <div class="rounded-lg border px-3.5 py-2.5" style="border-color: var(--sidebar-rail-border); background: var(--sidebar-rail-bg);">
            <div class="text-[20px] font-bold text-[#07C160]">{{ customerCount }}</div>
            <div class="text-[11px] mt-0.5" style="color: var(--sidebar-rail-icon-color);">客户沟通</div>
          </div>
          <div class="rounded-lg border px-3.5 py-2.5" style="border-color: var(--sidebar-rail-border); background: var(--sidebar-rail-bg);">
            <div class="text-[20px] font-bold" style="color: var(--sidebar-rail-icon-color);">{{ nonCustomerCount }}</div>
            <div class="text-[11px] mt-0.5" style="color: var(--sidebar-rail-icon-color);">其他</div>
          </div>
        </div>

        <!-- LLM status banner -->
        <div
          v-if="report && report.llm_configured != null"
          class="mb-3 rounded-lg border px-3 py-2 text-[11px] leading-relaxed"
          :class="report.llm_analyzed
            ? 'border-green-200 bg-green-50 text-green-800'
            : 'border-amber-200 bg-amber-50 text-amber-900'"
        >
          <template v-if="report.llm_analyzed">
            已通过 AI（{{ report.llm_model || '未知模型' }}）分析聊天记录，识别客户沟通。
            <template v-if="!report.llm_model">请在设置中配置大模型，以启用 AI 分析。</template>
          </template>
          <template v-else-if="report.llm_configured">
            AI 分析失败（大模型接口异常），所有条目标记为"其他"。可手动编辑或检查大模型配置。
          </template>
          <template v-else>
            <span class="font-medium">未配置大模型</span>，无法自动识别客户沟通。请在
            <button
              type="button"
              class="underline font-medium hover:text-amber-700"
              @click="openSettings"
            >设置 → AI 日报</button>
            中配置 Base URL 和 API Key。
          </template>
        </div>

          <div class="mb-3 flex items-center justify-between gap-3">
            <div class="flex items-center gap-2">
              <button
                type="button"
                class="rounded-full px-3 py-1 text-[11px] font-medium border transition"
                :class="filterMode === 'all'
                  ? 'text-white bg-[#07C160] border-[#07C160]'
                  : ''"
                :style="filterMode !== 'all' ? { borderColor: 'var(--sidebar-rail-border)', color: 'var(--sidebar-rail-icon-active-color)' } : {}"
                @click="filterMode = 'all'"
              >
                全部 ({{ localEntries.length }})
              </button>
              <button
                type="button"
                class="rounded-full px-3 py-1 text-[11px] font-medium border transition"
                :class="filterMode === 'customer'
                  ? 'text-white bg-[#07C160] border-[#07C160]'
                  : ''"
                :style="filterMode !== 'customer' ? { borderColor: 'var(--sidebar-rail-border)', color: 'var(--sidebar-rail-icon-active-color)' } : {}"
                @click="filterMode = 'customer'"
              >
                客户 ({{ customerCount }})
              </button>
              <button
                type="button"
                class="rounded-full px-3 py-1 text-[11px] font-medium border transition"
                :class="filterMode === 'internal'
                  ? 'text-white bg-blue-500 border-blue-500'
                  : ''"
                :style="filterMode !== 'internal' ? { borderColor: 'var(--sidebar-rail-border)', color: 'var(--sidebar-rail-icon-active-color)' } : {}"
                @click="filterMode = 'internal'"
              >
                内部工作 ({{ internalCount }})
              </button>
              <button
                type="button"
                class="rounded-full px-3 py-1 text-[11px] font-medium border transition"
                :class="filterMode === 'other'
                  ? 'text-white bg-gray-400 border-gray-400'
                  : ''"
                :style="filterMode !== 'other' ? { borderColor: 'var(--sidebar-rail-border)', color: 'var(--sidebar-rail-icon-color)' } : {}"
                @click="filterMode = 'other'"
              >
                其他 ({{ nonCustomerCount }})
              </button>
            </div>
            <button
              type="button"
              class="rounded-lg border px-3 py-1.5 text-[12px] font-medium transition hover:bg-[#f5f5f5]"
              :style="{ borderColor: 'var(--sidebar-rail-border)', color: 'var(--sidebar-rail-icon-active-color)' }"
              @click="goClassificationPage"
            >管理归类规则</button>
          </div>

        <!-- entries -->
        <div class="space-y-2.5">
          <div
            v-for="(entry, i) in filteredEntries"
            :key="entry._key || entry.username || i"
            class="rounded-lg border transition" :style="{ borderColor: 'var(--sidebar-rail-border)' }"
          >
            <div class="px-4 py-3">
              <div class="flex items-start justify-between gap-3">
                <div class="min-w-0 flex-1">
                  <div class="flex items-center gap-2">
                    <span class="text-[14px] font-semibold truncate" style="color: var(--sidebar-rail-icon-active-color);">{{ entry.display_name }}</span>
                    <span v-if="entry.is_group" class="shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium leading-none bg-blue-100 text-blue-700">群聊</span>
                    <button
                      type="button"
                      class="shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium leading-none border transition"
                      :class="categoryBadgeClass(entry)"
                    >
                      {{ categoryLabel(entry) }}
                    </button>
                  </div>
                  <div class="mt-1">
                    <span class="text-[12px] font-medium text-amber-600">客户名称：</span>
                    <input
                      :value="entry.customer_name"
                      class="inline-block min-w-[120px] rounded border px-1.5 py-0.5 text-[12px] outline-none transition focus:border-[#07C160]"
                      :style="{ borderColor: 'var(--sidebar-rail-border)', color: 'var(--sidebar-rail-icon-active-color)', backgroundColor: 'var(--sidebar-rail-bg)' }"
                      :placeholder="entry.category === 'customer' ? '客户名称' : '非客户类可留空'"
                      :disabled="entry.category !== 'customer'"
                      @input="onUpdateEntry(i, entry._key, 'customer_name', $event.target.value)"
                    />
                  </div>
                  <div class="mt-1">
                    <span class="text-[12px]" style="color: var(--sidebar-rail-icon-color);">摘要：</span>
                    <input
                      :value="entry.summary"
                      class="inline-block min-w-[200px] rounded border px-1.5 py-0.5 text-[12px] outline-none transition focus:border-[#07C160]"
                      :style="{ borderColor: 'var(--sidebar-rail-border)', color: 'var(--sidebar-rail-icon-active-color)', backgroundColor: 'var(--sidebar-rail-bg)' }"
                      placeholder="点击输入处理摘要"
                      @input="onUpdateEntry(i, entry._key, 'summary', $event.target.value)"
                    />
                  </div>
                </div>
                <button
                  type="button"
                  class="shrink-0 rounded p-1 text-[#999] transition hover:bg-red-50 hover:text-red-500"
                  title="删除该条目"
                  @click="deleteEntry(i, entry._key)"
                >
                  <svg class="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                    <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
                  </svg>
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- add custom entry -->
        <div class="mt-4 border-t pt-4" style="border-color: var(--sidebar-rail-border);">
          <button
            type="button"
            class="flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-[12px] font-medium transition hover:bg-[#f5f5f5]"
            :style="{ borderColor: 'var(--sidebar-rail-border)', color: 'var(--sidebar-rail-icon-active-color)' }"
            @click="showAddForm = !showAddForm"
          >
            <svg class="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
              <path d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z" />
            </svg>
            <span>新增手工条目</span>
          </button>
          <div v-if="showAddForm" class="mt-3 rounded-lg border p-3 space-y-2.5" :style="{ borderColor: 'var(--sidebar-rail-border)', backgroundColor: 'var(--sidebar-rail-bg)' }">
            <div class="grid grid-cols-2 gap-2.5">
              <div>
                <label class="block text-[11px] mb-0.5" style="color: var(--sidebar-rail-icon-color);">名称</label>
                <input
                  v-model="newEntry.display_name"
                  type="text"
                  placeholder="如：处理服务器故障"
                  class="w-full rounded border px-2 py-1 text-[12px] outline-none transition focus:border-[#07C160]"
                  :style="{ borderColor: 'var(--sidebar-rail-border)', color: 'var(--sidebar-rail-icon-active-color)', backgroundColor: 'white' }"
                />
              </div>
              <div>
                <label class="block text-[11px] mb-0.5" style="color: var(--sidebar-rail-icon-color);">客户名称</label>
                <input
                  v-model="newEntry.customer_name"
                  type="text"
                  placeholder="客户名称"
                  class="w-full rounded border px-2 py-1 text-[12px] outline-none transition focus:border-[#07C160]"
                  :style="{ borderColor: 'var(--sidebar-rail-border)', color: 'var(--sidebar-rail-icon-active-color)', backgroundColor: 'white' }"
                />
              </div>
            </div>
            <div>
              <label class="block text-[11px] mb-0.5" style="color: var(--sidebar-rail-icon-color);">处理摘要</label>
              <input
                v-model="newEntry.summary"
                type="text"
                placeholder="今天处理了什么事情"
                class="w-full rounded border px-2 py-1 text-[12px] outline-none transition focus:border-[#07C160]"
                :style="{ borderColor: 'var(--sidebar-rail-border)', color: 'var(--sidebar-rail-icon-active-color)', backgroundColor: 'white' }"
              />
            </div>
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2 text-[12px]" style="color: var(--sidebar-rail-icon-color);">
                <span>标记为客户</span>
                <button
                  type="button"
                  role="switch"
                  :aria-checked="newEntry.is_customer"
                  class="settings-switch shrink-0"
                  :class="newEntry.is_customer ? 'bg-[#07C160]' : 'bg-[#d0d0d0]'"
                  @click="newEntry.is_customer = !newEntry.is_customer"
                >
                  <span class="settings-switch-thumb" :class="newEntry.is_customer ? 'translate-x-[20px]' : 'translate-x-0'" />
                </button>
              </div>
              <div class="flex items-center gap-2">
                <button
                  type="button"
                  class="rounded-lg border px-3 py-1 text-[12px] transition hover:bg-[#f5f5f5]"
                  :style="{ borderColor: 'var(--sidebar-rail-border)', color: 'var(--sidebar-rail-icon-color)' }"
                  @click="showAddForm = false"
                >取消</button>
                <button
                  type="button"
                  class="rounded-lg px-3 py-1 text-[12px] font-medium text-white bg-[#07C160] hover:bg-[#06AD56] transition disabled:opacity-40"
                  :disabled="saving || !newEntry.summary.trim()"
                  @click="submitNewEntry"
                >添加</button>
              </div>
            </div>
          </div>
        </div>

        <!-- save button -->
        <div v-if="report" class="mt-4 flex items-center justify-end gap-3 border-t pt-3" style="border-color: var(--sidebar-rail-border);">
          <span v-if="saveSuccess" class="text-[12px] text-green-600">{{ saveSuccess }}</span>
          <span v-if="saveError" class="text-[12px] text-red-500">{{ saveError }}</span>
          <button
            type="button"
            class="rounded-lg px-4 py-1.5 text-[12px] font-medium text-white bg-[#07C160] hover:bg-[#06AD56] transition disabled:opacity-40"
            :disabled="saving"
            @click="saveAllEntries"
          >
            {{ saving ? '保存中...' : '保存修改' }}
          </button>
        </div>

        <!-- empty filter result -->
        <div v-if="filteredEntries.length === 0" class="flex flex-col items-center py-16 gap-2">
          <svg class="h-8 w-8" style="color: var(--sidebar-rail-icon-color);" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
          </svg>
          <span class="text-[13px]" style="color: var(--sidebar-rail-icon-color);">暂无匹配的条目</span>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import { useApi } from '~/composables/useApi'

const { listReports, getTodayReport, getReportByDate, triggerGenerateReport, triggerBatchGenerateReport, updateReport, addReportEntry } = useApi()
const settingsDialog = useSettingsDialog()

// ── date state ──
const todayStr = ref('')
const selectedDate = ref('')
const isToday = computed(() => selectedDate.value === todayStr.value)
const displayDate = computed(() => selectedDate.value || todayStr.value)

const dateTs = computed(() => {
  if (!selectedDate.value) return NaN
  const ts = new Date(selectedDate.value + 'T00:00:00').getTime()
  return isNaN(ts) ? NaN : ts
})

const displayLabel = computed(() => {
  if (!selectedDate.value) return ''
  if (isToday.value) return '今天'
  const yesterday = new Date()
  yesterday.setDate(yesterday.getDate() - 1)
  const yStr = yesterday.toISOString().slice(0, 10)
  if (selectedDate.value === yStr) return '昨天'
  return selectedDate.value
})

// ── report state ──
const report = ref(null)
const loading = ref(false)
const error = ref('')
const generating = ref(false)
const filterMode = ref('all')
const showBatchPanel = ref(false)
const batchStartDate = ref('')
const batchEndDate = ref('')
const batchGenerating = ref(false)
const batchProgress = ref('')

// ── editing state ──
const saving = ref(false)
const saveSuccess = ref('')
const saveError = ref('')
const showAddForm = ref(false)
const newEntry = ref({ display_name: '', customer_name: '', customer_id: '', summary: '', is_customer: true, category: 'customer' })
let saveSuccessTimer = null

// ── local entry cache (mirror of report entries for editing) ──
const localEntries = ref([])
let _keyCounter = 0
function _syncLocalEntries() {
  if (!report.value) { localEntries.value = []; return }
  _keyCounter = 0
  localEntries.value = (report.value.entries || []).map(e => ({
    category: e.category || (e.is_customer ? 'customer' : 'ignore'),
    customer_id: e.customer_id || '',
    ...e,
    _key: `e_${_keyCounter++}`,
  }))
}
function _nextKey() {
  return `e_${_keyCounter++}`
}

// ── computed ──
const customerCount = computed(() => localEntries.value.filter(e => e.category === 'customer').length)
const internalCount = computed(() => localEntries.value.filter(e => e.category === 'internal').length)
const nonCustomerCount = computed(() => localEntries.value.filter(e => e.category !== 'customer' && e.category !== 'internal').length)

const filteredEntries = computed(() => {
  if (filterMode.value === 'customer') return localEntries.value.filter(e => e.category === 'customer')
  if (filterMode.value === 'internal') return localEntries.value.filter(e => e.category === 'internal')
  if (filterMode.value === 'other') return localEntries.value.filter(e => e.category !== 'customer' && e.category !== 'internal')
  return localEntries.value
})

// ── helpers ──
function openSettings() {
  settingsDialog.openDialog()
}

function goClassificationPage() {
  navigateTo('/report-classification')
}

function categoryLabel(entry) {
  const category = entry?.category || (entry?.is_customer ? 'customer' : 'ignore')
  if (category === 'customer') return '客户'
  if (category === 'internal') return '内部工作'
  if (category === 'ignore') return '忽略'
  return '其他'
}

function categoryBadgeClass(entry) {
  const category = entry?.category || (entry?.is_customer ? 'customer' : 'ignore')
  if (category === 'customer') return 'bg-green-100 text-green-700 border-green-200'
  if (category === 'internal') return 'bg-blue-100 text-blue-700 border-blue-200'
  if (category === 'ignore') return 'bg-gray-100 text-gray-500 border-gray-200'
  return 'bg-gray-100 text-gray-500 border-gray-200'
}

function formatTime(ts) {
  if (!ts) return ''
  try {
    const d = new Date(ts * 1000)
    return d.toLocaleString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  } catch { return '' }
}

// ── date navigation ──
function goPrevDay() {
  const d = new Date(selectedDate.value + 'T00:00:00')
  d.setDate(d.getDate() - 1)
  selectedDate.value = d.toISOString().slice(0, 10)
}

function goNextDay() {
  if (isToday.value) return
  const d = new Date(selectedDate.value + 'T00:00:00')
  d.setDate(d.getDate() + 1)
  const next = d.toISOString().slice(0, 10)
  selectedDate.value = next > todayStr.value ? todayStr.value : next
}

function goDate(val) {
  if (!val) return
  selectedDate.value = val > todayStr.value ? todayStr.value : val
}

// ── entry editing ──
function onUpdateEntry(index, key, field, value) {
  const entry = localEntries.value.find(e => e._key === key)
  if (entry) entry[field] = value
}

function toggleCustomer(index, key) {
  const entry = localEntries.value.find(e => e._key === key)
  if (entry) entry.is_customer = !entry.is_customer
}

function deleteEntry(index, key) {
  localEntries.value = localEntries.value.filter(e => e._key !== key)
}

function submitNewEntry() {
  const entry = { ...newEntry.value }
  if (!entry.summary.trim()) return
  entry.display_name = entry.display_name.trim() || entry.summary.trim()
  entry.is_group = false
  entry.username = ''
  entry.category = entry.category || 'customer'
  entry.is_customer = entry.category === 'customer' || entry.category === 'internal'
  if (entry.category !== 'customer') {
    entry.customer_name = ''
    entry.customer_id = ''
  }
  entry._key = _nextKey()
  localEntries.value.push(entry)
  newEntry.value = { display_name: '', customer_name: '', customer_id: '', summary: '', is_customer: true, category: 'customer' }
  showAddForm.value = false
}

async function saveAllEntries() {
  if (saving.value) return
  saving.value = true
  saveSuccess.value = ''
  saveError.value = ''
  try {
    // Strip internal _key before sending to API
    const clean = localEntries.value.map(({ _key, ...rest }) => rest)
    await updateReport(selectedDate.value, clean)
    saveSuccess.value = '修改已保存'
    if (saveSuccessTimer) clearTimeout(saveSuccessTimer)
    saveSuccessTimer = setTimeout(() => { saveSuccess.value = '' }, 3000)
    // Refresh report from server
    await fetchReport(selectedDate.value)
  } catch (e) {
    saveError.value = e?.message || '保存失败'
  } finally {
    saving.value = false
  }
}

// ── fetch report ──
async function fetchReport(dateStr) {
  loading.value = true
  error.value = ''
  report.value = null
  localEntries.value = []

  try {
    if (dateStr === todayStr.value) {
      const res = await getTodayReport({ generate_if_missing: false })
      report.value = res?.report || null
      if (!res?.report) {
        error.value = '今日日报尚未生成，请点击上方"立即生成"按钮'
      }
    } else {
      const res = await getReportByDate(dateStr)
      report.value = res?.report || null
    }
    if (report.value) {
      _syncLocalEntries()
    }
  } catch (e) {
    if (e?.status === 404 || e?.statusCode === 404 || e?.response?.status === 404) {
      report.value = null
      error.value = ''
    } else {
      error.value = e?.message || '加载失败'
    }
  } finally {
    loading.value = false
  }
}

// ── generate ──
async function triggerGenerate() {
  if (generating.value) return
  generating.value = true
  error.value = ''

  try {
    await triggerGenerateReport({ date: selectedDate.value })

    // The generation runs in a background task (~15-25s for LLM analysis).
    // Poll every 3s until the report's generated_at timestamp is newer than
    // when we started.
    const startedAt = Date.now()
    const maxPolls = 20 // up to ~60s
    let prevGenAt = report.value?.generated_at || 0

    for (let i = 0; i < maxPolls; i++) {
      await new Promise(r => setTimeout(r, 3000))

      try {
        let res
        if (selectedDate.value === todayStr.value) {
          res = await getTodayReport({ generate_if_missing: false })
        } else {
          res = await getReportByDate(selectedDate.value)
        }

        if (res?.report) {
          const genAt = res.report.generated_at || 0
          // Report is fresh if generated_at changed after we triggered
          if (genAt > 0 && genAt !== prevGenAt && genAt * 1000 >= startedAt) {
            report.value = res.report
            _syncLocalEntries()
            return
          }
          prevGenAt = genAt
        }
      } catch {
        // Report may not be available yet (still generating), keep polling
      }
    }

    // Fallback: try one final fetch after all polls exhausted
    await fetchReport(selectedDate.value)
  } catch (e) {
    error.value = e?.message || '生成失败'
  } finally {
    generating.value = false
  }
}

// batch generate
async function startBatchGenerate() {
  if (batchGenerating.value || !batchStartDate.value || !batchEndDate.value) return
  batchGenerating.value = true
  batchProgress.value = '正在提交...' 

  try {
    const res = await triggerBatchGenerateReport({
      start_date: batchStartDate.value,
      end_date: batchEndDate.value,
    })
    const dates = res?.dates || []
    if (!dates.length) {
      batchProgress.value = res?.message || '没有需要生成的日期'
      return
    }

    batchProgress.value = '0 / ' + dates.length
    const done = new Set()
    const POLL_INTERVAL = 5000

    while (batchGenerating.value) {
      await new Promise(r => setTimeout(r, POLL_INTERVAL))

      for (const ds of dates) {
        if (done.has(ds)) continue
        try {
          let r
          if (ds === todayStr.value) {
            r = await getTodayReport({ generate_if_missing: false })
          } else {
            r = await getReportByDate(ds)
          }
          if (r?.report?.generated_at > 0) {
            done.add(ds)
            batchProgress.value = done.size + ' / ' + dates.length
          }
        } catch {}
      }

      if (done.size >= dates.length) {
        batchProgress.value = '已完成 (' + dates.length + '/' + dates.length + ')'
        fetchReport(selectedDate.value)
        return
      }
    }

    // User cancelled — show partial progress.
    if (done.size > 0) {
      batchProgress.value = '已完成 ' + done.size + ' / ' + dates.length + '，剩余的可单独生成'
    } else {
      batchProgress.value = ''
    }
    fetchReport(selectedDate.value)
  } catch (e) {
    batchProgress.value = e?.message || '批量生成失败'
  } finally {
    batchGenerating.value = false
  }
}

// ── watchers ──
watch(selectedDate, (val) => {
  if (val) fetchReport(val)
})

// ── init ──
function cancelBatchGenerate() {
  batchGenerating.value = false
}

onMounted(() => {
  const now = new Date()
  todayStr.value = now.toISOString().slice(0, 10)
  selectedDate.value = todayStr.value
})
</script>

<style scoped>
.settings-switch {
  width: 44px;
  height: 24px;
  border-radius: 999px;
  padding: 2px;
  transition: background-color 0.16s ease, opacity 0.16s ease, filter 0.16s ease;
}

.settings-switch-thumb {
  display: block;
  height: 20px;
  width: 20px;
  border-radius: 999px;
  background: #fff;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.24);
  transition: transform 0.16s ease;
}
</style>
