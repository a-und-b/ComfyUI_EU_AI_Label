import { app } from "../../scripts/app.js";

// Show only the widgets that matter for the selected Label Type.
// widget.hidden drives the legacy renderer, widget.options.hidden Nodes 2.0.
const VISIBLE_WHEN = {
  eu_icon_variant: (t) => t === "EU Icon" || t === "Text + EU Icon",
  color_variant: (t) => t !== "Custom Logo",
  custom_text: (t) => t === "Text" || t === "Text + EU Icon",
};

function applyVisibility(node) {
  const typeWidget = node.widgets?.find((w) => w.name === "label_type");
  if (!typeWidget) return;
  let changed = false;
  for (const [name, isVisible] of Object.entries(VISIBLE_WHEN)) {
    const w = node.widgets.find((x) => x.name === name);
    if (!w) continue;
    const hide = !isVisible(typeWidget.value);
    if (w.hidden === hide) continue;
    w.hidden = hide;
    w.options ??= {};
    w.options.hidden = hide;
    changed = true;
  }
  if (!changed) return;
  // height follows the visible widgets; the width stays as the user (or a workflow) set it
  node.setSize([node.size[0], node.computeSize()[1]]);
  node.setDirtyCanvas?.(true, true);
}

app.registerExtension({
  name: "a-und-b.EUAILabel.conditionalWidgets",
  nodeCreated(node) {
    if (node.comfyClass !== "EUAILabelVisible") return;
    const typeWidget = node.widgets?.find((w) => w.name === "label_type");
    if (!typeWidget) return;

    const callback = typeWidget.callback;
    typeWidget.callback = function (...args) {
      const r = callback?.apply(this, args);
      applyVisibility(node);
      return r;
    };

    // re-apply after a workflow is loaded (values are set without callbacks)
    const onConfigure = node.onConfigure;
    node.onConfigure = function (...args) {
      const r = onConfigure?.apply(this, args);
      applyVisibility(node);
      if (args[0]?.size) node.setSize(args[0].size); // a saved workflow keeps its layout
      return r;
    };

    applyVisibility(node);
  },
});
