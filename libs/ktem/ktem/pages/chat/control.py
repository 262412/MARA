import logging
from typing import TypeAlias, cast

import gradio as gr
from ktem.app import BasePage
from ktem.assets import ICONS_DIR
from ktem.auth.service import resolve_request_user_id
from ktem.db.models import User, engine
from ktem.docqa._runtime_session_mutations import RuntimeSessionMutationService
from ktem.docqa._runtime_session_service import RuntimeSessionService
from sqlmodel import Session, select
from theflow.settings import settings as flowsettings

from .chat_suggestion import ChatSuggestion
from .common import STATE

logger = logging.getLogger(__name__)

KH_DEMO_MODE = getattr(flowsettings, "KH_DEMO_MODE", False)
KH_SSO_ENABLED = getattr(flowsettings, "KH_SSO_ENABLED", False)
ASSETS_DIR = str(ICONS_DIR)
Request: TypeAlias = gr.Request | None
_REQUEST = cast(gr.Request, object())


logout_js = """
function () {
    removeFromStorage('google_api_key');
    window.location.href = "/logout";
}
"""


def is_conv_name_valid(name):
    """Check if the conversation name is valid"""
    errors = []
    if len(name) == 0:
        errors.append("Name cannot be empty")
    elif len(name) > 40:
        errors.append("Name cannot be longer than 40 characters")

    return "; ".join(errors)


def _empty_conversation_state(app):
    default_chat_suggestions = [[each] for each in ChatSuggestion.CHAT_SAMPLES]
    indices = []
    for index in app.index_manager.indices:
        if index.selector is None:
            continue
        if isinstance(index.selector, int):
            indices.append(index.default_selector)
        if isinstance(index.selector, tuple):
            indices.extend(index.default_selector)
    return (
        "",
        "",
        "",
        [],
        default_chat_suggestions,
        "",
        None,
        [],
        [],
        False,
        STATE,
        *indices,
    )


def _server_user_id(request, auth_mode):
    if request is _REQUEST:
        return None
    return resolve_request_user_id(request, auth_mode=auth_mode)


