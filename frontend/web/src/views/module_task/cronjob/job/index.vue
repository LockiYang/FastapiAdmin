<!-- 调度任务：主区调度器状态 + 任务卡片列表（getSchedulerJobs 全量、前端筛选）；抽屉内执行日志表用 useTable 分页 -->
<template>
  <div class="fa-full-height job-page flex flex-col min-h-0">
    <FaSearchBar
      v-show="showSearchBar"
      ref="searchBarRef"
      v-model="searchForm"
      :items="jobSearchItems"
      :rules="searchBarRules"
      :is-expand="false"
      :show-expand="true"
      :show-reset="true"
      :show-search="true"
      :disabled-search="false"
      :default-expanded="false"
      include-audit
      :audit-item-options="{ showCreatedBy: false, showUpdatedBy: false }"
      @search="handleSearchBarSearch"
      @reset="onResetSearch"
    />

    <ElCard
      class="flex flex-1 min-h-0 flex-col fa-table-card job-page-card"
      :style="{ 'margin-top': showSearchBar ? '12px' : '0' }"
    >
      <FaTableHeader
        v-model:columns="jobColumnChecks"
        v-model:showSearchBar="showSearchBar"
        layout="search,refresh"
        :loading="jobLoading"
        @refresh="refreshJobList"
      >
        <template #left>
          <div class="flex flex-wrap gap-1 items-center">
            <div class="flex gap-1 items-center">
              <div class="flex items-center gap-1 whitespace-nowrap">
                <span class="text-xs text-(--el-text-color-secondary)">本机调度器</span>
                <ElTag
                  :type="getSchedulerStatusType(schedulerStatus.status)"
                  size="small"
                  effect="dark"
                >
                  {{ getSchedulerStatusLabel(schedulerStatus.status) }}
                </ElTag>
              </div>
              <ElDivider direction="vertical" />
              <div class="flex items-center gap-1 whitespace-nowrap">
                <span class="text-xs text-(--el-text-color-secondary)">运行中</span>
                <ElTag
                  :type="schedulerStatus.is_running ? 'success' : 'info'"
                  size="small"
                  effect="dark"
                >
                  {{ schedulerStatus.is_running ? "是" : "否" }}
                </ElTag>
              </div>
              <ElDivider direction="vertical" />
              <div class="flex items-center gap-1 whitespace-nowrap">
                <span class="text-xs text-(--el-text-color-secondary)">任务</span>
                <span class="text-sm font-bold text-(--el-color-warning)">{{
                  schedulerStatus.job_count
                }}</span>
              </div>
            </div>
            <ElDivider direction="vertical" />
            <div class="flex flex-wrap gap-1 items-center">
              <ElButton
                v-hasPerm="['module_task:cronjob:job:scheduler']"
                type="warning"
                :icon="VideoPause"
                :disabled="schedulerStatus.status !== '运行中'"
                size="small"
                @click="handlePauseScheduler"
              >
                暂停
              </ElButton>
              <ElButton
                v-hasPerm="['module_task:cronjob:job:scheduler']"
                type="primary"
                :icon="RefreshRight"
                :disabled="schedulerStatus.status !== '暂停'"
                size="small"
                @click="handleResumeScheduler"
              >
                恢复
              </ElButton>
              <ElDivider direction="vertical" />
              <ElButton
                v-hasPerm="['module_task:cronjob:job:query']"
                size="small"
                @click="handleOpenExecutionLogDrawer()"
              >
                执行记录
              </ElButton>
            </div>
          </div>
        </template>
      </FaTableHeader>

      <!-- 卡片骨架：初始加载时显示 -->
      <ElSkeleton v-if="jobLoading && (!jobList || jobList.length === 0)" animated class="mt-3">
        <template #template>
          <div class="grid grid-cols-[repeat(auto-fill,minmax(200px,1fr))] gap-4">
            <div v-for="i in 12" :key="i" class="h-50">
              <ElSkeletonItem
                variant="rect"
                style="width: 100%; height: 100%; border-radius: var(--custom-radius)"
              />
            </div>
          </div>
        </template>
      </ElSkeleton>

      <ElScrollbar v-else class="job-cards-container mt-3 min-h-0 flex-1">
        <ElEmpty
          v-if="!jobLoading && (!jobList || jobList.length === 0)"
          :image-size="80"
          description="暂无数据"
        />
        <ElRow v-else :gutter="16">
          <ElCol
            v-for="job in jobList"
            :key="job.id"
            :xs="24"
            :sm="12"
            :md="6"
            :lg="4"
            class="mb-4"
          >
            <ElCard
              shadow="hover"
              :class="`fa-card job-card job-card--${getJobStatusClass(job.status)}`"
            >
              <template #header>
                <div class="job-card-title">
                  <span
                    class="job-card-dot"
                    :class="`job-card-dot--${getJobStatusClass(job.status)}`"
                  />
                  <ElTooltip :content="job.name" placement="top">
                    <span class="job-card-name">{{ job.name }}</span>
                  </ElTooltip>
                  <ElTag :type="getJobStatusType(job.status)" size="small" effect="dark">
                    {{ getJobStatusLabel(job.status) }}
                  </ElTag>
                </div>
              </template>

              <div class="job-card-body cursor-pointer" @click="handleOpenExecutionLogDrawer(job)">
                <div class="job-card-body-row">
                  <FaSvgIcon :icon="getTriggerIcon(job.trigger)" class="job-card-meta-icon" />
                  <span class="job-card-meta-text">{{ formatTrigger(job.trigger) }}</span>
                </div>
                <div class="job-card-body-row">
                  <FaSvgIcon icon="ri:time-line" class="job-card-meta-icon" />
                  <span class="job-card-meta-text">{{ job.next_run_time || "暂无" }}</span>
                </div>
              </div>
            </ElCard>
          </ElCol>
        </ElRow>
      </ElScrollbar>
    </ElCard>

    <FaDrawer v-model="executionLogDrawerVisible" title="执行记录" direction="rtl" size="80%">
      <div class="flex flex-col min-h-0 h-full">
        <FaSearchBar
          ref="logSearchBarRef"
          v-model="logSearchForm"
          :items="logSearchItems"
          :rules="logSearchBarRules"
          :is-expand="false"
          :show-expand="false"
          :show-reset="true"
          :show-search="true"
          :disabled-search="false"
          :default-expanded="false"
          @search="handleLogSearchBarSearch"
          @reset="onLogResetSearch"
        />
        <ElCard class="fa-table-card mt-3 flex flex-1 min-h-0 flex-col">
          <FaTableHeader
            v-model:columns="logColumnChecks"
            layout="search,refresh"
            :loading="logLoading"
            @refresh="refreshLogData"
          >
            <template #left>
              <FaTableHeaderLeft
                :remove-ids="logSelectedIds"
                :perm-delete="['module_task:cronjob:job:delete']"
                :delete-loading="logBatchDeleting"
                @delete="handleLogBatchDelete"
              />
            </template>
          </FaTableHeader>
          <FaTable
            ref="logfaTableRef"
            row-key="id"
            :loading="logLoading"
            :data="logTableData"
            :columns="logColumns"
            :pagination="logPaginationBind"
            @selection-change="onLogTableSelectionChange"
            @pagination:size-change="logHandleSizeChange"
            @pagination:current-change="logHandleCurrentChange"
          >
          </FaTable>
        </ElCard>
      </div>
    </FaDrawer>

    <!-- 执行记录详情弹窗 -->
    <FaDialog
      v-model="logDetailDialog.visible"
      title="执行记录详情"
      width="720px"
      form-mode="detail"
      @close="logDetailDialog.visible = false"
    >
      <FaDescriptions
        :column="4"
        :data="logDetailFormData"
        :items="logDetailItems"
        max-height="70vh"
      />
    </FaDialog>
  </div>
