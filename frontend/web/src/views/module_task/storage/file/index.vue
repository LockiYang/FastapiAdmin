<template>
  <div class="fa-full-height">
    <ElCard class="mb-3">
      <div class="flex flex-wrap items-center gap-3">
        <ElInput
          v-model="search.origin_name"
          class="!w-56"
          placeholder="原始文件名"
          clearable
          @keyup.enter="searchFiles"
        />
        <ElSelect v-model="search.topic" class="!w-36" placeholder="附件分类" clearable
          ><ElOption v-for="topic in topics" :key="topic.value" v-bind="topic"
        /></ElSelect>
        <ElSelect v-model="search.status" class="!w-28" placeholder="状态" clearable
          ><ElOption label="可用" :value="0" /><ElOption label="停用" :value="1"
        /></ElSelect>
        <ElButton type="primary" @click="searchFiles">查询</ElButton>
        <ElButton @click="reset">重置</ElButton>
      </div>
    </ElCard>
    <ElCard class="fa-table-card">
      <div class="mb-3 flex flex-wrap items-center gap-3">
        <ElSelect v-model="uploadTopic" class="!w-36"
          ><ElOption v-for="topic in topics" :key="topic.value" v-bind="topic"
        /></ElSelect>
        <ElButton
          v-hasPerm="['module_common:file:upload']"
          type="primary"
          :loading="uploading"
          @click="input?.click()"
          >上传附件</ElButton
        >
        <input ref="input" type="file" multiple hidden @change="uploadFiles" />
        <ElButton
          v-hasPerm="['module_task:storage:file:delete']"
          type="danger"
          plain
          :disabled="!selected.length"
          @click="remove(selected)"
          >删除记录</ElButton
        >
        <ElButton :loading="loading" @click="load">刷新</ElButton>
        <span class="text-sm text-gray-500">默认节点上传 · 公有访问 · 删除记录保留实际文件</span>
      </div>
      <FaTable
        :loading="loading"
        :data="rows"
        :columns="columns"
        :pagination="pagination"
        @selection-change="selection"
        @pagination:current-change="changePage"
        @pagination:size-change="changeSize"
      >
        <template #origin_name="{ row }"
          ><ElLink :href="row.file_url" target="_blank" rel="noopener noreferrer">{{
            row.origin_name
          }}</ElLink></template
        >
        <template #status="{ row }"
          ><ElTag :type="row.status === 0 ? 'success' : 'info'">{{
            row.status === 0 ? "可用" : "停用"
          }}</ElTag></template
        >
      </FaTable>
    </ElCard>
    <FaDialog
      v-model="visible"
      title="附件详情"
      width="760px"
      @confirm="visible = false"
      @cancel="visible = false"
    >
      <div v-loading="detailLoading" class="attachment-detail">
        <ElScrollbar max-height="72vh">
          <template v-if="detail">
            <div v-if="detail.mime_type?.startsWith('image/')" class="attachment-preview">
              <ElImage
                :key="detail.file_url"
                :src="detail.file_url"
                :alt="detail.origin_name"
                fit="contain"
                :preview-src-list="[detail.file_url]"
                preview-teleported
              >
                <template #error><span>图片暂时无法预览</span></template>
              </ElImage>
            </div>
            <FaDescriptions
              class="attachment-metadata"
              :column="2"
              :span="1"
              label-width="110px"
              :data="detailData"
              :items="detailFields"
              :scrollbar="false"
            >
              <template #file_url="{ value }">
                <ElLink :href="String(value)" target="_blank" rel="noopener noreferrer">{{
                  value
                }}</ElLink>
              </template>
            </FaDescriptions>
          </template>
        </ElScrollbar>
      </div>
    </FaDialog>
  </div>
