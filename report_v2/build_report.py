#!/usr/bin/env python3
"""对照品对账 V2：比对三库 -> 生成结构化报告 + 钉钉 markdown + 待发布原文件。

用法：python report_v2/build_report.py
设计约束：
1. 任何单库失败都记录为 error，绝不中断整体流程，保证 report.json 始终产出。
2. 不修改仓库根目录的任何原有脚本。
3. 日志错误摘要写入 report.json，网页 /api/report/status 可直接读取，无需翻 Actions 日志。
"""

from __future__ import annotations

import io
import json
import os
import quopri
import re
import shutil
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = HERE / "output"
FILES = OUT / "files"
LOGS = OUT / "logs"
for _d in (OUT, FILES, LOGS):
    _d.mkdir(parents=True, exist_ok=True)

BASE_FILE = ROOT / "现有全部对照品目录.xlsx"
BEIJING = timezone(timedelta(hours=8))
NOW = datetime.now(BEIJING)
DATE_TAG = NOW.strftime("%Y%m%d")

REPORT_URL = os.environ.get("REPORT_URL", "").strip()
RUN_ID = os.environ.get("GITHUB_RUN_ID", "").strip()
RUN_URL = os.environ.get("GITHUB_RUN_URL", "").strip()
ARTIFACT_NAME = "reference-excels"

SOURCES = {
    "chp": {
        "label": "国家药品标准物质目录 (ChP)",
        "short": "ChP",
        "path": ROOT / "国家药品标准物质目录_全量在售.xlsx",
        "base_cols": ("对照品中文名称", "对照品中文批号Chp"),
    },
    "edqm": {
        "label": "EDQM 欧洲药典",
        "short": "EP",
        "path": ROOT / "EDQM_Catalog_Output.xlsx",
        "base_cols": ("对照品英文名称EP", "对照品英文批号EP"),
    },
    "usp": {
        "label": "USP 美国药典",
        "short": "USP",
        "path": ROOT / "usprefstd.xls",
        "base_cols": ("对照品英文名称USP", "对照品英文批号USP"),
    },
}


def clean(series):
    """只去空格、转大写，不改动数字内容。"""
    return (
        series.fillna("")
        .astype(str)
        .str.replace(r"\s+", "", regex=True)
        .str.strip()
        .str.upper()
    )


def find_col(df, *keywords):
    """列名模糊匹配：忽略空格与大小写，修掉旧脚本硬编码 'Batc h n°' 的问题。"""
    for col in df.columns:
        flat = re.sub(r"\s+", "", str(col)).lower()
        if all(k.lower() in flat for k in keywords):
            return col
    return None


def load_base(name_col, lot_col):
    if not BASE_FILE.exists():
        raise FileNotFoundError(f"未找到基准表：{BASE_FILE.name}")
    df = pd.read_excel(BASE_FILE, dtype=str)
    if name_col not in df.columns or lot_col not in df.columns:
        raise KeyError(
            f"基准表缺少列 {name_col}/{lot_col}，实际列名：{df.columns.tolist()}"
        )
    sub = df[[name_col, lot_col]].dropna(subset=[name_col]).copy()
    sub["_n"] = clean(sub[name_col])
    sub["_l"] = clean(sub[lot_col])
    return sub


def read_chp():
    df = pd.read_excel(SOURCES["chp"]["path"], dtype=str)
    df.columns = df.columns.astype(str).str.replace(r"\s+", "", regex=True)
    name_col = find_col(df, "品名")
    lot_col = find_col(df, "批号")
    if not name_col or not lot_col:
        raise KeyError(f"ChP 目录未找到 品名/批号 列，实际列名：{df.columns.tolist()}")
    sub = df[[name_col, lot_col]].dropna(subset=[name_col]).copy()
    return set(zip(clean(sub[name_col]), clean(sub[lot_col]))), len(df)


def read_edqm():
    df = pd.read_excel(SOURCES["edqm"]["path"], dtype=str)
    df.columns = df.columns.astype(str)
    name_col = find_col(df, "reference", "standard") or find_col(df, "reference")
    lot_col = find_col(df, "batch")
    if not name_col or not lot_col:
        raise KeyError(f"EDQM 目录未找到 Reference Standard/Batch 列，实际列名：{df.columns.tolist()}")
    sub = df[[name_col, lot_col]].dropna(subset=[name_col]).copy()
    return set(zip(clean(sub[name_col]), clean(sub[lot_col]))), len(df)


