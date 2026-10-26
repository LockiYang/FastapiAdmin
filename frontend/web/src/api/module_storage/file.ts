import { request } from "@utils";

export interface Attachment extends UploadFilePath {
  id: number;
  uuid: string;
  topic: string;
  admin_id?: number;
  user_id?: number;
  storage_node_id: number;
  storage_name?: string;
  protocol?: string;
  sha1: string;
  upload_count: number;
  reference_count: number;
  last_upload_time: string;
  created_time: string;
  status: number;
}

const FileAPI = {
  upload(file: File, topic = "file") {
    const body = new FormData();
    body.append("file", file);
    return this.uploadForm(body, topic);
  },
  uploadForm(body: FormData, topic = "file") {
    return request<ApiResponse<UploadFilePath>>({
      url: "/common/file/upload",
      method: "post",
      params: { upload_type: topic },
      data: body,
      headers: { "Content-Type": "multipart/form-data" },
    });
  },
  page(
    params: PageQuery & {
      origin_name?: string;
      topic?: string;
      storage_node_id?: number;
      status?: number;
    }
  ) {
    return request<ApiResponse<PageResult<Attachment>>>({
      url: "/task/storage/file/page",
      method: "get",
      params,
    });
  },
  detail(id: number) {
    return request<ApiResponse<Attachment>>({
      url: `/task/storage/file/detail/${id}`,
      method: "get",
    });
  },
  update(id: number, status: number) {
    return request<ApiResponse>({
      url: `/task/storage/file/update/${id}`,
      method: "put",
      data: { status },
    });
  },
  delete(ids: number[]) {
    return request<ApiResponse>({ url: "/task/storage/file/delete", method: "delete", data: ids });
  },
};
export default FileAPI;
