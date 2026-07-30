export type DoctorPayload = {
  ok: boolean;
  app_name: string;
  default_user_id: string;
  index_name: string;
  index_id: number | null;
  llm_default: string;
  embedding_default: string;
  file_count: number;
  session_count: number;
  graph_cache_dir: string;
  issues: string[];
  warnings: string[];
};

export type DoctorResponse = {
  request_id: string;
  doctor: DoctorPayload;
};
