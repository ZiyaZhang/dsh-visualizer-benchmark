# DSH 可交互内联可视化 benchmark

独立仓库：[ZiyaZhang/dsh-visualizer-benchmark](https://github.com/ZiyaZhang/dsh-visualizer-benchmark)。产品 PR 只需在 README 链接此评测，不包含评测代码、题集或实验产物。

这套评测用于迭代 `show_widget` 的工具指导和 Visualize Skill。**只评价内联组件的质量；文件、项目修改、Cordis 扩展等任务只检查是否走了正确流程。** 固定 DeepSeek-V41-Flash（`deepseek-flash`）/ High。

## 先看效果，再给评分

启动 `python3 serve.py --port 3092` 后打开：

- [结果入口](http://127.0.0.1:3092/)
- [本轮 A/B：28 份内联成品](http://127.0.0.1:3092/label.html?stage=compare-visualizer-dev-connected-20260917)：7 题 × 2 次 × A/B，同题混排。
- [6 份历史校准样本](http://127.0.0.1:3092/label.html?stage=calibration)：二分查找、热传导、地区追问，每题两次；已保存的评分继续保留。
- [Codex / Cowork 参照](http://127.0.0.1:3092/reference.html)：仅供产品效果参考，不加入 DSH 指标，不要求你打分。

校准样本是历史版本的真实首次输出，**不是新旧提示词对照**。历史的 73 次运行、原始源码、失败与截图均保留。已知二分查找正文有最坏比较次数错误，部分终态说明也未同步；不能因按钮可点而说整体质量通过。

## 当前实测状态（2026-09-17）

**公司接口已恢复，46 次真实 DSH 生成已全部完成，实际配置均为 V41 Flash / High。** A 为当前两个 PR 加 master，B 只增加 Skill 主文的一段核对要求，M 为同一 master、不含两个 PR。

| 组别 | 已完成 / 计划 | 内联成品供人工评价 | 其它任务路由 |
| --- | ---: | ---: | ---: |
| A 当前指导 | 20 / 20 | 14 份 | 6 / 6 通过 |
| B 候选指导 | 20 / 20 | 14 份 | 6 / 6 通过 |
| M 纯 master | 6 / 6 | 不评价 | 6 / 6 通过 |

- 28 份内联输出的首次渲染：A 14 份通过；B 13 份通过、1 份失败。B 的失败样本自行猜测更新标识，被 Host 拒绝后又提交一张新卡；首次失败、拒绝、后续卡片全部保留。
- 二分题的“8 个元素最多比较 3 次”错误在 A 两次出现；B 一次避开精确错误断言，一次明确给出正确的最坏 4 次。此单项不能代表全文正确或整体质量胜出。
- 三道开发路由题在 M/A/B 各重复两次，共 18 次正确交付且未调用 `show_widget`。这只覆盖代码回复、文字汇总和项目修改，不代表尚未运行的文件/Cordis 题已通过。
- [结果与选择记录](results/visualizer-dev-connected-20260917.md)逐项说明结果、检查器校准及限制；[候选原文与动机](candidates/B-state-consistency.md)保留确切改动。**暂不采用 B，继续保留 A 产品基线**，等待人工四维判断后决定下一轮改法；保留测试集仍未运行。

最新 master `62b700bba7` 与 Host `a754eacf66` / Web `5aefdb9332` 在独立 checkout 整合为实验提交 `b56f63c297`；B 为 `9ca98673c5`。两份产品 PR 未修改、未合并。本地构建/检查不代表完整远端 CI。

连接恢复前的 [A pilot](results/dev-current-20260917/manifest.json) 和 [M pilot](results/dev-master-20260917/manifest.json) 各有一次连接错误，另有 9 / 2 次未开始；当时 TCP 成功而 TLS 握手超时。旧轮冻结记录保留，不把旧环境失败算作本轮模型错误。新三组共用 `visualizer-dev-connected-20260917`，没有覆盖失败重试。

采集复核发现旧脚本将非显示日志块混入回复，已从原始 Session 重新导出严格 `type: text` 正文；46 份均有修正元数据，原导出私有备份，模型输出与组件源码不变。没有重新请求模型，没有改写冻结 manifest。新评分使用校正后的可见完整回复。

## 你需要做什么

1. 打开本轮 A/B 页，逐份看 28 份完整回答。页面包含题目、预期结果、全部组件、正文和已有证据；可分批完成。
2. 实际操作控件，查看窄屏/深色，分别给理解价值、信息与布局、操作可理解性、简洁与聚焦打 **0 / 1 / 2**。
3. 无法观察的维度选 N/A 并说明原因；尚不能判断的整份结果保存“待核”，不要用 0 代替未评。
4. 保存。标注在本机私有目录，可继续修改或导出；旧版成对偏好仍保留，不转换成新评分。

你不需要运行模型、整理截图、检查 Git 提交或填写 Codex/Cowork 分数。先完成这轮四维与内容判断；维护者再结合失败决定保留当前版或提出下一候选，选定后运行未用于调优的保留集。规则或题目若改动，另起轮次，不追改本轮判据。

详见 [rubric.md](rubric.md)。人工分与路由、事实、功能门槛分开，不相加成总分，不相互抵销。

## 题集

[cases.json](cases.json) 有 20 题：开发集 10、保留测试集 10。每题保存自然语言请求、固定数据/文件、允许路由、预期结果和浏览器检查场景。

| 类别 | 开发集 | 保留测试集 |
| --- | --- | --- |
| 算法与数值交互 | W01 二分查找；W02 热传导 | W07 指数退避；W08 缓存成本 |
| 静态图 | W03 缺失/零/负数；W04 长中文标签 | W09 读取CSV画趋势；W10 职责与修复分支 |
| 控件与追问 | W05 数量选择器；W06 地区追问 | W11 筛选原型；W12 异常日期追问 |
| 允许主动可视化 | E01 TCP三次握手 | E02 REST/GraphQL取舍 |
| 其它任务的路由 | N01 代码；N02 文字汇总；N03 项目修改 | N04 SVG文件；N05 HTML文件；N06 Cordis扩展 |

主动可视化题允许文字与内联两种形式；出图率只描述行为，不奖励多画。静态图允许 SVG 或 HTML；需要脚本交互时应使用 HTML，其中可以包含 SVG。

N06 必须在真实 Cordis 预设下运行。headless 不加载该预设，运行器会记 `blocked`，不会用缺少工具的环境给模型判失败。文件存在或没有 `show_widget` 也不能单独证明正确路由，应结合任务要求与实际工具/交付记录。

原位修复、一次自动预算、准确版本、日志恢复继续由 Host/Web 功能验证单列。独立预览抓到消息不代表原对话已收到；普通用户修改图的产品语义也不预设成新的强制更新契约。

## 一次实验如何运行

`Task` 是题目；`Trial` 是某题在某版本的一次尝试。运行器准备隔离环境、启动真实 DSH，采集器读取完整 Session 日志，检查器核对产物与交互，人工页面评价呈现质量，汇总器检查记录后给出逐项结果。

比较分两种：

- **路由保护**：相同 master，不含两个 PR 的 M 与包含两个 PR 的 A 比较其它任务的路由。
- **提示词效果**：相同产品、模型、加载方式和题目，当前 A 与只改变已声明工具指导/Skill 的 B 比较内联效果。

每个 round 固定一个 arm，多 round 用同一个 `comparisonId` 关联。正式候选每题至少重复两次，保留所有首次尝试。先用开发集校准；候选与规则冻结后才运行保留集。看过测试结果再针对它改指导，应作为下一轮开发，不继续声称该题是未见测试。

### 看什么指标，怎样据此迭代

| 问题 | 报告方式 | 如何使用 |
| --- | --- | --- |
| 是否走错流程 | 非内联题逐题列 master / PR 路由结论、`show_widget` 调用和真实交付证据 | 新增误触发要定位到工具描述或 Skill 触发条件；不能以零组件调用代替正确交付 |
| 首次能否完成 | 各检查的 pass / fail / pending / error / N/A 计数，同时显示计划数和实际尝试数 | 首次拒绝、渲染失败和后续修复分开；环境错误不能从分母中消失 |
| 图是否更好用 | 四维分布及同题逐次结果，附具体问题；事实/完成判断独立展示 | 不合成总分；关注改善是否在重复尝试中出现，是否伴随别的退步 |
| 修改是否有额外成本 | 实际工具调用、加载过的 references、usage、耗时 | 只在配置与加载方式一致时比较；缓存、环境重试等限制写清楚 |

先根据开发集错误选择一个最小修改：路由问题改工具描述或 Skill 描述，重复的布局问题改对应 reference，状态与正文矛盾则补充交付前核对要求。每个候选记录具体改动和预期解决的失败，不同时换模型、产品与题目来宣布提示词有效。

选择记录应逐项回答：改善了什么，哪些地方持平或退步，是否出现新的误路由，哪些问题尚未验证。优先排除新增硬性失败；质量各维有取舍时保留取舍，由人工决定，不用一个总分掩盖。若样本不足或结果不稳定，结论就是“证据不足”。候选选定后才运行未用于调优的保留集。

### 准备

需要 Python 3.9+、符合产品要求的 Node（22.19+ 或 24+）、已构建且 Git 干净的 DSH checkout。浏览器检查使用 checkout 已安装的 Playwright 及浏览器。不同版本应各用独立 checkout；不要修改只读镜像。

凭据由 `DEEPSEEK_API_KEY` / `DEEPSEEK_BASE_URL` 环境变量，或显式的 `--env-file` 提供。运行器不读取 shell 配置，不打印密钥。私有 env 文件不放在此目录，不提交。

```sh
export DSH_EVAL_REPO=/absolute/path/to/built-dsh-checkout
export DSH_EVAL_NODE=/absolute/path/to/supported/node

# 只冻结输入并检查构建，不请求模型
python3 run-dsh.py --plan --round dev-A-v2 --comparison-id dev-v2 \
  --repo "$DSH_EVAL_REPO" --arm A --split dev --repeats 1

# 同一组计划执行尚未开始的尝试
python3 run-dsh.py --resume --round dev-A-v2 --comparison-id dev-v2 \
  --repo "$DSH_EVAL_REPO" --arm A --split dev --repeats 1 \
  --env-file /absolute/private/path/credentials.env
```

一次试跑用于验证工具链，不等于正式 A/B。`--case W01 W02` 可缩小范围。执行前冻结题集、rubric、源码与实际构建文件/Skill 哈希；运行中若产品文件变化会停止，避免一轮混入两版。旧轮的 runner、collector 或冻结规则不匹配时拒绝重新采集/续跑，须保留旧轮并新建实验。每次尝试独立 home、agents 和工作区，模型输入只提供任务与所需 fixture，评分真值和其它尝试不作为输入。这是运行目录隔离，不是额外的操作系统沙箱；判分前仍应核查完整 trace 是否有越界读取。

失败、超时、缺日志与未开始各自保留。`--resume` 不覆盖已完成或失败的尝试；重试须新 round，并解释原因。原始事件与完整 Session 私有保存，公开结果仅提取必要工具记录、源码、正文和统计。

### 检查与汇总

```sh
python3 check-dsh.py --trial results/dev-A-v2/W01-A-1/trial.json \
  --output results/dev-A-v2/W01-A-1/checks.json

"$DSH_EVAL_NODE" render-check.mjs \
  --trial results/dev-A-v2/W01-A-1/trial.json \
  --output results/dev-A-v2/W01-A-1 --repo "$DSH_EVAL_REPO"

python3 serve.py --port 3092
python3 summarize.py --stage dev-A-v2 --output results/dev-A-v2
```

采集器在 runner 每次结束后执行；手动重收集使用 `node collect-dsh.mjs --round ROUND_ID`，自定义私有目录时追加 `--private-root DIR`。它读取完整 Session，而非可能截断长字符串的 CLI 输出。正文按顺序合并本次运行全部 assistant message 的可见 text 块，包含组件前后的可见说明。首次源码保持原样，所有接受与拒绝的调用保留，不静默选最好的一张图。若需修正本轮旧版正文导出，可显式加 `--correct-final-exports`：须整轮结束、原摘要和 Session 身份匹配，并在私有目录备份；只更正导出，不改生成输入或 frozen collector 哈希。

浏览器检查打开真实 Web `srcdoc` 生成的预览，用隔离 iframe 操作。初始渲染、状态转换、消息与布局提醒分别记录；定位失败会保留待核或检查器错误。截图覆盖宽/窄和浅/深，关键动作后另保留状态证据。若某个场景尚无可用自动断言，它显示待人工核对，不能自动通过。

四维标注绑定题面、全部组件、完整正文、渲染产物和评分页/规则版本。正文使用本地 Marked 16.4.2 展示 Markdown，保留原文可查；原始 HTML 转义、外部图片不加载。汇总是生成时的快照，实时进度以打标页为准。汇总会拒绝无效评分，标出内容变化后的旧评分；未评、错误和不适用不算通过。结果按题和检查项报告计数，不用小样本制造统计显著性，也不自动选赢家。

## 文件与证据

| 文件 | 职责 |
| --- | --- |
| `cases.json` / `rubric.md` | 题集、允许路由、预期结果；人工锚点 |
| `run-dsh.py` | 冻结输入、构建检查、隔离运行、首次尝试保护 |
| `collect-dsh.mjs` | 完整日志采集、全部组件与正文、真实预览 |
| `check-dsh.py` / `render-check.mjs` | 路由/有限事实检查；浏览器操作与截图 |
| `serve.py` / `label.html` / `dsh-view.html` | 标注保存、逐份评价、独立操作 |
| `summarize.py` / `index.html` | 按证据汇总；当前结果入口 |
| `results/<round>/` | 冻结manifest、题目快照、逐trial结果与检查 |
| `history/cases-v1.json` / `dsh-results.json` | 历史题目和73次原始记录，不覆盖 |
| `dsh/` / `screenshots/` | 历史源码、原始预览、截图与文字观察 |
| `results.json` / `reference.html` | 历史Codex/Cowork参照，含当时的限制 |

原始 Session、凭据、私有标注和备份在目录外。历史目录里的独立源码与完整回复是有意保留的评测产物，不能与完整私有 Session 混为一谈。默认标注位置用于当前本机，也可用 `serve.py --state /private/path/annotations-v2.json` 更改；汇总时传同一个 `--annotations`。不要把私有运行目录整体复制进 benchmark。

## 设计来源与产品边界

基于用户提供的评测方案落实，直接复用已有 DSH 采集/预览能力，并参考 [file-references benchmark](https://github.com/Dudu-0223/dsh-benchmarks/tree/main/file-references) 的输入冻结、产物哈希和选择记录。人工维度依据本机 Codex Visualize Skill 1.0.32 的实际规则细化；Claude skill-creator 的 grader/analyzer 用于检查证据与分析失败，首版不引入未经校准的模型裁判。

[Anthropic agent evals](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)、[Claude plugin evals](https://code.claude.com/docs/en/plugin-evals)、[OpenAI eval best practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices)、[ArtifactsBench](https://arxiv.org/abs/2507.04952) 提供方法参考，不能代替本套检查器与人工标注的校准。

产品实现仍在 [Host #3820](https://github.com/deepseek-harness/deepseek-harness/pull/3820) 与 [Web #3340](https://github.com/deepseek-harness/deepseek-harness/pull/3340)。实验不向生产包增加测试接口；最终产品 README 只需说明行为并链接独立评测，候选、失败和选择过程留在这里。