def read_usp():
    """USP 文件是 MHTML + quoted-printable，先解码再找含 Product Name / Current Lot 的表。"""
    import bs4

    raw = SOURCES["usp"]["path"].read_bytes()
    text = quopri.decodestring(raw).decode("utf-8", errors="ignore")
    dfs = pd.read_html(io.StringIO(text), flavor="lxml")
    if not dfs:
        raise ValueError("USP 文件解码后未找到任何 HTML 表格")

    chosen = None
    for df in dfs:
        df = df.astype(str)
        header_idx = None
        for i in range(min(10, len(df))):
            vals = [re.sub(r"\s+", "", v).lower() for v in df.iloc[i].astype(str).tolist()]
            if any("productname" in v for v in vals) and any("currentlot" in v for v in vals):
                header_idx = i
                break
        if header_idx is None:
            cols = [re.sub(r"\s+", "", str(c)).lower() for c in df.columns]
            if any("productname" in c for c in cols) and any("currentlot" in c for c in cols):
                header_idx = -1
        if header_idx is None:
            continue
        if header_idx >= 0:
            df.columns = df.iloc[header_idx].astype(str)
            df = df.iloc[header_idx + 1:].reset_index(drop=True)
        df = df.astype(str)
        chosen = df
        break

    if chosen is None:
        chosen = dfs[0].astype(str)

    name_col = find_col(chosen, "product", "name")
    lot_col = find_col(chosen, "current", "lot") or find_col(chosen, "lot")
    if not name_col or not lot_col:
        raise KeyError(f"USP 目录未找到 Product Name/Current Lot 列，实际列名：{chosen.columns.tolist()}")

    sub = chosen[[name_col, lot_col]].dropna(subset=[name_col]).copy()
    return set(zip(clean(sub[name_col]), clean(sub[lot_col]))), len(chosen)


READERS = {"chp": read_chp, "edqm": read_edqm, "usp": read_usp}


def compare_one(key):
    info = SOURCES[key]
    name_col, lot_col = info["base_cols"]
    result = {
        "label": info["label"],
        "ok": False,
        "skipped": False,
        "note": "",
        "source_file": info["path"].name,
        "source_exists": info["path"].exists(),
        "checked": 0,
        "catalog_rows": 0,
        "missing": [],
        "error": "",
    }
    try:
        if not info["path"].exists():
            raise FileNotFoundError(f"未找到当日抓取文件：{info['path'].name}")
        base = load_base(name_col, lot_col)
        existing, catalog_rows = READERS[key]()
        missing = []
        for _, row in base.iterrows():
            if (row["_n"], row["_l"]) not in existing:
                missing.append(f"{row[name_col]} (批号: {row[lot_col]})")
        result.update(
            ok=True,
            checked=len(base),
            catalog_rows=catalog_rows,
            missing=missing,
        )
        if len(base) == 0:
            # 基准表该库列为空仍算正常比对：核对 0 条、未匹配 0 条，
            # 只有官方目录没抓到（上面的 FileNotFoundError）才算"未比对"。
            result["note"] = f"目前正在使用的{info['short']}对照品库的名称/批号列为空"
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        result["traceback"] = traceback.format_exc(limit=4)
    return result


def collect_log_errors():
    """汇总各抓取步骤的日志错误，供网页直接展示。"""
    hits = []
    pattern = re.compile(r"Traceback|Error|Exception|错误|警告|失败|致命", re.IGNORECASE)
    for path in sorted(LOGS.glob("*.log")):
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for idx, line in enumerate(lines, 1):
            if pattern.search(line):
                hits.append({"file": path.name, "line": idx, "text": line.strip()[:300]})
    return hits[-60:]


def publish_source_files():
    published = []
    for key, info in SOURCES.items():
        src = info["path"]
        if not src.exists():
            continue
        target = FILES / f"{key}_{DATE_TAG}{src.suffix}"
        shutil.copy2(src, target)
        published.append(
            {
                "key": key,
                "label": info["label"],
                "filename": target.name,
                "size_bytes": target.stat().st_size,
            }
        )
    return published


