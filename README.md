---
description: "DSH 内联可视化的固定题集、运行器、检查器与人工 rubric。"
kind: "package-reference"
---

# DSH 内联可视化评测

这套 benchmark 用于回答两个问题：**内联组件是否完成任务、是否更好理解和使用；新增能力是否把其它任务误导到内联组件。** 固定 DeepSeek-V41-Flash（`deepseek-flash`）/ High。其它任务只评路由，不评代码、文件或 Cordis 扩展的产物质量。

## 当前可以得出什么

当前提交提供可复跑的方法和题集，**不发布尚未经人工审核的 A/B 结果、视觉分数或候选胜出结论**。此前的生成产物、模型评分、截图、候选与报告已从当前文件树移除，完整实验保留在仓库外的本地归档；没有抹掉原始失败。Git 历史仍保留旧提交。

[保留的人工记录](results/reviewed-example/observation.json)只有一份历史校准样本，题面、源码、正文与人工标注的绑定哈希保持一致。原标注的 `correctness=pass` 与正文“8 个元素最多比较 3 次”存在冲突：标准二分查找最坏需要 4 次。保留原标注，不代替用户改分；这份样本不是通过验收或 A/B 有效的证明。

## 评测如何帮助改产品

| 发现 | 应采取的动作 | 证据要求 |
| --- | --- | --- |
| 文件或项目任务调用了 `show_widget` | 收紧工具描述或 Skill 路由条件 | 任务要求、实际工具调用、真实交付与 master 对照 |
| 首次无法渲染、控件计算或追问值错误 | 区分生成源码错误、指导缺口与运行时问题，再做小改动 | 原始源码、错误与实际交互状态；不能只看截图 |
| 图难理解、布局拥挤、正文重复 | 针对失败调整对应 Skill/reference 或工具回执 | 同题多次对照，经人工核对改善与新增退步 |

脚本提供可复核的检查与问题定位，人工决定内容是否正确、任务是否完成及四维质量。没有这些人工证据，就不把“能渲染”当作“效果好”，也不发布总体赢家。产品单测和浏览器回放另行验证运行时，不替代生成评测。

## 题集与规则

[cases.json](cases.json) 保存 20 道题的原始 query、固定 fixture、允许路由、真值与检查场景；[rubric.md](rubric.md) 定义判断方法。

| 题类 | 题目 |
| --- | --- |
| 12 道必须内联 | 二分查找、热传导、缺失/零/负数、长中文标签、数量选择器、地区追问、指数退避、缓存成本、CSV 趋势、职责与修复分支、筛选原型、异常日期追问 |
| 2 道允许主动可视化 | TCP 三次握手、REST/GraphQL 取舍；不奖励多出图 |
| 6 道路由保护 | 代码回答、文字汇总、项目修改、SVG 文件、HTML 文件、Cordis 扩展 |

静态图允许 SVG 或 HTML；脚本交互使用 HTML，其中可以包含 SVG。普通控件操作留在组件内，显式分析请求才发送追问。

保留原 dev/test 各 10 题的分组用于复跑；**这些题都已在此前开发中运行并被查看，不能再次宣称是新的未见测试集。** 新一轮若需要独立测试，应补充新题并在候选冻结后首次运行。

人工先判断内容正确性与完成情况，再分别评理解价值、信息与布局、操作可理解性、简洁与聚焦（0/1/2，必要时 N/A）。不合成总分，不用美观抵销错误。`pending`、环境错误和未评均不算通过。

N06 需要真实 Cordis 预设。普通 headless 没有该环境时记 `blocked`，不冒充通过。独立 iframe 捕获消息不能证明真实原对话收到追问；原位修复、版本核验与自动修复预算仍由产品功能验证覆盖。

## 运行一组评测

需要 Python 3.9+、符合产品要求的 Node（22.19+ 或 24+）、干净且已构建的 DSH checkout，以及 Web checkout 已安装的 Playwright 和浏览器。从本目录运行；若作为其它仓库的 `visualizer/` 子目录，先 `cd visualizer`。

