"""ldl L1 —— 布局定义层（纯声明数据 + 校验）。

一个 LayoutDef 是一份布局定义：app 名 + 列声明 + 行序列 + 阈值表。
每一行（row）= 行角色 + 高度模型 + 识别契约。契约里「凭什么证据认定
这一行、要过哪些位置检查、文字内容是否参与判定、有哪些例外、产出
哪些槽位」全部显式——硬规则（如 content_blind）是声明的一部分，
不是函数里的注释。

值的两种类：
- 窗口几何（measured 登记）：每运行实测，定义里只登记槽位名；
- 语料阈值（thresholds 表）：从帧语料量定的群体边界，每条必须带
  value + evidence（证据出处）。假设被推翻时改阈值表并留痕。

定义可 to_dict/from_dict 往返（机器可校验、diff 友好）。纯 stdlib。
"""
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional

MEASURED = "measured"   # 窗口几何标记：消费方每运行实测，定义不写死


@dataclass
class ContractSpec:
    """一行（row）的识别契约：凭什么认定它、要过哪些检查。"""
    shape: str                     # 认定证据的形状声明（如 "time_shape_row_on_text_column"）
    gates: List[str] = field(default_factory=list)   # 位置/结构检查序列；键必须存在于 thresholds
    content_blind: bool = True     # 文字内容不参与行判定；False 必须写理由
    content_blind_why: str = ""    # content_blind=False 时的理由（强制留痕）
    exceptions: List[str] = field(default_factory=list)  # 例外探针名（如 sponsor_arrow）
    emits: List[str] = field(default_factory=list)       # 该行认定后产出的槽位名

    def validate(self) -> List[str]:
        errs = []
        if not self.shape or not isinstance(self.shape, str):
            errs.append("shape 必须是非空字符串（形状声明）")
        if not self.content_blind and not self.content_blind_why:
            errs.append("content_blind=False 必须写 content_blind_why（留痕）")
        return errs


@dataclass
class RowSpec:
    """一行：行角色 + 高度模型 + 契约。行高多数可变（"variable"）；
    "fixed(...)" 指向 thresholds 里的一个固定高度，或 measured 里的
    一个每运行实测槽位（窗口几何——高度不能写死在定义里）。"""
    role: str
    height: str                    # "variable" 或 "fixed(<thresholds/measured 键>)"
    contract: ContractSpec

    def validate(self, thresholds: Dict, measured: Optional[List[str]] = None
                 ) -> List[str]:
        errs = list(self.contract.validate())
        if not self.role or not isinstance(self.role, str):
            errs.append("role 必须是非空字符串")
        if self.height == "variable":
            pass
        elif self.height.startswith("fixed(") and self.height.endswith(")"):
            key = self.height[len("fixed("):-1]
            if key not in thresholds and key not in (measured or []):
                errs.append(f"fixed 高度指向未知键（thresholds/measured "
                            f"里都没有）: {key}")
        else:
            errs.append(f"height 必须是 'variable' 或 'fixed(<键>)': "
                        f"{self.height!r}")
        return errs


@dataclass
class ColumnSpec:
    """一列：名字 + 左右界。界可为 MEASURED（每运行实测）或表达式
    字符串（如 "pane.x0+0.03"）——表达式由消费方解释，定义层只存字面。"""
    name: str
    x0: str
    x1: str

    def validate(self) -> List[str]:
        errs = []
        if not self.name:
            errs.append("列必须有名字")
        for side in ("x0", "x1"):
            v = getattr(self, side)
            if not v or not isinstance(v, str):
                errs.append(f"列 {self.name}.{side} 必须是字符串"
                            f"（{MEASURED} 或表达式）")
        return errs


@dataclass
class LayoutDef:
    """一份布局定义。rows 顺序 = 屏上自上而下。"""
    app: str
    columns: Dict[str, ColumnSpec] = field(default_factory=dict)
    rows: List[RowSpec] = field(default_factory=list)
    thresholds: Dict[str, Dict] = field(default_factory=dict)  # 键 → {value, evidence}
    measured: List[str] = field(default_factory=list)  # 每运行实测槽位名（窗口几何）

    def validate(self) -> List[str]:
        errs = []
        if not self.app:
            errs.append("app 必须非空")
        for name in self.measured:
            if not name or not isinstance(name, str):
                errs.append(f"measured 槽位名必须是非空字符串: {name!r}")
        for col in self.columns.values():
            errs.extend(col.validate())
        seen = set()
        for row in self.rows:
            if row.role in seen:
                errs.append(f"角色重复: {row.role}")
            seen.add(row.role)
            errs.extend(row.validate(self.thresholds, self.measured))
            for gate in row.contract.gates:
                if gate not in self.thresholds:
                    errs.append(f"行 {row.role} 的检查 {gate!r} 不在 "
                                f"thresholds 表")
            for e in row.contract.exceptions:
                if e not in self.thresholds and e not in _KNOWN_PROBES:
                    errs.append(f"行 {row.role} 的例外 {e!r} 既非阈值也非"
                                f"已知探针")
        for key, h in self.thresholds.items():
            if "value" not in h or "evidence" not in h:
                errs.append(f"阈值 {key} 缺 value/evidence（每条阈值必须"
                            f"带证据出处）")
        clash = set(self.thresholds) & set(self.measured)
        if clash:
            errs.append(f"键同时出现在 thresholds 和 measured（语料阈值 "
                        f"vs 窗口几何，必须二选一）: {sorted(clash)}")
        return errs

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict) -> "LayoutDef":
        cols = {k: ColumnSpec(**v) for k, v in (d.get("columns") or {}).items()}
        rows = [RowSpec(role=r["role"], height=r["height"],
                        contract=ContractSpec(**r["contract"]))
                for r in d.get("rows") or []]
        return cls(app=d.get("app", ""), columns=cols, rows=rows,
                   thresholds=d.get("thresholds") or {},
                   measured=list(d.get("measured") or []))


# 像素探针注册表：例外若不是语料阈值，必须是这里登记过的探针名。
# 消费方可以扩展（ldl 不预设实现——探针执行留在消费侧）。
_KNOWN_PROBES = {"sponsor_arrow"}
