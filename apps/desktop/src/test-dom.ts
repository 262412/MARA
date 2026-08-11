import { act, type ReactNode } from "react";
import type { Root } from "react-dom/client";
import { JSDOM } from "jsdom";

type InstalledDom = {
  cleanup(): Promise<void>;
  document: Document;
  window: Window & typeof globalThis;
};

const GLOBAL_NAMES = [
  "window",
  "document",
  "navigator",
  "HTMLElement",
  "HTMLInputElement",
  "HTMLTextAreaElement",
  "Event",
  "MouseEvent",
  "KeyboardEvent",
  "FocusEvent",
] as const;

export async function renderInDom(
  node: ReactNode,
  prepareWindow?: (window: Window & typeof globalThis) => void,
): Promise<InstalledDom> {
  const descriptors = new Map<string, PropertyDescriptor | undefined>();
  const dom = new JSDOM("<!doctype html><html><body><div id=\"root\"></div></body></html>", {
    url: "https://renderer.invalid/",
  });
  const browserWindow = dom.window as unknown as Window & typeof globalThis;
  prepareWindow?.(browserWindow);
  for (const name of GLOBAL_NAMES) {
    descriptors.set(name, Object.getOwnPropertyDescriptor(globalThis, name));
    Object.defineProperty(globalThis, name, {
      configurable: true,
      value: browserWindow[name],
      writable: true,
    });
  }
  const actDescriptor = Object.getOwnPropertyDescriptor(
    globalThis,
    "IS_REACT_ACT_ENVIRONMENT",
  );
  Object.defineProperty(globalThis, "IS_REACT_ACT_ENVIRONMENT", {
    configurable: true,
    value: true,
    writable: true,
  });
  const { createRoot } = await import("react-dom/client");
  let root: Root | undefined;
  await act(async () => {
    root = createRoot(browserWindow.document.getElementById("root")!);
    root.render(node);
    await flushPromises();
  });

  return {
    document: browserWindow.document,
    window: browserWindow,
    async cleanup() {
      if (root) {
        await act(async () => root?.unmount());
      }
      dom.window.close();
      for (const name of GLOBAL_NAMES) {
        restoreDescriptor(name, descriptors.get(name));
      }
      restoreDescriptor("IS_REACT_ACT_ENVIRONMENT", actDescriptor);
    },
  };
}

export async function dispatch(element: Element | Window, event: Event): Promise<void> {
  await act(async () => {
    element.dispatchEvent(event);
    await flushPromises();
  });
}

export async function click(element: HTMLElement): Promise<void> {
  await act(async () => {
    element.click();
    await flushPromises();
  });
}

export async function setInputValue(
  input: HTMLInputElement | HTMLTextAreaElement,
  value: string,
): Promise<void> {
  const descriptor = Object.getOwnPropertyDescriptor(
    Object.getPrototypeOf(input),
    "value",
  );
  descriptor?.set?.call(input, value);
  await dispatch(input, new window.Event("input", { bubbles: true }));
}

export async function flushPromises(): Promise<void> {
  await new Promise<void>((resolve) => setImmediate(resolve));
}

function restoreDescriptor(
  name: string,
  descriptor: PropertyDescriptor | undefined,
): void {
  if (descriptor) {
    Object.defineProperty(globalThis, name, descriptor);
  } else {
    Reflect.deleteProperty(globalThis, name);
  }
}
