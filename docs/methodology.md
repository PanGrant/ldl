# 布局 Schema 方法论 —— 定义与实现分离

> 状态：**第一个消费者迁移完成**（2026-11-25）。本仓 = 方法的载体：
> `ldl.schema` 是 L1，`ldl.census` 是 §4 的验证装置，L2 随第一个
> 消费者（朋友圈布局）生长。原始草稿与本仓演进的完整决策史见本机
> `local/design-docs/`（含真实案例名，不入公共仓）。

## 0. 一句话目标

把"读懂一张桌面 UI 并对它操作"变成可复用的三段方法：

1. **人假设**：观察桌面布局规律，人画出结构假设（容器、列、行，行高可变）；
2. **机器验证**：用真机帧语料逐条验证假设（普查：每条声明要有数字支撑，不成立就改假设）；
3. **按定义实现**：布局定义定稿后，感知（认知）和操作（动作）都只对着定义做——定义与实现物理分开。

朋友圈感知层是这个方法的第一个成品（摸出来的，不是照方法做的）。ldl 把它提炼成库，**下一个 UI 布局按方法走一遍**。

## 1. 为什么要做（教训出处）

| 教训 | 出处 | 方法论里的对应物 |
|---|---|---|
| 定义和实现混在一个文件里，改动漂移靠测试才能抓回 | 2026-11-23 一次作者行误判：ASCII 文档说"这格是名字"，代码里混进三道内容检查，判定出错 | 定义层 / 实现层物理分离 + 一致性普查 |
| 散逻辑=每处一套谓词/阈值，漂移不可查 | 2026-11-15 库纪律第一条 | 判据全部声明在定义里，函数只消费声明 |
| 窗口每次可能不同，答案永远是测量 | 2026-11-15 库纪律第三条（441pt→509pt 实证） | 值分两类：窗口几何（每运行实测）vs 语料阈值（语料量定的群体边界） |
| 位置决定身份，文字内容不参与行判定 | 2026-11-23 库纪律修正（名字区只认位置） | 识别契约里显式声明 content_blind + 例外（箭头探针） |
| 感知失败必须诚实为 None，绝不瞎判 | 落屏 schema 三假设、page_bottom_closer 槽 | 每个槽位可空；空=诚实，交由上层处置 |

## 2. 分层架构

```
L1 定义层  布局定义（纯声明数据，可人工审阅/机器校验）
   │   树：container → columns → rows（每行声明角色、高度模型、识别契约）
   │   值：{窗口几何: 每运行实测} ∪ {语料阈值: 语料量定的群体边界}
   │   每条阈值带证据出处（如"N 帧量定"）
   ▼
L2 实现层  感知（measure / read）
   │   measure：首屏量定几何槽
   │   read：每屏照树识别行、填数据模板
   │   识别函数不再自带阈值——阈值从契约声明里来
   ▼
L3 消费层  动作（消费方的遍历/执行逻辑）
       只引用 schema 槽位，禁止裸像素猜测
       跨屏连续性不靠移动精度，靠消费方自己的状态记录
```

定义层与实现层的一致性不靠自觉，靠验证装置（§4）钉死。

## 3. 定义层长什么样（真实示例）

第一个消费者是微信朋友圈（moments-mcp）。下面摘它定义里的两行。
注意 `doorplate` / `time_row` 是**那个应用自己起的行角色名**（前者指
头像旁的作者名行，后者指正文下方的时间戳行）——ldl 本身不预设任何
应用词汇：

```python
LayoutDef(
  app="wechat-moments",
  columns={
    "pane":  ColumnSpec("pane", MEASURED, MEASURED),
    "photo": ColumnSpec("photo", MEASURED, MEASURED),
    "text":  ColumnSpec("text", "leftmost_cluster(time_rows,"
             " author_rows, long_rows)", MEASURED),
  },
  rows=[
    RowSpec("doorplate", "fixed(name_row_h)", ContractSpec(
        shape="author_shape_row_hugging_photo_ink_top",
        gates=["doorplate_hug_up", "doorplate_next_min",
               "doorplate_photo_min_ratio"],  # 键在 thresholds
        content_blind=True,            # 文字内容不参与（位置决定身份）
        exceptions=["sponsor_arrow"],  # 广告卡箭头探针 → 广告帖
        emits=["author_name"])),
    RowSpec("time_row", "fixed(time_row_h)", ContractSpec(
        shape="time_shape_row_on_text_column",
        gates=["time_row_x_slack"],
        content_blind=True,
        emits=["time_text", "comment_button"])),
  ],
  thresholds={"doorplate_hug_up": {"value": 0.008,
              "evidence": "235 帧量定"}, ...},
  measured=["name_row_h", "time_row_h"],
)
```

要点：**每一行 = 行角色 + 高度模型 + 识别契约**。契约里"什么证据可以
认定它、要过哪些检查、文字是否参与、例外是什么、产出什么"全部显式。

## 4. 验证装置（"机器验证"的制度化）

1. **语料**：真机帧库（本机 `local/corpus/`，git 忽略——帧含真实屏幕内容）。
2. **普查**：`ldl.census` 对每帧运行感知适配器，输出逐帧判定快照。
3. **一致性门**：定义层或实现层任何改动，重跑普查并 diff——**除声明允许的变化外零漂移才算过**；None↔判定翻转不允许豁免，必须人看。
4. **假设卡**：每条阈值登记证据（帧数/行数/边界数字），假设被推翻时改 thresholds 并留痕。

## 5. 迁移路径（第一个消费者：moments-mcp 朋友圈）

- 现状 = 定义（ASCII 文档串）+ 字段（FeedSchema/post dict）+ 实现（scan 过程）三者写在同一个 post_schema.py 里。
- 第 0 步（已完成 2026-11-25）：**基线普查**——用现有引擎当黑盒对全语料出快照（191 帧 / 368 行判定 / 零 None 零 error），作为重构前的零漂移基准。
- 第 1 步（已完成 2026-11-25）：把行和契约抽成 `ldl.schema` 定义（moments-mcp `services/digest/layout_def.py`，两行先行）。
- 第 2 步（已完成 2026-11-25）：感知函数改读定义，行为不变；普查 diff 零漂移验收（191/191 帧逐字节一致）。
- 后续候选：剩余阈值收编进定义、正文/评论行的契约补齐、普查例行化（近似 CI）、第二个 UI 应用按方法走一遍。
- 不重写感知引擎——先分离，后理顺。

## 6. 明确不做

- **不做通用 UI 自动化框架**：抽象只按真实消费者的需求长；通用化是走通两个实例后的归纳。
- 帧语料与含真实案例名的原始设计文档只存本机 `local/`（git 忽略），永不入公共仓。
