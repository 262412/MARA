export type FileRecord = {
  file_id: string;
  name: string;
  size: number;
  tokens: number;
  loader: string;
  date_created: string | null;
};

export type FileListResponse = {
  request_id: string;
  files: FileRecord[];
};
