from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class _RuntimeAppContext:
    def __init__(self):
        from ktem.settings import BaseSettingGroup, SettingGroup, SettingReasoningGroup
        from theflow.settings import settings as flowsettings

        self.dev_mode = getattr(flowsettings, "KH_MODE", "") == "dev"
        self.app_name = getattr(flowsettings, "KH_APP_NAME", "MARA")
        self.app_version = getattr(flowsettings, "KH_APP_VERSION", "")
        self.f_user_management = getattr(
            flowsettings, "KH_FEATURE_USER_MANAGEMENT", False
        )
        self.default_settings = SettingGroup(
            application=BaseSettingGroup(settings=flowsettings.SETTINGS_APP),
            reasoning=SettingReasoningGroup(settings=flowsettings.SETTINGS_REASONING),
        )
        self._callbacks: dict[str, list] = {}
        self._events: dict[str, list] = {}

        self.register_extensions()
        self.register_reasonings()
        self.initialize_indices()
        self.default_settings.reasoning.finalize()
        self.default_settings.index.finalize()

    def initialize_indices(self):
        from ktem.index import IndexManager
        from ktem.settings import BaseSettingGroup

        self.index_manager = IndexManager(self)
        self.index_manager.on_application_startup()

        for index in self.index_manager.indices:
            options = index.get_user_settings()
            self.default_settings.index.options[index.id] = BaseSettingGroup(
                settings=options
            )

    def register_reasonings(self):
        from ktem.components import reasonings
        from ktem.settings import BaseSettingGroup
        from theflow.settings import settings as flowsettings
        from theflow.utils.modules import import_dotted_string

        if getattr(flowsettings, "KH_REASONINGS", None) is None:
            return

        for value in flowsettings.KH_REASONINGS:
            reasoning_cls = import_dotted_string(value, safe=False)
            rid = reasoning_cls.get_info()["id"]
            reasonings[rid] = reasoning_cls
            options = reasoning_cls().get_user_settings()
            self.default_settings.reasoning.options[rid] = BaseSettingGroup(
                settings=options
            )

    def register_extensions(self):
        import pluggy
        from ktem import extension_protocol
        from ktem.settings import BaseSettingGroup

        self.exman = pluggy.PluginManager("ktem")
        self.exman.add_hookspecs(extension_protocol)
        self.exman.load_setuptools_entrypoints("ktem")

        extension_declarations = self.exman.hook.ktem_declare_extensions()
        for extension_declaration in extension_declarations:
            functionality = extension_declaration["functionality"]
            if "reasoning" not in functionality:
                continue
            for rid, rdec in functionality["reasoning"].items():
                unique_rid = f"{extension_declaration['id']}/{rid}"
                self.default_settings.reasoning.options[unique_rid] = BaseSettingGroup(
                    settings=rdec["settings"],
                )

    def declare_event(self, name: str):
        self._events.setdefault(name, [])

    def subscribe_event(self, name: str, definition: dict):
        self._events.setdefault(name, []).append(definition)

    def get_event(self, name: str) -> list[dict]:
        return self._events.get(name, [])


class _DocQAPreviewService:
    def __init__(self, app):
        from ktem.docqa.preview_support import PreviewSupportService

        self._support = PreviewSupportService(app)

    def resolve_selected_file(
        self, selected_file_ids: list[str] | None, *, user_id=None
    ) -> tuple[str, str, str]:
        return self._support.resolve_selected_file(selected_file_ids, user_id=user_id)

    def resolve_file_path(self, file_id: str, *, user_id=None) -> str:
        return self._support.resolve_file_path(file_id, user_id=user_id)

    def resolve_file_name(self, file_id: str, *, user_id=None) -> str:
        return self._support.resolve_file_name(file_id, user_id=user_id)

    def resolve_sources(self, file_ids, *, user_id=None, strict: bool = True):
        return self._support.resolve_sources(file_ids, user_id=user_id, strict=strict)

    def get_page_context_text(
        self,
        file_id: str,
        file_name: str,
        page_number: int,
        max_chars: int = 7000,
        *,
        user_id=None,
    ) -> str:
        return self._support.get_page_context_text(
            file_id,
            file_name,
            page_number,
            max_chars,
            user_id=user_id,
        )
