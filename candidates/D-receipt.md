# 候选 D

基线 `b56f63c297`；候选 `1342c1de1cfbe95bd3e73c708d2615cf5675803a`；V41 Flash / High；开发集10题各2次。

只改工具成功返回后的文本，不改工具描述、Schema、Skill 或运行时行为。Host 只能确认源码接受，不能断言 Client 已渲染完成；同时限定后续回复为主要结论或限制。开发集完整可见回复字符数中位数 A=367.5，D=151，均14份。D仍有首次渲染和内容错误，不是整体质量胜出。此文本在首次源码已提交后才返回，不能把该次源码质量变化归因于它。

```diff
diff --git a/packages/visualizer/tool-visualizer/src/model.ts b/packages/visualizer/tool-visualizer/src/model.ts
index 9606cb123d..72a60028f5 100644
--- a/packages/visualizer/tool-visualizer/src/model.ts
+++ b/packages/visualizer/tool-visualizer/src/model.ts
@@ -69,7 +69,7 @@ export function apply(ctx: Context): void {
         },
         render: (args, value) => [{
           type: 'text',
-          text: `Widget "${args.title}" accepted (${value.kind}). The visual is complete; finish with brief supporting prose.`,
+          text: `Widget "${args.title}" source accepted (${value.kind}); the Client renders it. Finish in one or two sentences with the main takeaway or a relevant limitation. Let the widget carry its data and controls; omit repeated values, step-by-step walkthroughs, and implementation details.`,
         }],
         presentationMeta: (_args, value) => ({ ...value }),
       },
```

结果见 [视觉复核与选择](../results/visual-review.md)。
