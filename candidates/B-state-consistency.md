# B：组件状态与正文断言一致性

本候选只增加 Visualize Skill 主文的一段检查要求。A 基线为集成提交 `b56f63c297`；B 为本地实验提交 `9ca98673c522c0f74b11bbc640dbf92121442bb9`。两个原 PR 不因本实验改动或合并。

## 确切改动

文件：`packages/visualizer/tool-visualizer/assets/visualize.md`。在第一段后、references 入口前增加：

```diff
+Before submitting, trace the requested initial state, main transitions, completion, and reset where applicable. Keep the visual, readouts, control states, and supporting reply consistent with each step. Verify quantitative and boundary claims separately; omit unnecessary claims you have not checked.
+
```

其余主文、Skill 描述、路由提示、工具 schema/结果、references、Host 和 Web 实现均不变。references 仍按需加载；没有题目名称、数据、具体计算结果或判分真值。

## 动机与可检验假设

历史校准输出中，控件能够工作，但完整回复含未经核对的定量断言，个别组件在结束后仍保留上一状态的说明。假设这段要求能减少状态转换、读数、控件和正文之间的矛盾，并减少不必要的未核实断言。它是待评测的假设，不是已经证实的改进。

## 与历史候选的关系

已核对历史 baseline、candidate、revision、focused 的实际 Skill 文件及 `dsh-results.json` 的提示词迭代记录。旧 candidate 在 interaction reference 中要求同一状态驱动视觉/数值/控件；旧 revision 增加初态、一次更新和完成前检查。它们没有充分解决生成问题；focused 后来保留了元素选择和首帧初始化的具体规则。因此“交付前检查状态”并非全新思路。

本轮保留 focused 的全部现有规则，将通用检查放到必读主文，并把支持正文与定量/边界断言纳入检查；这是与旧 reference 改法的区别。另两个历史 refined/concise 候选只改变工具接受后的简短收尾要求，未被采纳；本轮不复用该改法。

## 运行与限制

运行标识为 `dev-B-connected-20260917`，与 A/M 共用 `comparisonId: visualizer-dev-connected-20260917`。使用 DeepSeek-V41-Flash / High，开发集 10 题各 2 次，保留所有首次尝试；模型运行错误自动停止。产品提交、实际 runtime/Skill 哈希、题面、规则与完整尝试状态以 [manifest](../results/dev-B-connected-20260917/manifest.json) 为准。

运行前的 A/B manifest 核对确认：模型、推理配置、题集、rubric、runner、collector、渲染器和超时设置一致；所冻结 runtime 文件仅 `assets/visualize.md` 的哈希不同。B 离线依赖安装、Host 构建和编译入口导入检查通过。这些准备检查不构成模型质量结论。

本轮 B 的 20 次生成均正常结束，runner 返回 0；这只表示生成阶段完成，不表示事实、交互或人工质量评分通过。首份真实请求为 `deepseek-flash / high`，完整 Skill 工具结果包含候选主文，主文 SHA256 为 `6107d459915bf0da240327a1e673a9b6a5cf166ba1f7474122525cc9201a26b3`。正文展示需按原始 Session 的可见 text 块提取，不能把 reasoning 文本计入用户可见答案。

## 输入路径审计

对本 comparison 的 A/B/M 共 46 份完整 Session、172 次工具调用进行只读审计，未观察到读取 benchmark 题集、rubric、oracle、历史结果、其他 trial 或凭据。74 次显式 read 全部针对当前任务的 `index.html` / `sales.csv` 或 Skill 的四份 references；6 次 glob 均在当前工作区；其余行为包括本地计算、生成代码和请求 Skill。

两处须单列的隔离限制：`W03-B-1` 为查主题变量，用 grep 遍历候选 checkout 的 Visualizer `.md` / `.html`，结果仅列出 `references/style.md`；`E01-B-1` 把自己的新生成脚本写到共享 `/tmp` 文件后做语法检查。因此这里是“未观察到评测输入泄漏”，不是额外操作系统沙箱或严格文件访问白名单的证明。审计不把合法的本地自测判为路由失败；N01 按本轮冻结题面没有禁止执行自测。

这是一个小样本开发实验；没有改动未见测试集，也没有向模型提供 oracle。主文变长会增加加载后的上下文，模型可能只口头遵循检查；需要检查真实生成、关键交互与正文，并由人工分别评价四维质量。一个候选同时包含状态轨迹和断言检查，不能从本轮结果分离两句话各自的因果贡献。路由退化、事实/功能失败、人工呈现评分分别报告，不相互抵销。
