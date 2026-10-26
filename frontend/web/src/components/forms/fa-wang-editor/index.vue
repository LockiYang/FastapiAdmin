<!-- WangEditor 富文本编辑器 插件地址：https://www.wangeditor.com/ -->
<template>
  <div class="editor-wrapper">
    <Toolbar
      class="editor-toolbar"
      :editor="editorRef"
      :mode="mode"
      :defaultConfig="toolbarConfig"
    />
    <Editor
      :style="{ height: height, overflowY: 'hidden' }"
      v-model="modelValue"
      :mode="mode"
      :defaultConfig="editorConfig"
      @onCreated="onCreateEditor"
    />
  </div>
</template>

<script setup lang="ts">
import "@wangeditor-next/editor/dist/css/style.css";
import { onBeforeUnmount, onMounted, onUnmounted, shallowRef, computed } from "vue";
import { Editor, Toolbar } from "@wangeditor-next/editor-for-vue";
import FileAPI from "@/api/module_storage/file";
import { IDomEditor, IToolbarConfig, IEditorConfig } from "@wangeditor-next/editor";
import { ElMessage } from "element-plus";

defineOptions({ name: "FaWangEditor" });

type InsertFnType = (url: string, alt: string, href: string) => void;

// Props 定义
interface Props {
  /** 编辑器高度 */
  height?: string;
  /** 自定义工具栏配置 */
  toolbarKeys?: string[];
  /** 插入新工具到指定位置 */
  insertKeys?: { index: number; keys: string[] };
  /** 排除的工具栏项 */
  excludeKeys?: string[];
  /** 编辑器模式 */
  mode?: "default" | "simple";
  /** 占位符文本 */
  placeholder?: string;
  /** 上传配置 */
  uploadConfig?: {
    maxFileSize?: number;
    maxNumberOfFiles?: number;
  };
}

const props = withDefaults(defineProps<Props>(), {
  height: "500px",
  mode: "default",
  placeholder: "请输入内容...",
  excludeKeys: () => ["fontFamily"],
});

const modelValue = defineModel<string>({ required: true });

// 编辑器实例
const editorRef = shallowRef<IDomEditor>();

// 常量配置
const DEFAULT_UPLOAD_CONFIG = {
  maxFileSize: 3 * 1024 * 1024, // 3MB
  maxNumberOfFiles: 10,
  fieldName: "file",
  allowedFileTypes: ["image/*"],
} as const;

// 合并上传配置
const mergedUploadConfig = computed(() => ({
  ...DEFAULT_UPLOAD_CONFIG,
  ...props.uploadConfig,
}));

// 工具栏配置
const toolbarConfig = computed((): Partial<IToolbarConfig> => {
  const config: Partial<IToolbarConfig> = {};

  // 完全自定义工具栏
  if (props.toolbarKeys && props.toolbarKeys.length > 0) {
    config.toolbarKeys = props.toolbarKeys;
  }

  // 插入新工具
  if (props.insertKeys) {
    config.insertKeys = props.insertKeys;
  }

  // 排除工具
  if (props.excludeKeys && props.excludeKeys.length > 0) {
    config.excludeKeys = props.excludeKeys;
  }

  return config;
});

// 编辑器配置
const editorConfig: Partial<IEditorConfig> = {
  placeholder: props.placeholder,
  MENU_CONF: {
    uploadImage: {
      fieldName: mergedUploadConfig.value.fieldName,
      maxFileSize: mergedUploadConfig.value.maxFileSize,
      maxNumberOfFiles: mergedUploadConfig.value.maxNumberOfFiles,
      allowedFileTypes: [...mergedUploadConfig.value.allowedFileTypes],
      customUpload: async (file: File, insertFn: InsertFnType) => {
        if (file.size > mergedUploadConfig.value.maxFileSize) {
          ElMessage.error("图片大小超过限制");
          return;
        }
        try {
          const result = (await FileAPI.upload(file, "attachment")).data.data;
          insertFn(result.file_url, result.origin_name, result.file_url);
        } catch (error) {
          ElMessage.error("图片上传失败");
          throw error;
        }
      },
    },
  },
};

