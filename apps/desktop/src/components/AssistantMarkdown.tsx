import type { ComponentPropsWithoutRef, ReactNode } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import rehypeKatex from "rehype-katex";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";

type AssistantMarkdownProps = {
  content: string;
};

const components: Components = {
  a: SafeMarkdownLink,
  img: () => null,
};

export function AssistantMarkdown({ content }: AssistantMarkdownProps) {
  return (
    <div className="answer-content">
      <ReactMarkdown
        components={components}
        rehypePlugins={[rehypeKatex]}
        remarkPlugins={[remarkGfm, remarkMath]}
        skipHtml
        urlTransform={safeMarkdownUrl}
      >
        {preserveCitationMarkers(content)}
      </ReactMarkdown>
    </div>
  );
}

function preserveCitationMarkers(content: string): string {
  return content.replace(
    /<a href=['"]#['"] class=['"]citation['"] id=['"]mark-(\d+)['"]>【(\d+)】<\/a>/gi,
    (_match, id: string, label: string) => (id === label ? `【${label}】` : ""),
  );
}

function SafeMarkdownLink({
  children,
  href,
  ...properties
}: ComponentPropsWithoutRef<"a"> & { children?: ReactNode }) {
  const safeHref = safeMarkdownUrl(href ?? "");
  if (!safeHref) {
    return <span>{children}</span>;
  }
  return (
    <a
      {...properties}
      href={safeHref}
      rel="noreferrer noopener"
      target="_blank"
    >
      {children}
    </a>
  );
}

function safeMarkdownUrl(value: string): string {
  const normalized = value.trim();
  if (/^#[A-Za-z0-9_.:-]+$/.test(normalized)) {
    return normalized;
  }
  try {
    const parsed = new URL(normalized);
    return parsed.protocol === "https:" || parsed.protocol === "http:"
      ? normalized
      : "";
  } catch {
    return "";
  }
}