def build_markdown(report):
    summary = report["summary"]
    if summary["status"] == "error":
        headline = "**结论：🚨 有官方目录未能成功抓取或读取，相应库本次未比对，请检查运行日志**"
    elif summary["missing_total"]:
        headline = "**结论：⚠️ 发现未匹配品种，请复核下方清单**"
    else:
        headline = (
            "**结论：✅ 所有正在使用的对照品信息（品名/批号）与三大药典最新官网数据"
            "均完全一致，未发现失效或下架品种。**"
        )

    total_checked = sum(s["checked"] for s in report["sources"].values())
    lines = [
        f"## 对照品信息对账日报 {NOW.strftime('%Y-%m-%d')}",
        "",
        headline,
        "",
        f"- 目前正在使用的法定对照品条目（ChP+EP+USP 合计）：{total_checked} 条",
        f"- 未匹配合计：{summary['missing_total']} 条",
        f"- 执行异常：{summary['error_total']} 项",
        f"- 未比对库：{summary['error_total']} 个",
        "",
    ]
    for key, src in report["sources"].items():
        if not src["ok"]:
            err_first = src["error"].splitlines()[0][:120] if src["error"] else "未知错误"
            lines.append(f"- {src['label']}：**未比对** — 官方目录抓取或读取失败：{err_first}")
        else:
            note = f" — {src['note']}" if src.get("note") else ""
            lines.append(
                f"- {src['label']}：核对 {src['checked']} 条，未匹配 {len(src['missing'])} 条{note}"
            )
    lines.append("")

    for key, src in report["sources"].items():
        if src["missing"]:
            lines.append(f"### {src['label']} 未匹配清单")
            for item in src["missing"][:30]:
                lines.append(f"- {item}")
            if len(src["missing"]) > 30:
                lines.append(f"- ……另有 {len(src['missing']) - 30} 条，见网页")
            lines.append("")

    if report["log_errors"]:
        lines.append("### 运行日志摘要")
        for hit in report["log_errors"][:8]:
            lines.append(f"- `{hit['file']}:{hit['line']}` {hit['text'][:120]}")
        lines.append("")

    if REPORT_URL:
        lines.append(f"[打开对账查询网页（含 3 个原始 Excel 下载）]({REPORT_URL})")
    elif RUN_URL:
        lines.append(f"[查看本次运行日志]({RUN_URL})")
    else:
        lines.append("> 未配置 REPORT_URL，钉钉消息中不含网页链接。")
    lines.append("")
    lines.append(f"> 生成时间：{NOW.strftime('%Y-%m-%d %H:%M')}（北京时间） · 原文件保留 7 天")
    return "\n".join(lines)


def main():
    sources = {key: compare_one(key) for key in SOURCES}
    log_errors = collect_log_errors()
    published = publish_source_files()

    error_total = sum(1 for s in sources.values() if not s["ok"])
    missing_total = sum(len(s["missing"]) for s in sources.values())
    skipped_total = sum(1 for s in sources.values() if s["skipped"])
    if error_total:
        status = "error"
    elif missing_total:
        status = "warning"
    else:
        status = "ok"

    report = {
        "generated_at": NOW.isoformat(),
        "date": DATE_TAG,
        "status": status,
        "run_id": RUN_ID,
        "run_url": RUN_URL,
        "artifact_name": ARTIFACT_NAME,
        "report_url": REPORT_URL,
        "summary": {
            "status": status,
            "error_total": error_total,
            "missing_total": missing_total,
            "skipped_total": skipped_total,
            "log_error_total": len(log_errors),
        },
        "sources": sources,
        "files": published,
        "log_errors": log_errors,
    }

    (OUT / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (OUT / "dingtalk.md").write_text(build_markdown(report), encoding="utf-8")
    (OUT / "notify_status.json").write_text(
        json.dumps({"sent": False, "reason": "pending"}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"[build_report] 状态={status} 未匹配={missing_total} 单库失败={error_total} 日志错误={len(log_errors)}")
    print(f"[build_report] 已发布原文件 {len(published)} 个：{[f['filename'] for f in published]}")
    print(f"[build_report] 报告输出：{OUT / 'report.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
