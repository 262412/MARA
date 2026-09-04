export type ModelProvider =
  | "none"
  | "openai_compatible"
  | "azure_openai"
  | "ollama";

export type CredentialStorage = "none" | "secure" | "session";

export type ModelRouteInput = {
  provider: ModelProvider;
  base_url: string;
  model: string;
  api_version: string;
  credential: string | null;
};

export type ModelSettingsInput = {
  chat: ModelRouteInput;
  embedding: ModelRouteInput;
};

export type ModelRouteStatus = Omit<ModelRouteInput, "credential"> & {
  credential_present: boolean;
  credential_storage: CredentialStorage;
};

export type ModelSettingsStatus = {
  chat: ModelRouteStatus;
  embedding: ModelRouteStatus;
  secure_storage_available: boolean;
  source: "compatibility" | "desktop";
};
