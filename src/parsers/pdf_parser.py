"""PDF 结构化解析模块 — 金融合同与产品要素跨页表格提取"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF
import pdfplumber
from loguru import logger

# ── 字段映射标准（统一 80 份 PDF 的异构字段名）─
FIELD_STANDARDIZATION: dict[str, str] = {
    # 合同相关
    "合同编号": "contract_id",
    "合同名称": "contract_name",
    "签约日期": "sign_date",
    "到期日期": "expiry_date",
    "甲方": "party_a",
    "乙方": "party_b",
    "合同金额": "contract_amount",
    "币种": "currency",
    # 产品相关
    "产品代码": "product_code",
    "产品名称": "product_name",
    "产品类型": "product_type",
    "净值日期": "nav_date",
    "单位净值": "unit_nav",
    "累计净值": "accumulated_nav",
    "日增长率": "daily_return",
    # 客户相关
    "客户姓名": "customer_name",
    "客户编号": "customer_id",
    "持仓份额": "holding_shares",
    "持仓市值": "holding_value",
    # 通用
    "基金管理人": "fund_manager",
    "托管银行": "custodian_bank",
    "风险等级": "risk_level",
    "费率": "fee_rate",
}


@dataclass
class ParsedTable:
    """解析出的结构化表格"""
    page_num: int
    table_index: int
    headers: list[str]
    rows: list[dict[str, object]]
    source_file: str = ""
    confidence: float = 1.0
    page_end: Optional[int] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ParsedTable":
        """Restore a table saved by :meth:`to_dict`, including older files."""
        page_start, _, legacy_page_end = str(data.get("page_num", 0)).partition("-")
        page_end = data.get("page_end") or legacy_page_end
        return cls(
            page_num=int(page_start),
            table_index=int(data.get("table_index", 0)),
            headers=[str(value) for value in data.get("headers", [])],
            rows=list(data.get("rows", [])),
            source_file=str(data.get("source_file", "")),
            confidence=float(data.get("confidence", 1.0)),
            page_end=int(page_end) if page_end else None,
        )


@dataclass
class ParsedDocument:
    """一份 PDF 解析后的完整结果"""
    source_file: str
    total_pages: int
    tables: list[ParsedTable] = field(default_factory=list)
    raw_text: str = ""
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "source_file": self.source_file,
            "total_pages": self.total_pages,
            "tables": [t.to_dict() for t in self.tables],
            # Persist the actual text. Keeping only its length made the service
            # rebuild an empty BM25 index after a restart.
            "raw_text": self.raw_text,
            "raw_text_length": len(self.raw_text),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ParsedDocument":
        """Restore a parsed document while remaining compatible with old JSON."""
        return cls(
            source_file=str(data.get("source_file", "")),
            total_pages=int(data.get("total_pages", 0)),
            tables=[ParsedTable.from_dict(item) for item in data.get("tables", [])],
            raw_text=str(data.get("raw_text", "")),
            metadata=dict(data.get("metadata", {})),
        )


class FinancialPDFParser:
    """
    金融 PDF 跨页表格结构化解析器

    策略：
      1. pdfplumber 提取表格（保留跨页信息）
      2. PyMuPDF 兜底纯文本区域
      3. 跨页表格按 header + 行合并
      4. 字段标准化映射
    """

    def __init__(self, input_dir: str, output_dir: str):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def parse_all(self) -> list[ParsedDocument]:
        """批量解析目录下所有 PDF"""
        pdf_files = sorted(self.input_dir.glob("*.pdf"))
        logger.info(f"发现 {len(pdf_files)} 份 PDF 待解析")

        results: list[ParsedDocument] = []
        for pdf_path in pdf_files:
            try:
                doc = self.parse_single(pdf_path)
                results.append(doc)
                # 保存中间结果
                out_path = self.output_dir / f"{pdf_path.stem}.json"
                out_path.write_text(json.dumps(doc.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception as e:
                logger.error(f"解析失败 {pdf_path.name}: {e}")

        logger.info(f"解析完成: {len(results)}/{len(pdf_files)} 份成功")
        return results

    def parse_single(self, pdf_path: Path) -> ParsedDocument:
        """解析单份 PDF"""
        doc = fitz.open(str(pdf_path))
        total_pages = len(doc)
        result = ParsedDocument(source_file=pdf_path.name, total_pages=total_pages)

        # ── 第一遍：pdfplumber 提取表格 ──
        all_tables: list[ParsedTable] = []
        with pdfplumber.open(str(pdf_path)) as pdf:
            for page_idx, page in enumerate(pdf.pages):
                tables = page.extract_tables(table_settings={
                    "vertical_strategy": "lines",
                    "horizontal_strategy": "lines",
                    "snap_tolerance": 3,
                })
                for t_idx, table in enumerate(tables or []):
                    if not table or len(table) < 2:
                        continue
                    headers, *body_rows = table
                    # 清洗 header
                    clean_headers = [self._clean_header(h or "") for h in headers]
                    rows = []
                    for row in body_rows:
                        row_dict = {}
                        for col_idx, cell in enumerate(row or []):
                            if col_idx < len(clean_headers):
                                key = clean_headers[col_idx]
                                row_dict[key] = self._normalize_cell(cell)
                        if any(v for v in row_dict.values()):
                            rows.append(row_dict)
                    if rows:
                        all_tables.append(ParsedTable(
                            page_num=page_idx + 1,
                            table_index=t_idx,
                            headers=clean_headers,
                            rows=rows,
                            source_file=pdf_path.name,
                        ))

        # ── 第二遍：跨页表格合并 ──
        merged_tables = self._merge_cross_page_tables(all_tables)
        result.tables = merged_tables

        # ── 第三遍：提取全文（用于 BM25）─
        try:
            result.raw_text = "\n".join(page.get_text() for page in doc)
        finally:
            doc.close()

        logger.info(f"{pdf_path.name}: {total_pages} 页, {len(merged_tables)} 个表格")
        return result

    # ── 内部方法 ──────────────────────────────────────

    @staticmethod
    def _clean_header(raw: str) -> str:
        """清洗表头：去空白、换行、统一异构字段"""
        h = re.sub(r"[\s\n\r\t]+", "", str(raw).strip())
        # 常见异构映射
        alias_map = {
            "合同号": "合同编号", "合约编号": "合同编号", "协议编号": "合同编号",
            "产品代号": "产品代码", "基金代码": "产品代码",
            "最新净值": "单位净值", "NAV": "单位净值",
            "客户名": "客户姓名", "投资者名称": "客户姓名",
            "持有份额": "持仓份额", "持有市值": "持仓市值",
            "成立日期": "签约日期", "起息日": "签约日期",
            "终止日期": "到期日期", "到期日": "到期日期",
        }
        return alias_map.get(h, h)

    @staticmethod
    def _normalize_cell(cell: object) -> str | float | None:
        """清洗单元格值"""
        if cell is None:
            return None
        s = str(cell).strip()
        s = re.sub(r"[\s\n\r\t]+", " ", s)
        # 尝试转数字
        try:
            # 处理千分位和百分号
            s_clean = s.replace(",", "").replace("%", "")
            if "." in s_clean:
                return float(s_clean)
            return int(s_clean)
        except (ValueError, OverflowError):
            pass
        return s if s else None

    def _merge_cross_page_tables(self, tables: list[ParsedTable]) -> list[ParsedTable]:
        """
        合并跨页表格

        判定逻辑：
          - 相邻页面的表格 header 相似度 > 0.8 → 视为同一表格的续页
          - 续表无 header 行（或 header 为空），直接合并行
        """
        if not tables:
            return []

        merged: list[ParsedTable] = []
        current = tables[0]

        for nxt in tables[1:]:
            current_end = current.page_end or current.page_num
            is_continuation = (
                nxt.page_num == current_end + 1
                and self._header_similarity(current.headers, nxt.headers) > 0.8
            )
            if is_continuation:
                # 续表行追加到当前表
                current.rows.extend(nxt.rows)
                current.page_end = nxt.page_end or nxt.page_num
            else:
                merged.append(current)
                current = nxt

        merged.append(current)
        return merged

    @staticmethod
    def _header_similarity(h1: list[str], h2: list[str]) -> float:
        """计算两组 header 的 Jaccard 相似度"""
        s1, s2 = set(h1), set(h2)
        if not s1 or not s2:
            return 0.0
        return len(s1 & s2) / len(s1 | s2)


# ── CLI 入口 ────────────────────────────────────────────
if __name__ == "__main__":
    from src.config.settings import get_settings

    settings = get_settings()
    parser = FinancialPDFParser(settings.pdf_input_dir, settings.parsed_output_dir)
    results = parser.parse_all()

    total_tables = sum(len(d.tables) for d in results)
    total_rows = sum(len(t.rows) for d in results for t in d.tables)
    print(f"\n解析统计: {len(results)} 份 PDF → {total_tables} 个表格, {total_rows} 行数据")
