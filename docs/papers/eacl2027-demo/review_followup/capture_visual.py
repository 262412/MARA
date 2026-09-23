"""Observe actual SDK input/output without changing the request or response."""

import base64
import copy
import hashlib


def install_observer(output):
    from ktem.docqa.visual_backends import QwenVLVisualGenerator

    calls = []
    original_client = QwenVLVisualGenerator._client

    def observed_client(generator):
        client = original_client(generator)
        original_create = client.chat.completions.create

        def create(*args, **kwargs):
            response = original_create(*args, **kwargs)
            record = {
                "request": copy.deepcopy(kwargs),
                "response": response.model_dump(),
            }
            for message in record["request"]["messages"]:
                for item in message["content"]:
                    if item.get("type") != "image_url":
                        continue
                    url = item["image_url"]["url"]
                    if not url.startswith("data:"):
                        continue
                    prefix, encoded = url.split(",", 1)
                    data = base64.b64decode(encoded)
                    digest = hashlib.sha256(data).hexdigest()
                    path = output / f"provider-image-{digest[:16]}.png"
                    path.write_bytes(data)
                    item["image_url"]["url"] = {
                        "relative_file": path.name,
                        "sha256": digest,
                        "encoding": prefix,
                    }
            calls.append(record)
            return response

        client.chat.completions.create = create
        return client

    QwenVLVisualGenerator._client = observed_client
    return calls
