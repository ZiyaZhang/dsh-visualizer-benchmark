# 候选 C

基线 `b56f63c297`；候选 `db0399958b07ce2a85088ddc8fcb3c5b49a2cb10`；V41 Flash / High；开发集10题各2次。

同时核对数值状态、统一图轴与标记、提高窄屏和深色可读性。开发集仍有二分最坏次数错误、销售数值条缺失及 TCP 窄屏裁切；不采用这组 Skill/reference 改动。

```diff
diff --git a/packages/visualizer/tool-visualizer/assets/references/charts.md b/packages/visualizer/tool-visualizer/assets/references/charts.md
index 58bcf3a2d0..d50f436a18 100644
--- a/packages/visualizer/tool-visualizer/assets/references/charts.md
+++ b/packages/visualizer/tool-visualizer/assets/references/charts.md
@@ -1,3 +1,3 @@
 # Charts
 
-choose bars for comparisons, lines for ordered change, dots for distributions, and tables for exact lookup. Include units, readable ticks, meaningful precision, and room for labels. Distinguish missing values from zero. Start magnitude comparisons at zero; otherwise make the scale and domain clear. Labelled log scales or small multiples can expose wide ranges. Prefer direct series labels, or one compact legend when labels collide.
+Choose bars for comparisons, lines for ordered change, dots for distributions, and tables for exact lookup. Include units, readable ticks, meaningful precision, and room for labels. Distinguish missing values from zero. Use one value-to-position mapping for marks, ticks, and the zero baseline, including both sides of a signed axis. Start magnitude comparisons at zero; otherwise make the scale and domain clear. Labelled log scales or small multiples can expose wide ranges. Prefer direct series labels, or one compact legend when labels collide.
diff --git a/packages/visualizer/tool-visualizer/assets/references/interaction.md b/packages/visualizer/tool-visualizer/assets/references/interaction.md
index dc3d7082bf..9f1a945e34 100644
--- a/packages/visualizer/tool-visualizer/assets/references/interaction.md
+++ b/packages/visualizer/tool-visualizer/assets/references/interaction.md
@@ -4,6 +4,7 @@
 - Keep input changes, selection, and self-contained computation local. Show current values with their units; use tabular numerals and reserve enough space to prevent layout shifts.
 - Select elements by IDs present in the fragment. A trailing script is a sibling of the visual; use document.getElementById or document.querySelector to locate it.
 - Initialize every value used by the first render. Display a missing previous value as a dash before applying numeric formatting.
+- Derive pointer positions, highlights, readouts, and enabled controls from the same current state. Label previous-state comparisons explicitly and clear obsolete indicators when the operation finishes.
 - Use motion when change over time contributes to meaning. It may start immediately when central to the result; otherwise start stable and let a user action begin continuous motion. Honor reduced-motion preferences. Reuse a bounded set of elements and stop scheduling when idle, paused, or settled.
 - Call window.dshWidget.sendPrompt(text) only when the next step needs the model. Include the selected values and requested explanation or investigation in the text. A clear user action or the widget's own logic may trigger it; the message enters the conversation immediately without confirmation. Local changes stay local.
 - Recover from non-fatal errors. Keep behavior deterministic, with reproducible and resettable variation when variation matters.
diff --git a/packages/visualizer/tool-visualizer/assets/references/style.md b/packages/visualizer/tool-visualizer/assets/references/style.md
index f160a19829..2be47707ed 100644
--- a/packages/visualizer/tool-visualizer/assets/references/style.md
+++ b/packages/visualizer/tool-visualizer/assets/references/style.md
@@ -2,5 +2,7 @@
 
 - Keep related inputs and primary results together. Reserve separate panels for distinct tasks; avoid an extra outer frame or a panel for every value.
 - Reflow controls, legends, comparisons, and value rows at narrow widths. Let flex and grid children shrink with min-width: 0; wrap labels or split overview and detail instead of clipping or shrinking text.
+- Keep labels readable at a 360px viewport: scaling an entire SVG also shrinks its text. Reflow the plot or place labels in wrapping HTML when needed, and reserve space for values beside the longest mark.
+- Pair foreground and background colors for each normal, highlighted, and hover state so both light and dark themes remain readable. Prefer the supplied theme styles for native controls.
 - Give each primary visual an accessible name and summary. Pair color with labels, shapes, or patterns. Use native controls with visible labels and one primary control per value: fields for exact entry, choices for discrete values, ranges for values meant to be swept.
 - Theme variables: --dsw-alias-bg-base, --dsw-alias-bg-layer-1, --dsw-alias-bg-layer-2, --dsw-alias-border-l1, --dsw-alias-border-l2, --dsw-alias-brand-primary, --dsw-alias-button-primary-fill, --dsw-alias-interactive-bg-hover, --dsw-alias-interactive-bg-active, --dsw-alias-label-primary, --dsw-alias-label-primary-inverted, --dsw-alias-label-secondary, --dsw-alias-label-tertiary, --dsw-alias-state-error-primary. Native controls already receive theme, focus, and disabled styles.
diff --git a/packages/visualizer/tool-visualizer/assets/visualize.md b/packages/visualizer/tool-visualizer/assets/visualize.md
index 86f02c9f6e..8bed5a79f0 100644
--- a/packages/visualizer/tool-visualizer/assets/visualize.md
+++ b/packages/visualizer/tool-visualizer/assets/visualize.md
@@ -1,6 +1,8 @@
 # Visualize
 
-Build one compact visual around the relationship or interaction that answers the request. For a broad request, choose one representative scenario. Keep labels in the user's language and supporting explanation in the reply. Use only the controls and readouts needed for the requested interaction. Use the available output tool's source format.
+Build one compact visual around the relationship or interaction that answers the request. For a broad request, choose one representative scenario. Keep labels in the user's language. Use only the controls and readouts needed for the requested interaction. Use the available output tool's source format.
+
+Compute each displayed quantity once and derive its marks, labels, and state indicators from that value. Trace the initial state, a transition, and the requested boundary or reset before submitting. In the reply, add only a useful interpretation or limitation; let the visual carry its data and controls. Keep numerical claims grounded in the same calculation and omit unverified extrapolations.
 
 Read only the references relevant to the task, using their paths relative to this skill's base directory:
 
```

结果见 [视觉复核与选择](../results/visual-review.md)。
