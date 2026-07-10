import importlib
import importlib.util
import warnings
from types import SimpleNamespace

import pytest


def _policy_module():
    package_spec = importlib.util.find_spec("ktem.auth")
    assert package_spec is not None, "ktem.auth must provide shared auth primitives"

    module_spec = importlib.util.find_spec("ktem.auth.policy")
    assert module_spec is not None, "ktem.auth.policy must centralize auth policy"
    return importlib.import_module("ktem.auth.policy")


@pytest.mark.parametrize(
    "host",
    [None, "", "localhost", "LOCALHOST", "127.0.0.1", "127.25.4.9", "::1"],
)
@pytest.mark.parametrize("mode", [None, "auto", "local"])
def test_local_auth_modes_allow_only_loopback_hosts(host, mode):
    policy = _policy_module()

    assert policy.resolve_auth_mode(configured_mode=mode, host=host) == (mode or "auto")


@pytest.mark.parametrize("host", ["0.0.0.0", "::", "*", "192.168.1.20"])
@pytest.mark.parametrize("mode", ["auto", "local"])
def test_local_auth_modes_fail_closed_on_non_loopback_hosts(host, mode):
    policy = _policy_module()

    with pytest.raises(
        policy.AuthConfigurationError,
        match="MARA_AUTH_MODE=password.*MARA_AUTH_MODE=sso",
    ):
        policy.resolve_auth_mode(configured_mode=mode, host=host)


@pytest.mark.parametrize("mode", ["password", "sso"])
@pytest.mark.parametrize("host", ["0.0.0.0", "::", "*", "mara.example.test"])
def test_authenticated_modes_allow_non_loopback_hosts(host, mode):
    policy = _policy_module()

    assert policy.resolve_auth_mode(configured_mode=mode, host=host) == mode


@pytest.mark.parametrize("mode", ["", "PASSWORD", "disabled", "local-password"])
def test_invalid_auth_mode_is_rejected(mode):
    policy = _policy_module()

    with pytest.raises(policy.AuthConfigurationError, match="auto, local, password, sso"):
        policy.resolve_auth_mode(configured_mode=mode, host="localhost")


def test_legacy_sso_true_maps_to_sso_with_deprecation_warning():
    policy = _policy_module()

    with pytest.warns(DeprecationWarning, match="KH_SSO_ENABLED.*MARA_AUTH_MODE=sso"):
        mode = policy.resolve_auth_mode(
            configured_mode=None,
            legacy_sso_enabled=True,
            host="0.0.0.0",
        )

    assert mode == "sso"


def test_canonical_auth_mode_takes_precedence_over_legacy_sso():
    policy = _policy_module()

    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        mode = policy.resolve_auth_mode(
            configured_mode="password",
            legacy_sso_enabled=True,
            host="0.0.0.0",
        )

    assert mode == "password"
    assert captured == []


def test_absent_legacy_bootstrap_credentials_do_not_create_a_user():
    policy = _policy_module()
    settings = SimpleNamespace(
        KH_FEATURE_USER_MANAGEMENT_ADMIN="",
        KH_FEATURE_USER_MANAGEMENT_PASSWORD="",
    )

    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        credentials = policy.resolve_legacy_bootstrap_credentials(settings)

    assert credentials is None
    assert captured == []


def test_safe_legacy_bootstrap_credentials_are_deprecated():
    policy = _policy_module()
    settings = SimpleNamespace(
        KH_FEATURE_USER_MANAGEMENT_ADMIN="operator",
        KH_FEATURE_USER_MANAGEMENT_PASSWORD="Operator123!",
    )

    with pytest.warns(
        DeprecationWarning,
        match="KH_FEATURE_USER_MANAGEMENT_ADMIN.*one minor release",
    ):
        credentials = policy.resolve_legacy_bootstrap_credentials(settings)

    assert credentials == ("operator", "Operator123!")


@pytest.mark.parametrize(
    ("username", "password", "message"),
    [
        ("operator", "", "both.*nonempty"),
        ("", "Operator123!", "both.*nonempty"),
        ("admin", "admin", "admin/admin"),
    ],
)
def test_unsafe_legacy_bootstrap_credentials_are_rejected(
    username,
    password,
    message,
):
    policy = _policy_module()
    settings = SimpleNamespace(
        KH_FEATURE_USER_MANAGEMENT_ADMIN=username,
        KH_FEATURE_USER_MANAGEMENT_PASSWORD=password,
    )

    with pytest.warns(DeprecationWarning):
        with pytest.raises(policy.AuthConfigurationError, match=message):
            policy.resolve_legacy_bootstrap_credentials(settings)
