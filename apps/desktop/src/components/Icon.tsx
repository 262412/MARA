export type IconName =
  | "add"
  | "book"
  | "chevron"
  | "files"
  | "help"
  | "panel"
  | "resources"
  | "search"
  | "send"
  | "settings"
  | "workbench";

const paths: Record<IconName, React.ReactNode> = {
  add: <path d="M12 5v14M5 12h14" />,
  book: <path d="M5 4.5h10a3 3 0 0 1 3 3V20H8a3 3 0 0 1-3-3V4.5Zm3 0V20" />,
  chevron: <path d="m9 6 6 6-6 6" />,
  files: (
    <>
      <path d="M6 3h8l4 4v14H6z" />
      <path d="M14 3v5h5M9 13h6M9 17h6" />
    </>
  ),
  help: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M9.8 9a2.4 2.4 0 1 1 3.6 2.1c-.9.5-1.4 1-1.4 2M12 17h.01" />
    </>
  ),
  panel: <path d="M4 5h16v14H4zM15 5v14" />,
  resources: (
    <>
      <circle cx="7" cy="7" r="2.5" />
      <circle cx="17" cy="7" r="2.5" />
      <circle cx="12" cy="17" r="2.5" />
      <path d="m9 8.2 2 6M15 8.2l-2 6" />
    </>
  ),
  search: (
    <>
      <circle cx="10.5" cy="10.5" r="6.5" />
      <path d="m15.5 15.5 4 4" />
    </>
  ),
  send: <path d="m4 4 17 8-17 8 3-8-3-8Zm3 8h14" />,
  settings: (
    <>
      <circle cx="12" cy="12" r="3" />
      <path d="M19 13.5v-3l-2-.7-.8-1.9.9-1.9L15 3.9l-1.9.9-1.9-.8-.7-2h-3l-.7 2-1.9.8L3 3.9.9 6l.9 1.9L1 9.8l-2 .7v3l2 .7.8 1.9L.9 18 3 20.1l1.9-.9 1.9.8.7 2h3l.7-2 1.9-.8 1.9.9 2.1-2.1-.9-1.9.8-1.9 2-.7Z" transform="translate(2 -1)" />
    </>
  ),
  workbench: (
    <>
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <path d="M8 4v16M8 10h13" />
    </>
  ),
};

export function Icon({ name, size = 18 }: { name: IconName; size?: number }) {
  return (
    <svg
      aria-hidden="true"
      className="icon"
      fill="none"
      height={size}
      viewBox="0 0 24 24"
      width={size}
    >
      <g stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.7">
        {paths[name]}
      </g>
    </svg>
  );
}
