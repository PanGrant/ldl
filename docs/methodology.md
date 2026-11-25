# 布局 Schema 方法论 —— 定义与实现分离

> 状态：**已开工**（2026-11-25）。本仓 = 方法的载体：`ldl.schema` 是 L1，
> `ldl.census` 是 §4 的验证装置，L2 随第一个消费者（朋友圈布局）生长。
> 原始草稿与本仓演进的完整决策史见本机 `local/design-docs/`（含真实
> 案例名，不入公共仓）。

## 0. 一句话目标

把"读懂一张桌面 UI 并对它操作"变成可复用的三段方法：

1. **人假设**：观察桌面布局规律，人画出结构假设（像写 HTML：容器、列、行，行高可变）；
2. **机器验证**：用真机帧语料逐条验证假设（普查：每条声明要有数字支撑，不成立就改假设）；
3. **照图施工**：布局 schema 定稿后，感知（认知）和操作（动作）都只对着 schema 做——定义是图纸，实现是施工，两者物理分开。

朋友圈 walker 是这个方法的第一个成品（摸出来的，不是照方法做的）。ldl 把它提炼成库，**下一个 UI 布局按方法走一遍**。

## 1. 为什么要做（血训出处）

| 教训 | 出处 | 方法论里的对应物 |
|---|---|---|
| 图纸和施工混在一个文件里，漂移靠测试才能抓回 | 2026-11-23 某头像样式冤案：ASCII 图说"这格是名字"，代码里混进三道内容检查，门牌判错 | 定义层 / 实现层物理分离 + 一致性普查 |
| 散逻辑=每处一套谓词/阈值，漂移不可查 | 2026-11-15 宪法第一条 | 判据全部声明在 schema，函数只消费声明 |
| 窗口每次可能不同，答案永远是测量 | 2026-11-15 宪法第三条（441pt→509pt 实证） | 值分两类：窗口几何（每运行实测）vs 物种习性（语料量定的群体边界） |
| 位置决定身份，内容不参与座位判定 | 2026-11-23 宪法修正（名字区只认位置） | 识别契约里显式声明 content: blind + 例外（箭头探针） |
| 感知失败必须诚实为 None，绝不瞎判 | 落屏 schema 三假设、page_bottom_closer 槽 | 每个槽位可空；空=诚实，交由循环处置 |

## 2. 分层架构

```
L1 定义层  layout schema（纯声明数据，可人工审阅/机器校验）
   │   树：container → columns → rows（每行声明角色、高度模型、识别契约）
   │   值：{窗口几何: 每运行实测} ∪ {物种习性: 语料量定的群体边界}
   │   每条声明带证据出处（如"N 帧真门牌量定"）
   ▼
L2 实现层  感知（measure / read）
   │   measure：首屏量定几何槽
   │   read：每屏照树填每帖模板
   │   识别函数不再自带门——门从契约声明里来
   ▼
L3 操作层  动作（消费方的 walker / act）
       只引用 schema 槽位，禁止裸像素猜测
       跨屏连续性不靠移动精度，靠帐本（消费方自理）
```

定义层与实现层的一致性不靠自觉，靠验证装置（§4）钉死。

## 3. 定义层长什么样（朋友圈实例，示意）

Python 纯数据（`ldl.schema`，可 to_dict/from_dict 往返供机器校验）。
示意：

```python
LayoutDef(
  app="wechat-moments",
  columns={
    "pane":  ColumnSpec("pane", MEASURED, MEASURED),
    "photo": ColumnSpec("photo", "pane.x0+0.02", "text.x0-0.008"),
    "text":  ColumnSpec("text", "leftmost_text", MEASURED),
  },
  rows=[
    RowSpec("doorplate", "fixed(name_row_h)", ContractSpec(
        admit="hug_photo_block_top",
        gates=["hug_window", "photo_stature", "clearance"],  # 结构三关
        content_blind=True,            # 内容不参与（宪法）
        exceptions=["sponsor_arrow"],  # 箭头探针 → 广告帖
        emits=[])),
    RowSpec("time_row", "fixed(time_row_h)", ContractSpec(
        admit="time_shape_row",
        gates=["x_on_text_column"],
        emits=["comment_button"])),
    RowSpec("body", "variable", ContractSpec(
        admit="under_doorplate", content_blind=False,
        content_blind_why="正文内容本身就是要提取的数据",
        emits=["expand_link"])),
    RowSpec("comments", "variable", ContractSpec(
        admit="under_time_row", content_blind=True,
        gates=["indent_column"])),
  ],
  habits={"name_row_h": {"value": ..., "evidence": "N 帧量定"}, ...},
)
```

要点：**每个座位 = 角色 + 高度模型 + 识别契约**。契约里"什么证据可以
入座、过哪几道门、内容是否参与、例外是什么"全部显式。

## 4. 验证装置（"机器验证"的制度化）

1. **语料**：真机帧库（本机 `local/corpus/`，git 忽略——帧含真实屏幕内容）。
2. **普查**：`ldl.census` 对每帧运行感知适配器，输出逐帧判定快照。
3. **一致性门**：定义层或实现层任何改动，重跑普查并 diff——**除声明允许的变化外零漂移才算过**；None↔判定翻转不允许豁免，必须人看。
4. **假设卡**：每条习性声明登记证据（帧数/座数/边界数字），假设被推翻时改 habits 并留痕。

## 5. 迁移路径（第一个消费者：moments-mcp 朋友圈）

- 现状 = 图纸（ASCII 文档串）+ 字段（FeedSchema/post dict）+ 施工（scan 过程）三者同居在 post_schema.py。
- 第 0 步（已完成）：**基线普查**——用现有引擎当黑盒对全语料出快照，作为重构前的零漂移基准。
- 第 1 步：把树和契约抽成 `ldl.schema` 定义（先门牌/时间行两个座位试点）。
- 第 2 步：感知函数改读声明施工，行为不变；普查 diff 零意外漂移验收。
- 不重写感知引擎——先分离，后理顺。

## 6. 明确不做

- **不做通用 UI 自动化框架**：抽象只按真实消费者的需求长；通用化是走通两个实例后的归纳。
- 帧语料与含真实案例名的原始设计文档只存本机 `local/`（git 忽略），永不入公共仓。