```sh
export DSH_EVAL_REPO=/absolute/path/to/built-dsh-checkout
export DSH_EVAL_NODE=/absolute/path/to/supported/node

# 冻结产品、工具/Skill、题集与 rubric；不调用模型
python3 run.py --plan --round dev-A-01 --comparison-id dev-01 \
  --repo "$DSH_EVAL_REPO" --arm A --split dev --repeats 2

# 运行同一组计划；凭据文件须在仓库外
python3 run.py --resume --round dev-A-01 --comparison-id dev-01 \
  --repo "$DSH_EVAL_REPO" --arm A --split dev --repeats 2 \
  --env-file /absolute/private/path/credentials.env
```

`Task` 是题目；`Trial` 是题目 × 版本 × 重复序号。M 是相同 master 上不含 Visualizer 的路由对照；A 是加入两个 PR 的版本；候选只改变预先声明的工具指导或 Skill。每版使用独立 checkout，相同模型、配置和题目。`--case W01 W02` 可缩小范围。

运行器冻结实际源码与构建文件哈希，每次尝试建立独立 home、agents 和工作区，仅把题目和 fixture 给模型，不提供真值或评分规则。这不是操作系统级沙箱，应检查 trace 中的越界读取。首次输出、拒绝、超时和环境错误都保留；`--resume` 不替换已结束的尝试，重试另开 round 并说明原因。

提取后的生成文件写入被 Git 忽略的 `results/<round>/`。原始 Session、日志、凭据及标注不作为共享结果提交；运行器默认将私有数据存到本目录之外的 `../.artifacts/visualizer/runs/`，可用 `--private-root` 指定其它目录。旧实验如需读取，应在原归档中使用当时冻结的脚本，不用新版改写。

## 检查、人工评审与汇总

```sh
python3 check-dsh.py --trial results/dev-A-01/W01-A-1/trial.json \
  --output results/dev-A-01/W01-A-1/checks.json
"$DSH_EVAL_NODE" render-check.mjs \
  --trial results/dev-A-01/W01-A-1/trial.json \
  --output results/dev-A-01/W01-A-1 --repo "$DSH_EVAL_REPO"

python3 serve.py --port 3092
# 打开 http://127.0.0.1:3092/label.html，查看完整正文并实际操作后保存
python3 summarize.py --stage dev-A-01 --output results/dev-A-01
python3 -m unittest discover -s . -p 'test_*.py' -v
```

运行器调用 `collect-dsh.mjs` 读取完整 Session，只导出可见正文及必要工具记录。浏览器检查复用真实 Web `srcdoc`，采集 736px/360px、浅/深主题及关键状态；定位不确定时保留待核。环境问题不归责给模型。

人工标注默认保存在网页目录外的 `../.artifacts/visualizer/annotations-v2.json`，可用 `serve.py --state /private/path/annotations.json` 改位置；汇总器须传对应的 `--annotations`。标签绑定完整成品、正文、题面和评分页面/规则哈希，变化后需重新审核。汇总器验证数据，不替代人工判断，也不自动选赢家。

共享结果应另作审核：保留完整计划数、缺失项、失败和审核状态，再提交经过人工核对的观察台账、指标与选择理由。未审核的数据继续留在本地。不能挑一份好样例代表整轮成功。

## 文件与来源

| 文件 | 职责 |
| --- | --- |
| `cases.json` / `rubric.md` | 固定题集、fixture、真值、路由边界与人工锚点 |
| `run.py` / `collect-dsh.mjs` | 冻结输入、运行 DSH、采集轨迹与原始输出 |
| `check-dsh.py` / `render-check.mjs` | 路由、有限事实与浏览器交互检查 |
| `serve.py` / `label.html` / `vendor/` | 本地人工评审与绑定标签 |
| `summarize.py` / `test_eval.py` | 分项汇总与检查器校准 |

目录与实验记录方式参考 [file-references benchmark](https://github.com/Dudu-0223/dsh-benchmarks/tree/main/file-references)。`cases.json` 将题目和真值集中存放，避免为每道题增加多份小文件；模型只收到其中的 prompt 与 fixture。四维是本 benchmark 的规则，不是 Codex 官方评分表。

产品实现位于 [Host #3820](https://github.com/deepseek-harness/deepseek-harness/pull/3820) 与 [Web #3340](https://github.com/deepseek-harness/deepseek-harness/pull/3340)。评测单独维护，产品 README 只链接。