</template>

<script lang="ts" setup>
defineOptions({
  name: "Job",
  inheritAttrs: false,
});

import JobAPI, {
  type SchedulerStatus,
  type SchedulerJob,
  type JobLogTable,
} from "@/api/module_task/cronjob/job";
import type { SearchFormItem } from "@/components/forms/fa-search-bar/index.vue";
import type FaSearchBar from "@/components/forms/fa-search-bar/index.vue";
import FaTableHeader from "@/components/tables/fa-table-header/index.vue";
import FaTable from "@/components/tables/fa-table/index.vue";
import FaDialog from "@/components/modal/fa-dialog/index.vue";
import FaDrawer from "@/components/modal/fa-drawer/index.vue";
import { VideoPause, RefreshRight } from "@element-plus/icons-vue";
import { renderTableOperationCell, type TableOperationAction } from "@utils";
import type { ColumnOption } from "@/types/component";

const schedulerStatus = ref<SchedulerStatus>({
  status: "未知",
  is_running: false,
  job_count: 0,
  code_exec_enabled: false,
});

type JobSearchForm = {
  name?: string;
  status?: number;
};

const searchForm = ref<JobSearchForm>({
  name: undefined,
  status: undefined,
});

const showSearchBar = ref(true);
const searchBarRef = ref<InstanceType<typeof FaSearchBar> | null>(null);
const searchBarRules: Record<string, unknown> = {};

