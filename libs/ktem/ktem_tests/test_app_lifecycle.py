from ktem.app import BaseApp, BasePage


class _RecorderPage(BasePage):
    public_events = ["recorder:event"]
    alias_child: BasePage | None
    legacy_child: BasePage | None

    def __init__(self, app, events, name):
        super().__init__(app)
        self._events = events
        self._name = name
        self.alias_child = None
        self.legacy_child = None

    def declare_public_events(self):
        self._events.append((self._name, "declare"))
        super().declare_public_events()

    def on_subscribe_public_events(self):
        self._events.append((self._name, "subscribe"))

    def on_register_events(self):
        self._events.append((self._name, "register"))

    def _on_app_created(self):
        self._events.append((self._name, "created"))


class _RecorderApp(BaseApp):
    alias_child: BasePage | None
    legacy_child: BasePage | None
    helper: object | None

    def __init__(self):
        self._registered_child_pages = []
        self._events = {}
        self._declared = []
        self._tracker = []
        self.alias_child = None
        self.legacy_child = None
        self.helper = None

    def declare_event(self, name: str):
        self._declared.append(name)
        self._events[name] = []

    def on_subscribe_public_events(self):
        self._tracker.append(("app", "subscribe"))

    def on_register_events(self):
        self._tracker.append(("app", "register"))

    def _on_app_created(self):
        self._tracker.append(("app", "created"))


class _LegacyPage(BasePage):
    public_events = ["legacy:event"]

    def __init__(self, app, events, name):
        self._app = app
        self._events = events
        self._name = name

    def on_subscribe_public_events(self):
        self._events.append((self._name, "subscribe"))

    def on_register_events(self):
        self._events.append((self._name, "register"))

    def _on_app_created(self):
        self._events.append((self._name, "created"))


def test_base_page_child_lifecycle_prefers_registered_pages_without_duplicates():
    tracker: list[tuple[str, str]] = []
    app = _RecorderApp()
    page = _RecorderPage(app, tracker, "parent")
    child = page.register_child_page(
        "registered_child", _RecorderPage(app, tracker, "child")
    )
    page.alias_child = child
    page.legacy_child = _RecorderPage(app, tracker, "legacy")

    page.declare_public_events()
    page.subscribe_public_events()
    page.register_events()
    page.on_app_created()

    assert tracker == [
        ("parent", "declare"),
        ("child", "declare"),
        ("legacy", "declare"),
        ("parent", "subscribe"),
        ("child", "subscribe"),
        ("legacy", "subscribe"),
        ("parent", "register"),
        ("child", "register"),
        ("legacy", "register"),
        ("parent", "created"),
        ("child", "created"),
        ("legacy", "created"),
    ]


def test_base_app_child_lifecycle_prefers_registered_pages_without_duplicates():
    app = _RecorderApp()
    child = app.register_child_page(
        "registered_child", _RecorderPage(app, app._tracker, "child")
    )
    app.alias_child = child
    app.legacy_child = _RecorderPage(app, app._tracker, "legacy")

    app.declare_public_events()
    app.subscribe_public_events()
    app.register_events()
    app.on_app_created()

    assert app._tracker == [
        ("child", "declare"),
        ("legacy", "declare"),
        ("app", "subscribe"),
        ("child", "subscribe"),
        ("legacy", "subscribe"),
        ("app", "register"),
        ("child", "register"),
        ("legacy", "register"),
        ("app", "created"),
        ("child", "created"),
        ("legacy", "created"),
    ]
    assert app._declared == ["recorder:event", "recorder:event"]


def test_base_page_lifecycle_supports_legacy_pages_without_base_init():
    app = _RecorderApp()
    legacy_page = _LegacyPage(app, app._tracker, "legacy")

    legacy_page.declare_public_events()
    legacy_page.subscribe_public_events()
    legacy_page.register_events()
    legacy_page.on_app_created()

    assert app._declared == ["legacy:event"]
    assert app._tracker == [
        ("legacy", "subscribe"),
        ("legacy", "register"),
        ("legacy", "created"),
    ]


def test_register_child_page_ignores_non_basepage_objects():
    app = _RecorderApp()
    helper = object()

    returned = app.register_child_page("helper", helper)
    app.declare_public_events()
    app.subscribe_public_events()
    app.register_events()
    app.on_app_created()

    assert returned is helper
    assert app.helper is helper
    assert app._declared == []
    assert app._tracker == [
        ("app", "subscribe"),
        ("app", "register"),
        ("app", "created"),
    ]
