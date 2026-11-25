"""ldl L1 —— 布局定义层（纯声明数据 + 校验）。

一个 LayoutDef 是一张图纸：app 名 + 列声明 + 行序列 + 物种习性表。
每个座位（row）= 角色 + 高度模型 + 识别契约。契约里「什么证据可以
入座、过哪几道结构门、内容是否参与、例外是什么、产出哪些槽位」全部
显式——宪法级决定（如 content: blind）是声明的一部分，不是函数里的
注释。

值的两种类（宪法第三条）：
- 窗口几何：每运行实测，定义里只写 "measured"；
- 物种习性：语料量定的群体边界，值进 habits 表，每条带证据出处
  （帧数/座数/边界数字）。假设被推翻时改 habits 并留痕。

定义可 to_dict/from_dict 往返（机器可校验、diff 友好）。纯 stdlib。
"""
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional

MEASURED = "measured"   # 窗口几何标记：消费方每运行实测，定义不写死


@dataclass
class ContractSpec:
    """一个座位的识别契约。"""
    admit: str                     # 入座证据的形状声明（如 "hug_photo_top"）
    gates: List[str] = field(default_factory=list)   # 结构门序列（habits 里的名字）
    content_blind: bool = True     # 内容不参与座位判定（宪法；False 需在声明里写理由）
    content_blind_why: str = ""    # content_blind=False 时的理由（强制留痕）
    exceptions: List[str] = field(default_factory=list)  # 例外探针名（如 sponsor_arrow）
    emits: List[str] = field(default_factory=list)       # 该座位产出的槽位名

    def validate(self) -> List[str]:
        errs = []
        if not self.admit or not isinstance(self.admit, str):
            errs.append("admit 必须是非空字符串（形状声明）")
        if not self.content_blind and not self.content_blind_why:
            errs.append("content_blind=False 必须写 content_blind_why（留痕）")
        return errs


@dataclass
class RowSpec:
    """一个座位：角色 + 高度模型 + 契约。行高多数可变，fixed(...) 指
    向 habits 里的一个固定高度量名。"""
    role: str
    height: str                    # "variable" 或 "fixed(<habit_key>)"
    contract: ContractSpec

    def validate(self, habits: Dict) -> List[str]:
        errs = list(self.contract.validate())
        if not self.role or not isinstance(self.role, str):
            errs.append("role 必须是非空字符串")
        if self.height == "variable":
            pass
        elif self.height.startswith("fixed(") and self.height.endswith(")"):
            key = self.height[len("fixed("):-1]
            if key not in habits:
                errs.append(f"fixed 高度指向未知习性键: {key}")
        else:
            errs.append(f"height 必须是 'variable' 或 'fixed(<habit_key>)': "
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
    """一张布局图纸。rows 顺序 = 屏上自上而下。"""
    app: str
    columns: Dict[str, ColumnSpec] = field(default_factory=dict)
    rows: List[RowSpec] = field(default_factory=list)
    habits: Dict[str, Dict] = field(default_factory=dict)  # 键 → {value, evidence}

    def validate(self) -> List[str]:
        errs = []
        if not self.app:
            errs.append("app 必须非空")
        for col in self.columns.values():
            errs.extend(col.validate())
        seen = set()
        for row in self.rows:
            if row.role in seen:
                errs.append(f"角色重复: {row.role}")
            seen.add(row.role)
            errs.extend(row.validate(self.habits))
            for gate in row.contract.gates:
                if gate not in self.habits:
                    errs.append(f"行 {row.role} 的门 {gate!r} 不在 habits 表")
            for e in row.contract.exceptions:
                if e not in self.habits and e not in _KNOWN_PROBES:
                    errs.append(f"行 {row.role} 的例外 {e!r} 既非习性也非"
                                f"已知探针")
        for key, h in self.habits.items():
            if "value" not in h or "evidence" not in h:
                errs.append(f"习性 {key} 缺 value/evidence（每条声明必须"
                            f"带证据出处）")
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
                   habits=d.get("habits") or {})


# 像素探针注册表：例外若不是物种习性，必须是这里登记过的探针名。
# 消费方可以扩展（ldl 不预设实现——探针执行留在消费侧）。
_KNOWN_PROBES = {"sponsor_arrow"}