const jobSearchItems = computed<SearchFormItem[]>(() => [
  {
    label: "任务名称",
    key: "name",
    type: "input",
    placeholder: "请输入任务名称",
    clearable: true,
    span: 6,
  },
  {
    label: "任务状态",
    key: "status",
    type: "select",
    props: {
      placeholder: "请选择状态",
      clearable: true,
      options: [
        { label: "待调度", value: 0 },
        { label: "暂停中", value: 1 },
      ],
    },
    span: 6,
  },
]);

async function loadSchedulerStatus() {
  try {
    const statusRes = await JobAPI.getSchedulerStatus();
    schedulerStatus.value = statusRes.data.data;
  } catch (error: unknown) {
    if (import.meta.env.DEV) console.error(error);
  }
}

/** 调度器任务列表为全量列表接口，无分页；筛选在前端完成 */
const jobList = ref<SchedulerJob[]>([]);
const jobLoading = ref(false);
/** 主区域为卡片列表无表格列配置，仅占位满足 FaTableHeader v-model */
const jobColumnChecks = ref<ColumnOption<SchedulerJob>[]>([]);

function matchesJobStatusFilter(jobStatus: number | undefined, filter?: number): boolean {
  if (filter === undefined) return true;
  const map: Record<number, number[]> = {
    0: [0], // 运行中
    1: [1], // 暂停
    2: [2], // 停止
  };
  const allowed = map[filter];
  if (!allowed) return true;
  return allowed.includes(jobStatus ?? -1);
}

async function fetchSchedulerJobs() {
  jobLoading.value = true;
  try {
    const res = await JobAPI.getSchedulerJobs();
    const raw = res.data?.data;
    const list: SchedulerJob[] = Array.isArray(raw) ? raw : [];
    const nameQ = searchForm.value.name?.trim();
    const statusQ = searchForm.value.status;
    jobList.value = list.filter((j) => {
      if (nameQ && !(j.name ?? "").includes(nameQ)) return false;
      if (!matchesJobStatusFilter(j.status, statusQ)) return false;
      return true;
    });
    await loadSchedulerStatus();
  } catch (error: unknown) {
    if (import.meta.env.DEV) console.error(error);
    jobList.value = [];
  } finally {
    jobLoading.value = false;
  }
}

const refreshJobList = fetchSchedulerJobs;

async function handleSearchBarSearch() {
  await searchBarRef.value?.validate?.();
  await fetchSchedulerJobs();
}

async function onResetSearch() {
  searchForm.value = {
    name: undefined,
    status: undefined,
  };
  await fetchSchedulerJobs();
}

onMounted(() => {
  void fetchSchedulerJobs();
});

type LogSearchForm = {
  status?: number;
  trigger_type?: string;
  created_time?: string[];
  updated_time?: string[];
};

function buildLogReplaceParams(u: LogSearchForm): Record<string, unknown> {
  return {
    status: u.status,
    trigger_type: u.trigger_type,
    created_time:
      Array.isArray(u.created_time) && u.created_time.length === 2 ? u.created_time : undefined,
    updated_time:
      Array.isArray(u.updated_time) && u.updated_time.length === 2 ? u.updated_time : undefined,
  };
}

const logSearchForm = ref<LogSearchForm>({
  status: undefined,
  trigger_type: undefined,
  created_time: undefined,
  updated_time: undefined,
});

const logSearchBarRef = ref<InstanceType<typeof FaSearchBar> | null>(null);
const logSearchBarRules: Record<string, unknown> = {};

const logSearchItems = computed<SearchFormItem[]>(() => [
  {
    label: "执行状态",
    key: "status",
    type: "select",
    props: {
      placeholder: "请选择状态",
      clearable: true,
      options: [
        { label: "待执行", value: 0 },
        { label: "执行中", value: 1 },
        { label: "成功", value: 2 },
        { label: "失败", value: 3 },
        { label: "超时", value: 4 },
        { label: "已取消", value: 5 },
      ],
    },
    span: 8,
  },
  {
    label: "触发方式",
    key: "trigger_type",
    type: "select",
    props: {
      placeholder: "请选择",
      clearable: true,
      options: [
        { label: "Cron表达式", value: "cron" },
        { label: "时间间隔", value: "interval" },
        { label: "固定日期", value: "date" },
        { label: "一次性任务", value: "manual" },
      ],
    },
    span: 8,
  },
]);

