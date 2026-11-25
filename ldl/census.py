"""ldl 验证装置 —— 语料普查与零漂移门。

用法（库 API 或 CLI）：

    # 快照：对帧目录逐帧跑适配器，落一份判定快照
    python -m ldl.census snapshot <frames_dir> <out.json> \
        --adapter "pkg.module:fn"
    # 漂移：两份快照对比；除 allowlist 外零差异才算过
    python -m ldl.census diff <old.json> <new.json> [--allow none-frames]

适配器协议：fn(image_path) -> dict | None（dict 必须可 JSON 序列化；
None = 诚实不可判——也入快照，diff 时按 none-frames 类别报）。

快照里是真实屏幕内容 → 落盘路径由调用方负责放进本机非公开目录。
纯 stdlib。
"""
import argparse
import json
import os
import sys
from typing import Callable, Dict, List, Optional, Tuple

IMAGE_EXTS = (".png", ".jpg", ".jpeg")


def _import_adapter(spec: str) -> Callable[[str], Optional[Dict]]:
    """'pkg.module:fn' → 函数。路径式 'file.py:fn' 也收（'/' 或 '.py'
    结尾段视为路径）。"""
    mod_part, _, fn_part = spec.partition(":")
    if not fn_part:
        raise SystemExit(f"adapter 需要形如 module:fn：{spec}")
    if mod_part.endswith(".py") or "/" in mod_part or os.sep in mod_part:
        import importlib.util
        path = os.path.abspath(mod_part)
        name = "__census_adapter_" + \
            "".join(c if c.isalnum() else "_" for c in os.path.basename(path))
        mspec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(mspec)
        mspec.loader.exec_module(mod)      # noqa: 执行消费方适配器
    else:
        import importlib
        mod = importlib.import_module(mod_part)
    return getattr(mod, fn_part)


def snapshot(frames_dir: str, adapter: Callable[[str], Optional[Dict]],
             on_frame=None) -> Dict:
    """逐帧运行适配器 → {帧名: 判定|None}。帧名按字典序（确定性）。
    on_frame(name, result, error) 供进度显示。适配器抛异常 = 该帧
    记 error 字符串（普查不中断；异常本身也是行为，漂移门要抓它）。"""
    names = sorted(n for n in os.listdir(frames_dir)
                   if n.lower().endswith(IMAGE_EXTS))
    out: Dict[str, object] = {}
    for n in names:
        path = os.path.join(frames_dir, n)
        try:
            r = adapter(path)
            rec = {"result": r} if r is not None else {"result": None}
        except Exception as e:              # noqa: 普查吞异常记账，不中断
            rec = {"error": repr(e)[:300]}
        out[n] = rec
        if on_frame:
            on_frame(n, rec)
    return out


def write_snapshot(data: Dict, path: str) -> None:
    d = os.path.dirname(path) or "."
    os.makedirs(d, exist_ok=True)
    tmp = f"{path}.tmp-{os.getpid()}"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1, sort_keys=True)
    os.replace(tmp, path)


def diff(old: Dict, new: Dict,
         allow_none_frames: bool = False) -> Tuple[List[str], Dict]:
    """两份快照对比。返回 (问题列表, 统计)。None↔内容 的翻转**不算**
    none-frames 类别——那是判定变了，必须人看；只有 内容↔内容 且相等
    之外的合法类别是 None↔None。"""
    problems: List[str] = []
    stats = {"added": 0, "removed": 0, "changed": 0, "none_flips": 0,
             "errors": 0, "same": 0}
    for name in sorted(set(old) | set(new)):
        if name not in old:
            stats["added"] += 1
            problems.append(f"+ 新帧出现（语料变了？）: {name}")
            continue
        if name not in new:
            stats["removed"] += 1
            problems.append(f"- 帧消失: {name}")
            continue
        o, n = old[name], new[name]
        if o == n:
            stats["same"] += 1
            continue
        # 容错类别：两侧同为 None（判定为"诚实不可判"且一致）——不报
        o_none = o.get("result", "MISSING") is None and "error" not in o
        n_none = n.get("result", "MISSING") is None and "error" not in n
        if o_none and n_none:
            stats["same"] += 1
            continue
        if "error" in o or "error" in n:
            stats["errors"] += 1
            problems.append(f"! 适配器异常状态变化: {name}")
            continue
        o_was_none = o.get("result") is None
        n_was_none = n.get("result") is None
        if o_was_none != n_was_none:
            stats["none_flips"] += 1
            problems.append(f"! None↔判定翻转（不许,必须人看）: {name}")
            continue
        if allow_none_frames and (o_was_none or n_was_none):
            # 双侧都有判定但不等、且允许 none 相关帧——仍属"变化"，除非
            # 用户显式给该帧开脱；保守起见计入 changed
            stats["changed"] += 1
            problems.append(f"~ 判定变化: {name}")
            continue
        stats["changed"] += 1
        problems.append(f"~ 判定变化: {name}")
    return problems, stats


def _cli(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="ldl.census")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("snapshot")
    sp.add_argument("frames_dir")
    sp.add_argument("out")
    sp.add_argument("--adapter", required=True)
    dp = sub.add_parser("diff")
    dp.add_argument("old")
    dp.add_argument("new")
    dp.add_argument("--allow-none-frames", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "snapshot":
        fn = _import_adapter(a.adapter)
        done = {"n": 0}

        def prog(name, rec):
            done["n"] += 1
            if done["n"] % 10 == 0 or rec.get("error"):
                print(f"[census] {done['n']} 帧… {name}"
                      + (" ⚠error" if rec.get("error") else ""),
                      file=sys.stderr)

        data = snapshot(a.frames_dir, fn, on_frame=prog)
        write_snapshot(data, a.out)
        n_none = sum(1 for v in data.values()
                     if v.get("result") is None and "error" not in v)
        n_err = sum(1 for v in data.values() if "error" in v)
        print(f"[census] 快照 {len(data)} 帧 → {a.out} "
              f"(None={n_none} error={n_err})")
        return 0
    with open(a.old, encoding="utf-8") as f:
        old = json.load(f)
    with open(a.new, encoding="utf-8") as f:
        new = json.load(f)
    problems, stats = diff(old, new, allow_none_frames=a.allow_none_frames)
    for p in problems[:40]:
        print(p)
    if len(problems) > 40:
        print(f"…另有 {len(problems) - 40} 条")
    verdict = "PASS（零漂移）" if not problems else f"FAIL（{len(problems)} 项）"
    print(f"[census] {stats} → {verdict}")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(_cli())