// 编辑器创建回调
const onCreateEditor = (editor: IDomEditor) => {
  editorRef.value = editor;

  // 监听全屏事件
  editor.on("fullScreen", () => {
    // 全屏状态由 wangEditor 内部管理
  });

  // 确保在编辑器创建后应用自定义图标
  applyCustomIcons();
};

// 图标重试定时器（提升到顶层以便 onUnmounted 访问）
let _iconTimerId: ReturnType<typeof setTimeout> | null = null;

// 应用自定义图标（带重试机制）
//
// 注意：递归 setTimeout 用于等待 wangEditor 工具栏 DOM 渲染完成。
// 组件卸载时必须清理，避免定时器在编辑器实例已销毁后继续执行。
const applyCustomIcons = () => {
  let retryCount = 0;
  const maxRetries = 10;
  const retryDelay = 100;

  const tryApplyIcons = () => {
    const editor = editorRef.value;
    if (!editor) {
      if (retryCount < maxRetries) {
        retryCount++;
        _iconTimerId = setTimeout(tryApplyIcons, retryDelay);
      }
      return;
    }

    // 获取当前编辑器的工具栏容器
    const editorContainer = editor.getEditableContainer().closest(".editor-wrapper");
    if (!editorContainer) {
      if (retryCount < maxRetries) {
        retryCount++;
        _iconTimerId = setTimeout(tryApplyIcons, retryDelay);
      }
      return;
    }

    const toolbar = editorContainer.querySelector(".w-e-toolbar");
    const toolbarButtons = editorContainer.querySelectorAll(".w-e-bar-item button[data-menu-key]");

    if (toolbar && toolbarButtons.length > 0) {
      return;
    }

    // 如果工具栏还没渲染完成，继续重试
    if (retryCount < maxRetries) {
      retryCount++;
      _iconTimerId = setTimeout(tryApplyIcons, retryDelay);
    } else {
      console.warn("工具栏渲染超时，无法应用自定义图标 - 编辑器实例:", editor.id);
    }
  };

  // 使用 requestAnimationFrame 确保在下一帧执行
  requestAnimationFrame(tryApplyIcons);
};

// 组件卸载时清理挂起的重试定时器（需在 setup 顶层注册）
onUnmounted(() => {
  if (_iconTimerId !== null) {
    clearTimeout(_iconTimerId);
    _iconTimerId = null;
  }
});

// 暴露编辑器实例和方法
defineExpose({
  /** 获取编辑器实例 */
  getEditor: () => editorRef.value,
  /** 设置编辑器内容 */
  setHtml: (html: string) => editorRef.value?.setHtml(html),
  /** 获取编辑器内容 */
  getHtml: () => editorRef.value?.getHtml(),
  /** 清空编辑器 */
  clear: () => editorRef.value?.clear(),
  /** 聚焦编辑器 */
  focus: () => editorRef.value?.focus(),
});

// 生命周期
onMounted(() => {
  // 图标替换已在 onCreateEditor 中处理
});

onBeforeUnmount(() => {
  const editor = editorRef.value;
  if (editor) {
    editor.destroy();
  }
});
</script>

<style lang="scss">
$box-radius: calc(var(--custom-radius) / 3 + 2px);

/* 全屏容器 z-index 调整 */
.w-e-full-screen-container {
  z-index: 100 !important;
}