const currentLogJobId = ref<string | undefined>(undefined);
function buildLogRowActions(row: JobLogTable): TableOperationAction[] {
  const all: TableOperationAction[] = [
    {
      key: "detail",
      label: "详情",
      artType: "view",
      perm: "module_task:cronjob:job:detail",
      run: () => handleOpenLogDetail(row),
    },
    {
      key: "delete",
      label: "删除",
      artType: "delete",
      perm: "module_task:cronjob:job:delete",
      run: () => deleteLogRow(row.id, String(row?.job_name ?? row?.id ?? "")),
    },
  ];
  return all;
}

function formatLogOperationCell(row: JobLogTable) {
  return renderTableOperationCell(buildLogRowActions(row));
}

const logfaTableRef = ref<{ elTableRef?: { clearSelection: () => void } } | null>(null);
const logSelectedRows = ref<JobLogTable[]>([]);
const logSelectedIds = computed(() =>
  logSelectedRows.value.map((r) => r.id).filter((id): id is number => typeof id === "number")
);
const logBatchDeleting = ref(false);

function onLogTableSelectionChange(rows: JobLogTable[]) {
  logSelectedRows.value = rows;
}

const {
  columns: logColumns,
  columnChecks: logColumnChecks,
  data: logTableData,
  loading: logLoading,
  pagination: logPagination,
  getData: getLogData,
  replaceSearchParams: replaceLogSearchParams,
  resetSearchParams: resetLogSearchParams,
  handleSizeChange: logHandleSizeChange,
  handleCurrentChange: logHandleCurrentChange,
  refreshData: refreshLogData,
  refreshRemove: refreshLogRemove,
} = useTable({
  core: {
    apiFn: JobAPI.getJobLogList,
    immediate: false,
    apiParams: {
      page_no: 1,
      page_size: 10,
      job_id: "",
      status: undefined,
      trigger_type: undefined,
    },
    columnsFactory: (): ColumnOption<JobLogTable>[] => [
      { type: "selection", width: 48, fixed: "left" },
      { type: "globalIndex", width: 56, label: "序号" },
      {
        prop: "job_id",
        label: "任务ID",
        minWidth: 80,
        showOverflowTooltip: true,
      },
      {
        prop: "job_name",
        label: "任务名称",
        minWidth: 140,
        showOverflowTooltip: true,
      },
      {
        prop: "trigger_type",
        label: "触发方式",
        minWidth: 120,
        status: {
          cron: { type: "info", text: "Cron表达式" },
          interval: { type: "info", text: "时间间隔" },
          date: { type: "info", text: "固定日期" },
          manual: { type: "info", text: "手动执行" },
        },
      },
      {
        prop: "status",
        label: "状态",
        minWidth: 80,
        status: {
          0: { type: "info", text: "待执行" },
          1: { type: "primary", text: "执行中" },
          2: { type: "success", text: "成功" },
          3: { type: "danger", text: "失败" },
          4: { type: "warning", text: "超时" },
          5: { type: "info", text: "已取消" },
        },
      },
      { prop: "started_time", label: "开始时间", minWidth: 200, showOverflowTooltip: true },
      { prop: "finished_time", label: "结束时间", minWidth: 200, showOverflowTooltip: true },
      { prop: "duration_ms", label: "耗时(ms)", minWidth: 100 },
      {
        prop: "result",
        label: "执行结果",
        minWidth: 100,
        showOverflowTooltip: true,
      },
      {
        prop: "error",
        label: "错误信息",
        minWidth: 100,
        showOverflowTooltip: true,
      },
      {
        prop: "created_time",
        label: "创建时间",
        minWidth: 160,
        sortable: true,
        showOverflowTooltip: true,
      },
      {
        prop: "updated_time",
        label: "更新时间",
        minWidth: 160,
        sortable: true,
        showOverflowTooltip: true,
      },
      {
        prop: "operation",
        label: "操作",
        width: 88,
        fixed: "right",
        align: "center",
        formatter: (row: JobLogTable) => formatLogOperationCell(row),
      },
    ],
  },
});

