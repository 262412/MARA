import type { RuntimeStatus } from "../electron/sidecar-manager";

type MaraDesktopBridge = {
  getRuntimeStatus(): Promise<RuntimeStatus>;
  onRuntimeStatus(listener: (status: RuntimeStatus) => void): () => void;
  platform: NodeJS.Platform;
};

declare global {
  interface Window {
    maraDesktop?: MaraDesktopBridge;
  }
}

export {};
