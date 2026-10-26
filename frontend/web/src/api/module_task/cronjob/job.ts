import { request } from "@utils";

const API_PATH = "/task/cronjob/job";

const JobAPI = {
  getSchedulerStatus() {
    return request<ApiResponse<SchedulerStatus>>({
      url: `${API_PATH}/scheduler/status`,
      method: "get",
    });
  },

  getSchedulerJobs() {
    return request<ApiResponse<SchedulerJob[]>>({
      url: `${API_PATH}/scheduler/jobs`,
      method: "get",
    });
  },

  pauseScheduler() {
    return request<ApiResponse>({
      url: `${API_PATH}/scheduler/pause`,
      method: "post",
    });
  },

  resumeScheduler() {
    return request<ApiResponse>({
      url: `${API_PATH}/scheduler/resume`,
      method: "post",
    });
  },

  getJobLogList(query: JobLogPageQuery) {
    return request<ApiResponse<PageResult<JobLogTable>>>({
      url: `${API_PATH}/log/list`,
      method: "get",
      params: query,
    });
  },

  getJobLogDetail(id: number) {
    return request<ApiResponse<JobLogTable>>({
      url: `${API_PATH}/log/detail/${id}`,
      method: "get",
    });
  },

  deleteJobLog(ids: number[]) {
    return request<ApiResponse>({
      url: `${API_PATH}/log/delete`,
      method: "delete",
      data: ids,
    });
  },
};

export default JobAPI;

export interface SchedulerStatus {
  status: string;
  is_running: boolean;
  job_count: number;
  code_exec_enabled: boolean;
}

export interface SchedulerJob {
  id: string;
  name: string;
  trigger: string;
  next_run_time?: string;
  status: number;
  schedulable: boolean;
  unschedulable_reason?: string;
}

export interface JobLogPageQuery extends PageQuery, UserByQueryParams {
  job_id?: string;
  job_name?: string;
  trigger_type?: string;
  status?: number;
}

export interface JobLogTable extends BaseType {
  job_id: string;
  job_name?: string;
  trigger_type?: string;
  started_time?: string;
  finished_time?: string;
  duration_ms?: number;
  result?: string;
  error?: string;
  status?: number;
  description?: string;
}