/* 编辑器容器 */
.editor-wrapper {
  width: 100%;
  height: 100%;
  border: 1px solid var(--fa-gray-300);
  border-radius: $box-radius !important;

  .w-e-bar {
    border-radius: $box-radius $box-radius 0 0 !important;
  }

  .menu-item {
    display: flex;
    flex-direction: row;
    align-items: center;

    i {
      margin-right: 5px;
    }
  }

  /* 工具栏 */
  .editor-toolbar {
    border-bottom: 1px solid var(--default-border);
  }

  /* 下拉选择框配置 */
  .w-e-select-list {
    min-width: 140px;
    padding: 5px 10px 10px;
    border: none;
    border-radius: $box-radius;
  }

  /* 下拉选择框元素配置 */
  .w-e-select-list ul li {
    margin-top: 5px;
    font-size: 15px !important;
    border-radius: $box-radius;
  }

  /* 下拉选择框 正文文字大小调整 */
  .w-e-select-list ul li:last-of-type {
    font-size: 16px !important;
  }

  /* 下拉选择框 hover 样式调整 */
  .w-e-select-list ul li:hover {
    background-color: var(--fa-gray-200);
  }

  :root {
    /* 激活颜色 */
    --w-e-toolbar-active-bg-color: var(--fa-gray-200);

    /* toolbar 图标和文字颜色 */
    --w-e-toolbar-color: #000;

    /* 表格选中时候的边框颜色 */
    --w-e-textarea-selected-border-color: #ddd;

    /* 表格头背景颜色 */
    --w-e-textarea-slight-bg-color: var(--fa-gray-200);
  }

  /* 工具栏按钮样式 */
  .w-e-bar-item svg {
    fill: var(--fa-gray-800);
  }

  .w-e-bar-item button {
    color: var(--fa-gray-800);
    border-radius: $box-radius;
  }

  /* 工具栏 hover 按钮背景颜色 */
  .w-e-bar-item button:hover {
    background-color: var(--fa-gray-200);
  }

  /* 工具栏分割线 */
  .w-e-bar-divider {
    height: 20px;
    margin-top: 10px;
    background-color: var(--fa-gray-400);
  }

  /* 工具栏菜单 */
  .w-e-bar-item-group .w-e-bar-item-menus-container {
    min-width: 120px;
    padding: 10px 0;
    border: none;
    border-radius: $box-radius;

    .w-e-bar-item {
      button {
        width: 100%;
        margin: 0 5px;
      }
    }
  }

  /* 代码块 */
  .w-e-text-container [data-slate-editor] pre > code {
    padding: 0.6rem 1rem;
    background-color: var(--fa-gray-50);
    border-radius: $box-radius;
  }

  /* 弹出框 */
  .w-e-drop-panel {
    border: 0;
    border-radius: $box-radius;
  }

  a {
    color: #318ef4;
  }

  .w-e-text-container {
    [data-slate-editor] {
      h1,
      h2,
      h3,
      h4,
      h5,
      h6 {
        margin: 0.8em 0 0.4em;
        font-weight: 700;
        line-height: 1.35;
      }

      h1 {
        font-size: 2em;
      }

      h2 {
        font-size: 1.5em;
      }

      h3 {
        font-size: 1.25em;
      }

      h4 {
        font-size: 1.125em;
      }

      h5 {
        font-size: 1em;
      }

      h6 {
        font-size: 0.875em;
      }

      ul,
      ol {
        padding-left: 1.5em;
        margin: 0.8em 0;
      }

      ul {
        list-style: disc;
      }

      ol {
        list-style: decimal;
      }

      li {
        margin: 0.25em 0;
      }

      ul ul {
        list-style: circle;
      }

      ul ul ul {
        list-style: square;
      }
    }

    strong,
    b {
      font-weight: 700;
    }

    i,
    em {
      font-style: italic;
    }
  }

  /* 表格样式优化 */
  .w-e-text-container [data-slate-editor] .table-container th {
    border-right: none;
  }

  .w-e-text-container [data-slate-editor] .table-container th:last-of-type {
    border-right: 1px solid #ccc !important;
  }

  /* 引用 */
  .w-e-text-container [data-slate-editor] blockquote {
    background-color: var(--fa-gray-200);
    border-left: 4px solid var(--fa-gray-300);
  }

  /* 输入区域弹出 bar  */
  .w-e-hover-bar {
    border-radius: $box-radius;
  }

  /* 超链接弹窗 */
  .w-e-modal {
    border: none;
    border-radius: $box-radius;
  }

  /* 图片样式调整 */
  .w-e-text-container [data-slate-editor] .w-e-selected-image-container {
    overflow: inherit;

    &:hover {
      border: 0;
    }

    img {
      border: 1px solid transparent;
      transition: border 0.3s;

      &:hover {
        border: 1px solid var(--el-color-primary) !important;
      }
    }

    .w-e-image-dragger {
      width: 12px;
      height: 12px;
      background-color: var(--el-color-primary);
      border: 2px solid #fff;
      border-radius: $box-radius;
    }

    .left-top {
      top: -6px;
      left: -6px;
    }

    .right-top {
      top: -6px;
      right: -6px;
    }

    .left-bottom {
      bottom: -6px;
      left: -6px;
    }

    .right-bottom {
      right: -6px;
      bottom: -6px;
    }
  }
}
</style>