async function deleteLogRow(id: number | undefined, name: string | number) {
  if (id == null) return;
  try {
    await confirmDelete(`确定删除执行记录「${name}」吗？`);
    await JobAPI.deleteJobLog([id]);
    logfaTableRef.value?.elTableRef?.clearSelection();
    await refreshLogRemove();
  } catch {
    // 用户取消
  }
}

async function handleLogBatchDelete() {
  const ids = logSelectedIds.value;
  if (ids.length === 0) return;
  try {
    await confirmBatchDelete(
      ids.length,
      logSelectedRows.value.map((r) => String(r?.job_name ?? r?.id ?? ""))
    );
    logBatchDeleting.value = true;
    await JobAPI.deleteJobLog(ids);
    logSelectedRows.value = [];
    await refreshLogRemove();
  } catch {
    // 用户取消
  } finally {
    logBatchDeleting.value = false;
  }
}

const logPaginationBind = computed(() => {
  const p = logPagination as unknown as {
    current?: number;
    size?: number;
    total?: number;
    page_no?: number;
    page_size?: number;
  };
  return {
    current: p.current ?? p.page_no ?? 1,
    size: p.size ?? p.page_size ?? 10,
    total: p.total ?? 0,
  };
});

async function handleLogSearchBarSearch(params: LogSearchForm) {
  await logSearchBarRef.value?.validate?.();
  if (!currentLogJobId.value) return;
  replaceLogSearchParams({
    ...buildLogReplaceParams(params),
    job_id: currentLogJobId.value,
  });
  await getLogData();
}

async function onLogResetSearch() {
  logSearchForm.value = {
    status: undefined,
    trigger_type: undefined,
    created_time: undefined,
    updated_time: undefined,
  };
  await resetLogSearchParams();
  if (currentLogJobId.value) {
    replaceLogSearchParams({ job_id: currentLogJobId.value });
    await getLogData();
  }
}

const executionLogDrawerVisible = ref(false);

// ─── 执行记录详情弹窗 ───
const logDetailDialog = reactive({
  visible: false,
});
const logDetailFormData = ref<JobLogTable>({} as JobLogTable);

const logDetailItems: import("@/components/display/fa-descriptions/index.vue").DescriptionsItem[] =
  [
    { label: "任务ID", prop: "job_id" },
    { label: "任务名称", prop: "job_name" },
    { label: "触发方式", prop: "trigger_type" },
    { label: "执行状态", prop: "status" },
    { label: "开始时间", prop: "started_time" },
    { label: "结束时间", prop: "finished_time" },
    { label: "耗时(ms)", prop: "duration_ms" },
    { label: "执行结果", prop: "result", span: 4 },
    { label: "错误信息", prop: "error", span: 4 },
    { label: "创建时间", prop: "created_time" },
    { label: "更新时间", prop: "updated_time" },
  ];

async function handleOpenLogDetail(row: JobLogTable) {
  if (row.id == null) return;
  try {
    const res = await JobAPI.getJobLogDetail(row.id);
    Object.assign(logDetailFormData.value, res.data.data ?? {});
    logDetailDialog.visible = true;
  } catch {
    /* 已由全局拦截器提示 */
  }
}

function getSchedulerStatusType(status: string) {
  switch (status) {
    case "运行中":
      return "success";
    case "暂停":
      return "warning";
    case "停止":
      return "danger";
    default:
      return "info";
  }
}

function getSchedulerStatusLabel(status: string) {
  return status || "未知";
}

function getJobStatusType(status: number) {
  switch (status) {
    case 0:
      return "success";
    case 1:
      return "warning";
    case 2:
      return "danger";
    case 3:
      return "info";
    default:
      return "info";
  }
}

function getJobStatusLabel(status: number) {
  switch (status) {
    case 0:
      return "待调度";
    case 1:
      return "暂停中";
    case 2:
      return "已停止";
    case 3:
      return "未知";
    default:
      return status;
  }
}

