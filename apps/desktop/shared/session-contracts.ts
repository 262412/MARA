export type SessionSummary = {
  conversation_id: string;
  name: string;
  message_count: number;
  graph_source_count: number;
  origin: string;
  is_public: boolean;
  date_created: string | null;
  date_updated: string | null;
};

export type SessionListResponse = {
  request_id: string;
  sessions: SessionSummary[];
};