class ConversationControl(BasePage):
    """Manage conversation"""

    def __init__(self, app):
        self._app = app
        self.logout_js = logout_js
        self.on_building_ui()

    def on_building_ui(self):
        with gr.Row():
            title_text = "Session" if not KH_DEMO_MODE else "Slides Papers"
            gr.Markdown("## {}".format(title_text))
            self.btn_chat_expand = gr.Button(
                value="",
                icon=f"{ASSETS_DIR}/expand.svg",
                scale=1,
                size="sm",
                elem_classes=["no-background", "body-text-color"],
                elem_id="chat-expand-button",
                visible=False,
            )
        self.conversation_id = gr.State(value="")
        self.conversation = gr.Dropdown(
            label="Chat sessions",
            choices=[],
            container=False,
            filterable=True,
            interactive=True,
            elem_classes=["unset-overflow"],
            elem_id="conversation-dropdown",
        )

        with gr.Row() as self._new_delete:
            self.cb_suggest_chat = gr.Checkbox(
                value=False,
                label="Suggest chat",
                min_width=10,
                scale=6,
                elem_id="suggest-chat-checkbox",
                container=False,
                visible=False,
            )
            self.cb_is_public = gr.Checkbox(
                value=False,
                label="Share this conversation",
                elem_id="is-public-checkbox",
                container=False,
                visible=not KH_DEMO_MODE and not KH_SSO_ENABLED,
            )

            if not KH_DEMO_MODE:
                self.btn_conversation_rn = gr.Button(
                    value="",
                    icon=f"{ASSETS_DIR}/rename.svg",
                    min_width=2,
                    scale=1,
                    size="sm",
                    elem_classes=["no-background", "body-text-color"],
                    elem_id="rename-conv-button",
                )
                self.btn_del = gr.Button(
                    value="",
                    icon=f"{ASSETS_DIR}/delete.svg",
                    min_width=2,
                    scale=1,
                    size="sm",
                    elem_classes=["no-background", "body-text-color"],
                    elem_id="delete-conv-button",
                )
                self.btn_new = gr.Button(
                    value="",
                    icon=f"{ASSETS_DIR}/new.svg",
                    min_width=2,
                    scale=1,
                    size="sm",
                    elem_classes=["no-background", "body-text-color"],
                    elem_id="new-conv-button",
                )
            else:
                self.btn_new = gr.Button(
                    value="New chat",
                    min_width=120,
                    size="sm",
                    scale=1,
                    variant="primary",
                    elem_id="new-conv-button",
                    visible=False,
                )

        if KH_DEMO_MODE:
            with gr.Row():
                self.btn_demo_login = gr.Button(
                    "Sign-in to create new chat",
                    min_width=120,
                    size="sm",
                    scale=1,
                    variant="primary",
                )
                _js_redirect = """
                () => {
                    url = '/login' + window.location.search;
                    window.open(url, '_blank');
                }
                """
                self.btn_demo_login.click(None, js=_js_redirect)

                self.btn_demo_logout = gr.Button(
                    "Sign-out",
                    min_width=120,
                    size="sm",
                    scale=1,
                    visible=False,
                )

        with gr.Row(visible=False) as self._delete_confirm:
            self.btn_del_conf = gr.Button(
                value="Delete",
                variant="stop",
                min_width=10,
            )
            self.btn_del_cnl = gr.Button(value="Cancel", min_width=10)

        with gr.Row():
            self.conversation_rn = gr.Text(
                label="(Enter) to save",
                placeholder="Conversation name",
                container=True,
                scale=5,
                min_width=10,
                interactive=True,
                visible=False,
            )

    def load_chat_history(self, user_id, request: gr.Request = _REQUEST):
        """Reload chat history"""
        resolved_user_id = self._resolve_user_id(user_id, request)
        return self._load_chat_history(resolved_user_id)

    def _load_chat_history(self, user_id):
        can_see_public = False
        with Session(engine) as session:
            statement = select(User).where(User.id == user_id)
            result = session.exec(statement).one_or_none()
            if result is not None:
                if flowsettings.KH_USER_CAN_SEE_PUBLIC:
                    can_see_public = (
                        result.username == flowsettings.KH_USER_CAN_SEE_PUBLIC
                    )
                else:
                    can_see_public = True

        print(f"User-id: {user_id}, can see public conversations: {can_see_public}")
        sessions = self._get_session_service(user_id).list_sessions(
            user_id,
            include_public=can_see_public,
            public_first=can_see_public,
        )
        return [(session.name, session.conversation_id) for session in sessions]

    def reload_conv(self, user_id, request: gr.Request = _REQUEST):
        conv_list = self.load_chat_history(user_id, request)
        if conv_list:
            return gr.update(value=None, choices=conv_list)
        else:
            return gr.update(value=None, choices=[])

    def new_conv(self, user_id, request: gr.Request = _REQUEST):
        """Create new chat"""
        user_id = self._resolve_user_id(user_id, request)
        if user_id is None:
            gr.Warning("Please sign in first (Settings → User Settings)")
            return None, gr.update()
        created = self._get_session_service(user_id).create_session(user_id=user_id)
        history = self._load_chat_history(user_id)
        return created.conversation_id, gr.update(
            value=created.conversation_id,
            choices=history,
        )

    def delete_conv(self, conversation_id, user_id, request: gr.Request = _REQUEST):
        """Delete the selected conversation"""
        if not conversation_id:
            gr.Warning("No conversation selected.")
            return None, gr.update()
        user_id = self._resolve_user_id(user_id, request)
        if user_id is None:
            gr.Warning("Please sign in first (Settings → User Settings)")
            return None, gr.update()
        try:
            self._get_mutation_service(user_id).delete_session(
                conversation_id,
                user_id,
            )
        except PermissionError as exc:
            raise gr.Error(str(exc)) from exc
        history = self._load_chat_history(user_id)
        if history:
            id_ = history[0][1]
            return id_, gr.update(value=id_, choices=history)
        else:
            return None, gr.update(value=None, choices=[])

    def select_conv(self, conversation_id, user_id, request: gr.Request = _REQUEST):
        """Select the conversation"""
        default_chat_suggestions = [[each] for each in ChatSuggestion.CHAT_SAMPLES]
        user_id = self._resolve_user_id(user_id, request)
        try:
            session_info = self._get_session_service(user_id).load_session(
                conversation_id,
                user_id=user_id,
            )
            if session_info is None:
                raise PermissionError(
                    "Conversation is outside the authenticated user scope: "
                    f"conversation_id={conversation_id}"
                )
            id_ = session_info.conversation_id
            name = session_info.name
            is_conv_public = session_info.is_public
            selected = (
                session_info.selected_mapping if user_id == session_info.user_id else {}
            )
            chats = session_info.data_source.get("messages", [])
            chat_suggestions = session_info.data_source.get(
                "chat_suggestions", default_chat_suggestions
            )
            retrieval_history = session_info.retrieval_messages
            plot_history = session_info.plot_history
            info_panel = (
                retrieval_history[-1]
                if retrieval_history
                else "<h5><b>No evidence found.</b></h5>"
            )
            plot_data = plot_history[-1] if plot_history else None
            state = session_info.state
        except Exception as exc:
            logger.warning("Conversation selection failed: %s", exc)
            id_ = ""
            name = ""
            selected = {}
            chats = []
            chat_suggestions = default_chat_suggestions
            retrieval_history = []
            plot_history = []
            info_panel = ""
            plot_data = None
            state = STATE
            is_conv_public = False

        indices = []
        for index in self._app.index_manager.indices:
            # assume that the index has selector
            if index.selector is None:
                continue
            if isinstance(index.selector, int):
                indices.append(selected.get(str(index.id), index.default_selector))
            if isinstance(index.selector, tuple):
                indices.extend(selected.get(str(index.id), index.default_selector))

        return (
            id_,
            id_,
            name,
            chats,
            chat_suggestions,
            info_panel,
            plot_data,
            retrieval_history,
            plot_history,
            is_conv_public,
            state,
            *indices,
        )

    def clear_conv(self):
        return _empty_conversation_state(self._app)

    def rename_conv(
        self,
        conversation_id,
        new_name,
        is_renamed,
        user_id,
        request: gr.Request = _REQUEST,
    ):
        """Rename the conversation"""
        if not is_renamed or KH_DEMO_MODE or user_id is None or not conversation_id:
            return (
                gr.update(),
                conversation_id,
                gr.update(visible=False),
            )

        errors = is_conv_name_valid(new_name)
        if errors:
            gr.Warning(errors)
            return (
                gr.update(),
                conversation_id,
                gr.update(visible=False),
            )

        user_id = self._resolve_user_id(user_id, request)
        try:
            self._get_mutation_service(user_id).rename_session(
                conversation_id,
                new_name,
                user_id,
            )
        except PermissionError as exc:
            raise gr.Error(str(exc)) from exc
        history = self._load_chat_history(user_id)
        gr.Info("Conversation renamed.")
        return (
            gr.update(choices=history),
            conversation_id,
            gr.update(visible=False),
        )

    def persist_chat_suggestions(
        self,
        conversation_id,
        new_suggestions,
        is_updated,
        user_id,
        request: gr.Request = _REQUEST,
    ):
        """Update the conversation's chat suggestions"""
        if not is_updated:
            return

        user_id = self._resolve_user_id(user_id, request)
        if user_id is None:
            gr.Warning("Please sign in first (Settings → User Settings)")
            return gr.update(), ""

        if not conversation_id:
            gr.Warning("No conversation selected.")
            return gr.update(), ""

        try:
            self._get_mutation_service(user_id).update_chat_suggestions(
                conversation_id,
                new_suggestions.iloc[:, 0].tolist(),
                user_id,
            )
        except PermissionError as exc:
            raise gr.Error(str(exc)) from exc
        gr.Info("Chat suggestions updated.")

    @staticmethod
    def _resolve_user_id(user_id, request: Request):
        auth_mode = str(getattr(flowsettings, "MARA_AUTH_MODE", "auto")).lower()
        if auth_mode not in {"password", "sso"}:
            return user_id
        resolved = _server_user_id(request, auth_mode)
        if not resolved:
            raise gr.Error("Authenticated user identity is unavailable.")
        return resolved

    def _get_session_service(self, user_id) -> RuntimeSessionService:
        return RuntimeSessionService(
            app=self._app,
            file_index=None,
            engine=engine,
            resolve_user_id=lambda value=None: user_id if value is None else value,  # type: ignore[misc]
        )

    @staticmethod
    def _get_mutation_service(user_id) -> RuntimeSessionMutationService:
        return RuntimeSessionMutationService(
            engine=engine,
            resolve_user_id=lambda value=None: user_id if value is None else value,  # type: ignore[misc]
        )

    def toggle_demo_login_visibility(self, user_api_key, request: gr.Request):
        try:
            import gradiologin as grlogin

            user = grlogin.get_user(request)
        except (ImportError, AssertionError):
            user = None

        if user:  # or user_api_key:
            return [
                gr.update(visible=True),
                gr.update(visible=True),
                gr.update(visible=True),
                gr.update(visible=False),
            ]
        else:
            return [
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=True),
            ]

    def _on_app_created(self):
        """Reload the conversation once the app is created"""
        self._app.app.load(
            self.reload_conv,
            inputs=[self._app.user_id],
            outputs=[self.conversation],
        )