function formatTrigger(trigger: string) {
  if (!trigger) {
    return "-";
  }

  if (trigger.includes("cron")) {
    const match = trigger.match(/cron\[([^\]]+)\]/);
    if (match) {
      const params = match[1]!;
      // 提取关键参数
      const month = params.match(/month='([^']+)'/);
      const day = params.match(/day='([^']+)'/);
      const hour = params.match(/hour='([^']+)'/);
      const minute = params.match(/minute='([^']+)'/);
      const second = params.match(/second='([^']+)'/);
      const dayOfWeek = params.match(/day_of_week='([^']+)'/);

      // 构建简化的 cron 表达式
      const parts = [];
      if (second && second[1] !== "'*'") parts.push(`秒:${second[1]}`);
      if (minute && minute[1] !== "'*'") parts.push(`分:${minute[1]}`);
      if (hour && hour[1] !== "'*'") parts.push(`时:${hour[1]}`);
      if (day && day[1] !== "'*'") parts.push(`日:${day[1]}`);
      if (month && month[1] !== "'*'") parts.push(`月:${month[1]}`);
      if (dayOfWeek && dayOfWeek[1] !== "'*'") parts.push(`周:${dayOfWeek[1]}`);

      if (parts.length === 0) {
        return "Cron: 每分钟";
      }
      return `Cron: ${parts.join(" ")}`;
    }
    return trigger;
  }

  if (trigger.includes("interval")) {
    const match = trigger.match(/interval\[([^\]]+)\]/);
    return match ? `间隔时长: ${match[1]}` : trigger;
  }

  if (trigger.includes("date")) {
    const match = trigger.match(/date\[([^\]]+)\]/);
    return match ? `执行日期: ${match[1]}` : trigger;
  }

  return trigger;
}

async function handlePauseScheduler() {
  try {
    await JobAPI.pauseScheduler();
    await refreshJobList();
  } catch (error: unknown) {
    if (import.meta.env.DEV) console.error(error);
  }
}

async function handleResumeScheduler() {
  try {
    await JobAPI.resumeScheduler();
    await refreshJobList();
  } catch (error: unknown) {
    if (import.meta.env.DEV) console.error(error);
  }
}

async function handleOpenExecutionLogDrawer(job?: SchedulerJob) {
  currentLogJobId.value = job?.id;
  logSearchForm.value = {
    status: undefined,
    trigger_type: undefined,
    created_time: undefined,
    updated_time: undefined,
  };
  executionLogDrawerVisible.value = true;
  await nextTick();
  replaceLogSearchParams({
    job_id: job?.id,
    page_no: 1,
    page_size: 10,
  });
  getLogData();
}

function getJobStatusClass(status: number) {
  switch (status) {
    case 0:
      return "running";
    case 1:
      return "paused";
    case 2:
      return "stopped";
    default:
      return "unknown";
  }
}

function getTriggerIcon(trigger: string | undefined) {
  const t = (trigger ?? "").toLowerCase();
  if (t.includes("cron")) return "ri:timer-line";
  if (t.includes("interval")) return "ri:repeat-line";
  if (t.includes("date")) return "ri:calendar-event-line";
  return "ri:flashlight-line";
}
</script>

<style scoped lang="scss">
.job-page :deep(.data-table) {
  height: 100%;
}

.job-page-card {
  :deep(.el-card__body) {
    display: flex;
    flex: 1;
    flex-direction: column;
    min-height: 0;
    overflow: hidden;
  }
}

.job-card {
  :deep(.el-card__header) {
    padding: 8px 16px;
  }

  :deep(.el-card__body) {
    padding: 8px 16px;
  }

  :deep(.el-card__footer) {
    padding: 8px 16px;
  }
}

.job-card-title {
  display: flex;
  gap: 6px;
  align-items: center;
  min-width: 0;
}

.job-card-dot {
  flex-shrink: 0;
  width: 8px;
  height: 8px;
  border-radius: 50%;

  &--running {
    background: var(--el-color-success);
  }

  &--paused {
    background: var(--el-color-warning);
  }

  &--stopped {
    background: var(--el-color-danger);
  }

  &--unknown {
    background: var(--el-color-info);
  }
}

.job-card-body {
  display: flex;
  flex-direction: column;
  gap: 5px;
  min-width: 0;
  overflow: hidden;

  &-row {
    display: flex;
    gap: 4px;
    align-items: center;
    min-width: 0;
    overflow: hidden;
  }
}

.job-card-name {
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 14px;
  font-weight: 600;
  white-space: nowrap;
}

.job-card-meta-icon {
  flex-shrink: 0;
  font-size: 13px;
  color: var(--el-color-primary-light-3);
}

.job-card-meta-text {
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  white-space: nowrap;
}

.execution-log-drawer :deep(.el-card.data-table) {
  flex: 1;
  min-height: 0;
}
</style>
