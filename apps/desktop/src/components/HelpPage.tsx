import { useLanguage } from "../i18n";

type HelpPageProps = {
  onOpenResources: () => void;
  onOpenSettings: () => void;
  version?: string;
};

export function HelpPage({
  onOpenResources,
  onOpenSettings,
  version,
}: HelpPageProps) {
  const { t } = useLanguage();
  return (
    <main className="standalone-page help-page" id="main-workspace">
      <header className="standalone-header">
        <div>
          <p className="eyebrow">{t("help.eyebrow")}</p>
          <h1 data-page-title tabIndex={-1}>{t("help.title")}</h1>
          <p>{t("help.description", { version: version ? `v${version}` : "" })}</p>
        </div>
      </header>
      <section>
        <h2>{t("help.basics")}</h2>
        <ol>
          <li>{t("help.stepSettings")}</li>
          <li>{t("help.stepFiles")}</li>
          <li>{t("help.stepTask")}</li>
          <li>{t("help.stepAnswer")}</li>
        </ol>
      </section>
      <section>
        <h2>{t("help.modelConfiguration")}</h2>
        <p>{t("help.modelDescription")}</p>
        <button onClick={onOpenSettings} type="button">{t("help.openSettings")}</button>
      </section>
      <section>
        <h2>{t("help.shortcuts")}</h2>
        <dl className="shortcut-list">
          <div><dt>Ctrl/⌘+N</dt><dd>{t("help.shortcutNewTask")}</dd></div>
          <div><dt>Ctrl/⌘+,</dt><dd>{t("help.shortcutSettings")}</dd></div>
          <div><dt>Ctrl/⌘+L</dt><dd>{t("help.shortcutFocus")}</dd></div>
          <div><dt>Enter</dt><dd>{t("help.shortcutSend")}</dd></div>
          <div><dt>Alt+Enter</dt><dd>{t("help.shortcutNewline")}</dd></div>
          <div><dt>Ctrl/⌘+Enter</dt><dd>{t("help.shortcutCompatible")}</dd></div>
        </dl>
      </section>
      <section>
        <h2>{t("help.diagnostics")}</h2>
        <p>{t("help.diagnosticsDescription")}</p>
        <button onClick={onOpenResources} type="button">{t("help.openResources")}</button>
      </section>
    </main>
  );
}
