from pathlib import Path

import pytest

from kotaemon.contribs.promptui.config import export_pipeline_to_config
from kotaemon.contribs.promptui.export import export_from_dict
from kotaemon.contribs.promptui.ui import build_from_dict

from .simple_pipeline import Pipeline


def test_internal_promptui_tunnel_is_retired_without_downloads_or_embedded_secrets():
    from kotaemon.contribs.promptui.tunnel import Tunnel

    source = (
        Path(__file__).parents[1] / "kotaemon/contribs/promptui/tunnel.py"
    ).read_text(encoding="utf-8")
    tunnel = Tunnel(appname="demo", username="operator", local_port=7860)

    with pytest.raises(RuntimeError, match="retired"):
        tunnel.run()
    for forbidden in ("requests.get", "subprocess.Popen", "--token", "chmod"):
        assert forbidden not in source


class TestPromptConfig:
    def test_export_prompt_config(self):
        """Test if the prompt config is exported correctly"""
        pipeline = Pipeline()
        config_dict = export_pipeline_to_config(pipeline)
        config = list(config_dict.values())[0]

        assert "inputs" in config, "inputs should be in config"
        assert "text" in config["inputs"], "inputs should have config"

        assert "params" in config, "params should be in config"
        assert "llm.deployment_name" in config["params"]
        assert "llm.azure_endpoint" in config["params"]
        assert "llm.openai_api_key" in config["params"]
        assert "llm.openai_api_version" in config["params"]
        assert "llm.request_timeout" in config["params"]
        assert "llm.temperature" in config["params"]


class TestPromptUI:
    def test_uigeneration(self):
        """Test if the gradio UI is exposed without any problem"""
        pipeline = Pipeline()
        config = export_pipeline_to_config(pipeline)

        build_from_dict(config)


class TestExport:
    def test_export(self, tmp_path):
        """Test if the export functionality works without error"""
        from pathlib import Path

        import yaml
        from theflow.storage import storage

        config_path = tmp_path / "config.yaml"
        pipeline = Pipeline()
        Path(storage.url(pipeline.config.store_result)).mkdir(
            parents=True, exist_ok=True
        )

        config_dict = export_pipeline_to_config(pipeline)
        pipeline_name = list(config_dict.keys())[0]

        config_dict[pipeline_name]["logs"] = {
            "sheet1": {
                "inputs": [{"name": "text", "step": ".", "variable": "text"}],
                "outputs": [{"name": "answer", "step": "."}],
            },
        }
        with open(config_path, "w") as f:
            yaml.safe_dump(config_dict, f)

        export_from_dict(
            config=str(config_path),
            pipeline=pipeline_name,
            output_path=str(tmp_path / "exported.xlsx"),
        )