</template>
<script setup lang="ts">
import { computed, onActivated, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import FaTable from "@/components/tables/fa-table/index.vue";
import FaDialog from "@/components/modal/fa-dialog/index.vue";
import FaDescriptions, {
  type DescriptionsItem,
} from "@/components/display/fa-descriptions/index.vue";
import type { ColumnOption } from "@/types/component";
import FileAPI, { type Attachment } from "@/api/module_storage/file";
import { renderTableOperationCell, type TableOperationAction } from "@utils";

defineOptions({ name: "StorageFile" });
const topics = [
  { label: "通用文件", value: "file" },
  { label: "头像", value: "avatar" },
  { label: "系统参数", value: "param" },
  { label: "资源", value: "resource" },
  { label: "业务附件", value: "attachment" },
];
const search = reactive<{ origin_name?: string; topic?: string; status?: number }>({});
const pagination = reactive({ current: 1, size: 20, total: 0 });
const rows = ref<Attachment[]>([]);
const selected = ref<number[]>([]);
const loading = ref(false);
const uploading = ref(false);
const uploadTopic = ref("attachment");
const input = ref<HTMLInputElement>();
const detail = ref<Attachment>();
const visible = ref(false);
const detailLoading = ref(false);
const detailData = computed<Record<string, unknown>>(() =>
  detail.value
    ? {
        ...detail.value,
        topic:
          topics.find((item) => item.value === detail.value?.topic)?.label || detail.value.topic,
        dimensions:
          detail.value.width && detail.value.height
            ? `${detail.value.width} × ${detail.value.height} px`
            : "—",
        admin_id: detail.value.admin_id ?? "—",
        user_id: detail.value.user_id ?? "—",
      }
    : {}
);
async function openDetail(row: Attachment) {
  visible.value = true;
  detail.value = undefined;
  detailLoading.value = true;
  try {
    detail.value = (await FileAPI.detail(row.id)).data.data;
  } catch (error) {
    visible.value = false;
    console.error("附件详情加载失败:", error);
  } finally {
    detailLoading.value = false;
  }
}
const columns: ColumnOption[] = [
  { type: "selection", width: 46 },
  { prop: "id", label: "ID", width: 80 },
  { prop: "origin_name", label: "文件名称", useSlot: true, minWidth: 200 },
  { prop: "topic", label: "分类", width: 100 },
  { prop: "storage_name", label: "存储节点", minWidth: 130 },
  { prop: "file_size", label: "字节数", width: 110 },
  { prop: "upload_count", label: "上传次数", width: 100 },
  { prop: "reference_count", label: "业务引用", width: 100 },
  { prop: "status", label: "状态", useSlot: true, width: 80 },
  { prop: "last_upload_time", label: "最后上传", minWidth: 175 },
  {
    prop: "operation",
    label: "操作",
    width: 150,
    fixed: "right",
    align: "center",
    formatter: (row: Attachment) => renderAttachmentActions(row),
  },
];
function renderAttachmentActions(row: Attachment) {
  const actions: TableOperationAction[] = [
    {
      key: "detail",
      label: "详情",
      artType: "view",
      run: () => openDetail(row),
    },
    {
      key: "copy-link",
      label: "复制链接",
      artType: "view",
      icon: "ri:link",
      iconColor: "var(--el-color-primary)",
      run: () => copy(row.file_url),
    },
    {
      key: "copy-id",
      label: "复制 ID",
      artType: "view",
      icon: "ri:file-copy-line",
      run: () => copy(String(row.file_id)),
    },
    {
      key: "status",
      label: row.status === 0 ? "停用" : "启用",
      artType: "edit",
      icon: row.status === 0 ? "ri:pause-circle-line" : "ri:play-circle-line",
      perm: "module_task:storage:file:update",
      run: () => toggle(row),
    },
    {
      key: "delete",
      label: "删除",
      artType: "delete",
      perm: "module_task:storage:file:delete",
      run: () => remove([row.id]),
    },
  ];
  return renderTableOperationCell(actions, {
    maxInline: 2,
    wrapperClass: "attachment-row-actions",
  });
}

const detailFields: DescriptionsItem[] = [
  { prop: "id", label: "文件 ID" },
  {
    prop: "status",
    label: "状态",
    tag: { map: { 0: { type: "success", text: "可用" }, 1: { type: "info", text: "停用" } } },
  },
  { prop: "origin_name", label: "原始文件名", span: 2 },
  { prop: "topic", label: "附件分类" },
  { prop: "mime_type", label: "文件类型" },
  { prop: "file_size", label: "大小（字节）" },
  { prop: "dimensions", label: "图片尺寸" },
  { prop: "storage_name", label: "存储节点" },
  { prop: "protocol", label: "存储驱动" },
  { prop: "admin_id", label: "上传管理员" },
  { prop: "user_id", label: "前台用户" },
  { prop: "file_name", label: "存储文件名", span: 2 },
  { prop: "file_path", label: "存储路径", span: 2 },
  { prop: "file_url", label: "公有链接", span: 2 },
  { prop: "uuid", label: "UUID", span: 2 },
  { prop: "sha1", label: "SHA1", span: 2 },
  { prop: "upload_count", label: "上传次数" },
  { prop: "reference_count", label: "业务引用数" },
  { prop: "created_time", label: "创建时间" },
  { prop: "last_upload_time", label: "最后上传" },
];
async function load() {
  loading.value = true;
  try {
    const result = (
      await FileAPI.page({ ...search, page_no: pagination.current, page_size: pagination.size })
    ).data.data;
    rows.value = result.items;
    pagination.total = result.total;
    selected.value = [];
  } finally {
    loading.value = false;
  }
}
function searchFiles() {
  pagination.current = 1;
  void load();
}
function reset() {
  search.origin_name = undefined;
  search.topic = undefined;
  search.status = undefined;
  searchFiles();
}
function changePage(page: number) {
  pagination.current = page;
  void load();
}
function changeSize(size: number) {
  pagination.size = size;
  searchFiles();
}
function selection(items: Attachment[]) {
  selected.value = items.map((item) => item.id);
}
async function uploadFiles(event: Event) {
  const target = event.target as HTMLInputElement;
  uploading.value = true;
  try {
    for (const file of Array.from(target.files || []))
      await FileAPI.upload(file, uploadTopic.value);
    pagination.current = 1;
    await load();
  } catch (error) {
    // HTTP 层已提示请求失败，事件入口在此接住异常，避免触发组件错误边界。
    console.error("附件上传失败:", error);
  } finally {
    uploading.value = false;
    target.value = "";
  }
}
async function copy(value: string) {
  try {
    await navigator.clipboard.writeText(value);
    ElMessage.success("已复制");
  } catch {
    ElMessage.warning("复制失败，请在详情中手动复制");
  }
}
async function toggle(row: Attachment) {
  await FileAPI.update(row.id, row.status === 0 ? 1 : 0);
  await load();
}
async function remove(ids: number[]) {
  try {
    await ElMessageBox.confirm(
      "删除附件记录后不能再建立新引用，实际文件与已有公有链接保留。确认删除？",
      "删除附件",
      { type: "warning" }
    );
  } catch {
    return;
  }
  await FileAPI.delete(ids);
  ElMessage.success("附件记录已删除");
  await load();
}
onActivated(load);
</script>

<style scoped>
:deep(.attachment-row-actions) {
  display: inline-flex;
  flex-flow: row nowrap;
  align-items: center;
  justify-content: center;
  gap: 4px;
  white-space: nowrap;
}
:deep(.attachment-row-actions > *) {
  flex: 0 0 auto;
}
:deep(.attachment-row-actions .hover-btn) {
  margin-right: 0;
}
.attachment-detail {
  min-height: 140px;
  min-width: 0;
}
.attachment-preview {
  height: 220px;
  max-height: 34vh;
  margin-bottom: 16px;
  overflow: hidden;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
  background: var(--el-fill-color-lighter);
}
.attachment-preview :deep(.el-image) {
  width: 100%;
  height: 100%;
}
.attachment-preview :deep(.el-image__error) {
  color: var(--el-text-color-secondary);
}
.attachment-metadata {
  width: 100%;
}
.attachment-metadata :deep(.el-descriptions__table) {
  width: 100%;
  table-layout: fixed;
}
.attachment-metadata :deep(.el-descriptions__label) {
  width: 110px;
  white-space: nowrap;
}
.attachment-metadata :deep(.el-descriptions__content),
.attachment-metadata :deep(.el-link) {
  overflow-wrap: anywhere;
  word-break: break-word;
}
.attachment-metadata :deep(.el-link) {
  justify-content: flex-start;
  text-align: left;
}
</style>
