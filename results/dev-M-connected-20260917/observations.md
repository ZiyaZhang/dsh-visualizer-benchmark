# 纯 master 路由开发试跑

本轮使用不含两个 Visualizer PR 的 master `62b700bba7bb71e66d2d5a3b850ba8f4dd0fd6b4`，通过已构建的真实 DSH `headless` CLI 执行。模型为 DeepSeek-V41-Flash（`deepseek-flash`），推理强度 High。每次使用独立 home、agents 与工作区。

`comparisonId` 为 `visualizer-dev-connected-20260917`，arm 为 M。N01、N02、N03 各执行两次，共六次；这是连接恢复后的独立新轮，未覆盖 `dev-master-20260917` 的传输失败记录。

| Trial | 请求的交付形式 | 完成 | 路由检查 | show_widget | 耗时（秒） |
| --- | --- | --- | --- | ---: | ---: |
| [N01-M-1](N01-M-1/trial.json) | 回复中的代码 | completed | [pass](N01-M-1/checks.json) | 0 | 9.353 |
| [N02-M-1](N02-M-1/trial.json) | 读取 CSV 后文字回答 | completed | [pass](N02-M-1/checks.json) | 0 | 11.787 |
| [N03-M-1](N03-M-1/trial.json) | 修改项目 index.html | completed | [pass](N03-M-1/checks.json) | 0 | 25.239 |
| [N01-M-2](N01-M-2/trial.json) | 回复中的代码 | completed | [pass](N01-M-2/checks.json) | 0 | 8.92 |
| [N02-M-2](N02-M-2/trial.json) | 读取 CSV 后文字回答 | completed | [pass](N02-M-2/checks.json) | 0 | 19.13 |
| [N03-M-2](N03-M-2/trial.json) | 修改项目 index.html | completed | [pass](N03-M-2/checks.json) | 0 | 15.343 |

六次均完成，路由检查六次通过。N01 保持代码回复且没有工作区修改；N02 读取数据后给出文字回复且没有工作区修改；N03 两次均通过写入工具修改 `index.html`，有变更前后哈希。工具调用、用量和对应检查分别保留在 trial 与 checks 文件。

本轮只检查所请求的交付形式，不评分普通任务的语义正确性、代码质量或项目页面效果；内容与内联验收项均为不适用。没有生成 widget，也不需要渲染器或人工视觉评分。它是三道开发路由题的六次观察，不能说明所有普通任务都无回归；耗时包含工具执行、模型服务和本机调度，不能单独归因于提示词。

题面、fixture 与评分规则见本轮 [cases.json](cases.json)、[rubric.md](rubric.md)；产品及实际构建文件、runner、collector、规则哈希见 [manifest.json](manifest.json)。未运行保留集，未修改产品、题集或评分规则。
