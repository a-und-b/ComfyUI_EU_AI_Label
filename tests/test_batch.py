"""Node-level batch handling: every image in an IMAGE batch gets the label."""

import json
import os

import numpy as np
import torch

from ComfyUI_EU_AI_Label import nodes
from ComfyUI_EU_AI_Label.nodes import EUAILabelVisible


def test_visible_node_labels_every_batch_image():
    batch = torch.zeros((3, 256, 256, 3))  # 3 black images
    node = EUAILabelVisible()
    (out,) = node.apply(batch, label_type="EU Icon", eu_icon_variant="AI",
                        color_variant="white", custom_text="", size=10.0,
                        margin=0.0, opacity=100.0, position="bottom right")
    assert out.shape == batch.shape
    for i in range(out.shape[0]):
        arr = out[i].numpy()
        assert arr.max() > 0.5, f"batch image {i} got no label"
        # label sits bottom-right, top-left corner stays black
        assert arr[:32, :32].max() == 0.0


def test_visible_node_batch_images_identical():
    batch = torch.rand((2, 128, 128, 3))
    batch[1] = batch[0]  # identical inputs -> identical labeled outputs
    node = EUAILabelVisible()
    (out,) = node.apply(batch, label_type="Text", eu_icon_variant="AI",
                        color_variant="black", custom_text="AI generated",
                        size=20.0, margin=3.0, opacity=100.0, position="top left")
    assert np.array_equal(out[0].numpy(), out[1].numpy())


def test_check_report_hides_local_folders():
    # a file in ComfyUI's output folder shows as a relative path in the report
    import folder_paths
    from PIL import Image
    out = folder_paths.get_output_directory()
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, "report_path.png")
    Image.new("RGB", (8, 8)).save(path)
    res = nodes.EUAILabelMetadataCheck().check(path)
    report, data = res["result"][0], json.loads(res["result"][1])
    assert "File:   report_path.png" in report
    assert out not in report
    assert data["file"] == path  # the JSON keeps the full path
