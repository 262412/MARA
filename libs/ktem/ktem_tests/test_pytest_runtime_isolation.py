from pathlib import Path


def test_package_local_pytest_isolates_runtime_before_settings_import(
    mara_test_runtime_paths,
):
    from theflow.settings import settings as flowsettings

    assert Path(flowsettings.KH_APP_DATA_DIR) == mara_test_runtime_paths.app_data_dir
    assert flowsettings.KH_DATABASE == (
        f"sqlite:///{mara_test_runtime_paths.database_path}"
    )
    assert Path(flowsettings.KH_FILESTORAGE_PATH) == (
        mara_test_runtime_paths.file_storage_path
    )
