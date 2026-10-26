import { request } from "@utils";

const API_PATH = "/task/storage/browse";
export interface StorageObject {
  name?: string;
  key?: string;
  is_dir?: boolean;
  size?: number;
  modified_time?: string;
}
export interface StoragePageResult {
  items: StorageObject[];
  has_next: boolean;
  next_cursor: string | null;
}
export interface FileListParams {
  source_id?: number | null;
  prefix?: string;
  bucket?: string;
  page_size?: number;
  cursor?: string;
}
export interface FilePathBody {
  remote_path: string;
  source_id?: number | null;
  bucket?: string;
}

export default {
  listFiles(params?: FileListParams) {
    return request<ApiResponse<StorageObject[] | StoragePageResult>>({
      url: `${API_PATH}/list`,
      method: "get",
      params,
    });
  },
  listBuckets(params?: { source_id?: number | null }) {
    return request<ApiResponse<string[]>>({ url: `${API_PATH}/buckets`, method: "get", params });
  },
  downloadFile(body: FilePathBody) {
    return request<Blob>({
      url: `${API_PATH}/download`,
      method: "post",
      data: body,
      responseType: "blob",
    });
  },
  downloadDir(body: FilePathBody) {
    return request<Blob>({
      url: `${API_PATH}/download_dir`,
      method: "post",
      data: body,
      responseType: "blob",
    });
  },
};
