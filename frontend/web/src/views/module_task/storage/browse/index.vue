<template>
  <ElCard class="fa-full-height">
    <div class="mb-3 flex flex-wrap items-center gap-2">
      <ElSelect v-model="selectedNode" placeholder="打开存储节点" @change="openNode">
        <ElOption
          v-for="node in nodes"
          :key="node.id"
          :value="node.id!"
          :label="`${node.name}${node.is_default ? '（默认）' : ''}`"
        />
      </ElSelect>
    </div>
    <ElTabs v-if="tabs.length" v-model="activeId" type="card" closable @tab-remove="closeTab">
      <ElTabPane
        v-for="id in tabs"
        :key="id"
        :name="id"
        :label="nodes.find((n) => n.id === id)?.name || String(id)"
      />
    </ElTabs>
    <template v-if="activeId">
      <div class="mb-3 flex items-center gap-2">
        <ElSelect v-if="buckets.length" v-model="bucket" placeholder="存储桶" @change="navigate('')"
          ><ElOption v-for="item in buckets" :key="item" :label="item" :value="item"
        /></ElSelect>
        <ElButton :disabled="!prefix" @click="navigate(prefix.split('/').slice(0, -1).join('/'))"
          >上一级</ElButton
        >
        <ElInput v-model="pathInput" placeholder="存储根目录" @keyup.enter="navigate(pathInput)" />
        <ElButton @click="navigate(pathInput)">打开</ElButton
        ><ElButton :loading="loading" @click="load(true)">刷新</ElButton>
      </div>
      <FaTable :loading="loading" :data="rows" :columns="columns">
        <template #name="{ row }"
          ><ElLink
            :type="row.is_dir ? 'primary' : 'default'"
            @click="row.is_dir && navigate(row.key)"
            >{{ row.is_dir ? "📁 " : "" }}{{ row.name }}</ElLink
          ></template
        >
        <template #operation="{ row }"
          ><ElButton
            v-hasPerm="['module_task:storage:browse:download']"
            link
            type="primary"
            @click="download(row)"
            >{{ row.is_dir ? "下载 ZIP" : "下载" }}</ElButton
          ></template
        >
      </FaTable>
      <div class="mt-3 flex justify-end">
        <ElButton :disabled="!hasNext || loading" @click="load(false)">加载更多</ElButton>
      </div>
    </template>
    <ElEmpty v-else description="请选择存储节点" />
  </ElCard>
</template>
<script setup lang="ts">
import { onActivated, onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { saveAs } from "file-saver";
import FaTable from "@/components/tables/fa-table/index.vue";
import type { ColumnOption } from "@/types/component";
import NodeAPI, { type SourceTable } from "@/api/module_storage/node";
import BrowseAPI, { type StorageObject } from "@/api/module_storage/browse";

defineOptions({ name: "WorkflowBrowse" });
const route = useRoute();
const nodes = ref<SourceTable[]>([]);
const tabs = ref<number[]>([]);
const activeId = ref<number>();
const selectedNode = ref<number>();
const prefix = ref("");
const pathInput = ref("");
const buckets = ref<string[]>([]);
const bucket = ref<string>();
const rows = ref<StorageObject[]>([]);
const cursor = ref<string>();
const hasNext = ref(false);
const loading = ref(false);
let generation = 0;
const columns: ColumnOption[] = [
  { prop: "name", label: "名称", useSlot: true, minWidth: 240 },
  { prop: "size", label: "字节数", width: 140 },
  { prop: "modified_time", label: "修改时间", minWidth: 180 },
  { prop: "operation", label: "操作", useSlot: true, width: 120 },
];
function openNode(id: number) {
  if (!nodes.value.some((n) => n.id === id)) return;
  if (!tabs.value.includes(id)) tabs.value.push(id);
  activeId.value = id;
}
function closeTab(name: string | number) {
  tabs.value = tabs.value.filter((id) => id !== Number(name));
  if (activeId.value === Number(name)) activeId.value = tabs.value[0];
}
async function load(reset = true) {
  if (!activeId.value) return;
  const current = ++generation;
  loading.value = true;
  try {
    const response = await BrowseAPI.listFiles({
      source_id: activeId.value,
      prefix: prefix.value,
      bucket: bucket.value,
      page_size: 100,
      cursor: reset ? undefined : cursor.value,
    });
    if (current !== generation) return;
    const result = response.data.data;
    const items = Array.isArray(result) ? result : result.items;
    rows.value = reset ? items : [...rows.value, ...items];
    hasNext.value = !Array.isArray(result) && result.has_next;
    cursor.value = Array.isArray(result) ? undefined : result.next_cursor || undefined;
  } finally {
    if (current === generation) loading.value = false;
  }
}
function navigate(path: string) {
  prefix.value = path.replace(/^\/+|\/+$/g, "");
  pathInput.value = prefix.value;
  void load(true);
}
watch(activeId, async (id) => {
  const current = ++generation;
  rows.value = [];
  prefix.value = "";
  pathInput.value = "";
  bucket.value = undefined;
  buckets.value = [];
  hasNext.value = false;
  if (!id) return;
  const response = await BrowseAPI.listBuckets({ source_id: id });
  if (current !== generation) return;
  buckets.value = response.data.data;
  const node = nodes.value.find((n) => n.id === id);
  bucket.value = node?.bucket || buckets.value[0];
  await load(true);
});
async function download(row: StorageObject) {
  if (!row.key) return;
  const body = { source_id: activeId.value, remote_path: row.key, bucket: bucket.value };
  const response = await (row.is_dir ? BrowseAPI.downloadDir(body) : BrowseAPI.downloadFile(body));
  saveAs(response.data, `${row.name || "file"}${row.is_dir ? ".zip" : ""}`);
}
let initialized = false;
onMounted(async () => {
  nodes.value = (await NodeAPI.listNode({ status: 0 })).data.data;
  const id =
    Number(route.query.nodeId || route.query.source_id) ||
    nodes.value.find((n) => n.is_default)?.id ||
    nodes.value[0]?.id;
  if (id) openNode(id);
  initialized = true;
});
watch(
  () => route.query.nodeId || route.query.source_id,
  (id) => {
    if (id) openNode(Number(id));
  }
);
onActivated(async () => {
  if (!initialized) return;
  nodes.value = (await NodeAPI.listNode({ status: 0 })).data.data;
});
</script>
