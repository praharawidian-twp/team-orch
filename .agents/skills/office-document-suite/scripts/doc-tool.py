#!/usr/bin/env python3
"""
doc-tool.py - Token-Efficient Office Document Suite CLI (Zero-Dependency Resilient)
Supports Inspect, Read, and Write for .xlsx, .docx, .pptx, .pdf, .doc, .rtf, .csv, .tsv, .json.

Standard Library only: zipfile, xml.etree.ElementTree, csv, json, re, sys, os, subprocess.
macOS Native Integrations: /usr/bin/textutil (doc/rtf), osascript/PDFKit (pdf).
"""

import os
import sys
import argparse
import json
import re
import csv
import io
import zipfile
import html
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
import xml.etree.ElementTree as ET
import struct
import copy

ET.register_namespace("w", "http://schemas.openxmlformats.org/wordprocessingml/2006/main")
ET.register_namespace("wp", "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing")
ET.register_namespace("a", "http://schemas.openxmlformats.org/drawingml/2006/main")
ET.register_namespace("pic", "http://schemas.openxmlformats.org/drawingml/2006/picture")
ET.register_namespace("r", "http://schemas.openxmlformats.org/officeDocument/2006/relationships")
ET.register_namespace("m", "http://schemas.openxmlformats.org/officeDocument/2006/math")
ET.register_namespace("w14", "http://schemas.microsoft.com/office/word/2010/wordml")

# --- HELPER FUNCTIONS ---

def strip_ns(tag: str) -> str:
    """Strip XML namespace prefix from tag name."""
    return tag.split("}", 1)[1] if "}" in tag else tag

def get_attr(el: ET.Element, name: str, default: str = "") -> str:
    """Get attribute by local name, ignoring namespace prefix."""
    for k, v in el.attrib.items():
        if strip_ns(k).lower() == name.lower():
            return v
    return default

def find_children_by_local(el: ET.Element, name: str) -> List[ET.Element]:
    """Find direct child elements matching local tag name."""
    return [c for c in el if strip_ns(c.tag).lower() == name.lower()]

def iter_by_local(el: ET.Element, name: str) -> List[ET.Element]:
    """Iterate all descendant elements matching local tag name."""
    return [c for c in el.iter() if strip_ns(c.tag).lower() == name.lower()]

def col_idx_to_letter(col_idx: int) -> str:
    """Convert 1-based column index to Excel column letter (1 -> A, 27 -> AA)."""
    result = []
    while col_idx > 0:
        col_idx, remainder = divmod(col_idx - 1, 26)
        result.append(chr(65 + remainder))
    return "".join(reversed(result))

def cell_ref_to_row_col(ref: str) -> Tuple[int, int]:
    """Convert cell reference like 'AA5' to (row=5, col=27)."""
    m = re.match(r"^([A-Z]+)([0-9]+)$", ref)
    if not m:
        return 1, 1
    col_str, row_str = m.groups()
    col = 0
    for ch in col_str:
        col = col * 26 + (ord(ch) - ord('A') + 1)
    return int(row_str), col

def clean_sheet_name(name: str) -> str:
    """Sanitize Excel sheet name (max 31 chars, no invalid characters)."""
    clean = re.sub(r"[\\/*?:\[\]]", "_", name).strip()
    return clean[:31] if clean else "Sheet1"

def escape_xml(s: Any) -> str:
    """Escape string for XML insertion."""
    if s is None:
        return ""
    text = str(s)
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
    )

# --- PARSERS & READERS ---

def read_shared_strings(zf: zipfile.ZipFile) -> List[str]:
    """Parse xl/sharedStrings.xml if present."""
    shared = []
    # Case-insensitive search for sharedStrings
    target = next((f for f in zf.namelist() if f.lower() == "xl/sharedstrings.xml"), None)
    if not target:
        return shared
    try:
        tree = ET.fromstring(zf.read(target))
        for si in iter_by_local(tree, "si"):
            texts = [t.text for t in iter_by_local(si, "t") if t.text]
            shared.append("".join(texts))
    except Exception:
        pass
    return shared

def parse_xlsx_sheets(file_path: Path) -> List[Dict[str, Any]]:
    """Inspect and extract sheets from .xlsx file."""
    sheets_data = []
    
    with zipfile.ZipFile(file_path, "r") as zf:
        shared_strings = read_shared_strings(zf)
        namelist = zf.namelist()
        
        # 1. Read workbook and rels
        wb_file = next((f for f in namelist if f.lower() == "xl/workbook.xml"), None)
        wb_rels_file = next((f for f in namelist if f.lower() == "xl/_rels/workbook.xml.rels"), None)
        
        if not wb_file:
            return sheets_data
            
        wb_tree = ET.fromstring(zf.read(wb_file))
        rel_map = {}
        if wb_rels_file:
            rels_tree = ET.fromstring(zf.read(wb_rels_file))
            for rel in iter_by_local(rels_tree, "relationship"):
                r_id = get_attr(rel, "id")
                target = get_attr(rel, "target")
                if r_id and target:
                    rel_map[r_id] = target

        for sheet in iter_by_local(wb_tree, "sheet"):
            s_name = get_attr(sheet, "name", "Sheet")
            r_id = get_attr(sheet, "id")
            target = rel_map.get(r_id, "")
            
            # Resolve target path inside zip
            target_path = None
            if target:
                clean_target = target.lstrip("/")
                candidates = [
                    f"xl/{clean_target}",
                    clean_target,
                    f"xl/worksheets/{Path(target).name}"
                ]
                for c in candidates:
                    found = next((f for f in namelist if f.lower() == c.lower()), None)
                    if found:
                        target_path = found
                        break
                        
            if not target_path:
                # Fallback: find by sheet index
                idx = len(sheets_data) + 1
                cand = f"xl/worksheets/sheet{idx}.xml"
                found = next((f for f in namelist if f.lower() == cand.lower()), None)
                if found:
                    target_path = found
                    
            if not target_path or target_path not in namelist:
                continue
                
            # Parse sheet XML
            sheet_tree = ET.fromstring(zf.read(target_path))
            rows_grid: Dict[int, Dict[int, str]] = {}
            max_row = 0
            max_col = 0
            
            for row_el in iter_by_local(sheet_tree, "row"):
                r_str = get_attr(row_el, "r")
                r_idx = int(r_str) if r_str.isdigit() else (max_row + 1)
                max_row = max(max_row, r_idx)
                if r_idx not in rows_grid:
                    rows_grid[r_idx] = {}
                    
                for c_el in find_children_by_local(row_el, "c"):
                    r_coord = get_attr(c_el, "r")
                    if r_coord:
                        curr_r, curr_c = cell_ref_to_row_col(r_coord)
                    else:
                        curr_r = r_idx
                        curr_c = len(rows_grid[r_idx]) + 1
                        
                    max_col = max(max_col, curr_c)
                    c_type = get_attr(c_el, "t").lower()
                    
                    val = ""
                    if c_type == "s":
                        v_el = next(iter(find_children_by_local(c_el, "v")), None)
                        if v_el is not None and v_el.text and v_el.text.isdigit():
                            s_idx = int(v_el.text)
                            if 0 <= s_idx < len(shared_strings):
                                val = shared_strings[s_idx]
                    elif c_type == "inlinestr":
                        is_el = next(iter(find_children_by_local(c_el, "is")), None)
                        if is_el is not None:
                            texts = [t.text for t in iter_by_local(is_el, "t") if t.text]
                            val = "".join(texts)
                    elif c_type == "b":
                        v_el = next(iter(find_children_by_local(c_el, "v")), None)
                        val = "TRUE" if v_el is not None and v_el.text == "1" else "FALSE"
                    else:
                        v_el = next(iter(find_children_by_local(c_el, "v")), None)
                        if v_el is not None and v_el.text:
                            val = v_el.text
                            
                    rows_grid[r_idx][curr_c] = val
                    
            # Convert sparse grid to dense 2D list
            dense_rows: List[List[str]] = []
            for r in range(1, max_row + 1):
                row_vals = []
                for c in range(1, max_col + 1):
                    row_vals.append(rows_grid.get(r, {}).get(c, ""))
                dense_rows.append(row_vals)
                
            sheets_data.append({
                "name": s_name,
                "row_count": max_row,
                "col_count": max_col,
                "rows": dense_rows
            })
            
    return sheets_data

def parse_docx(file_path: Path) -> Dict[str, Any]:
    """Parse .docx document into structured paragraphs and tables."""
    elements = []
    headings = []
    table_count = 0
    para_count = 0
    image_count = 0
    
    with zipfile.ZipFile(file_path, "r") as zf:
        image_count = len([f for f in zf.namelist() if f.lower().startswith("word/media/")])
        doc_file = next((f for f in zf.namelist() if f.lower() == "word/document.xml"), None)
        if not doc_file:
            return {"headings": [], "elements": [], "table_count": 0, "para_count": 0}
            
        tree = ET.fromstring(zf.read(doc_file))
        body = next(iter(iter_by_local(tree, "body")), None)
        if body is None:
            return {"headings": [], "elements": [], "table_count": 0, "para_count": 0}
            
        for child in body:
            tag = strip_ns(child.tag).lower()
            if tag == "p":
                para_count += 1
                pStyle = ""
                pPr = next(iter(find_children_by_local(child, "ppr")), None)
                if pPr is not None:
                    pStyle_el = next(iter(find_children_by_local(pPr, "pstyle")), None)
                    if pStyle_el is not None:
                        pStyle = get_attr(pStyle_el, "val")
                        
                text_runs = []
                for r in find_children_by_local(child, "r"):
                    t_el = next(iter(find_children_by_local(r, "t")), None)
                    if t_el is not None and t_el.text:
                        rPr = next(iter(find_children_by_local(r, "rpr")), None)
                        is_bold = rPr is not None and len(find_children_by_local(rPr, "b")) > 0
                        is_italic = rPr is not None and len(find_children_by_local(rPr, "i")) > 0
                        t_text = t_el.text
                        if is_bold and is_italic:
                            t_text = f"***{t_text}***"
                        elif is_bold:
                            t_text = f"**{t_text}**"
                        elif is_italic:
                            t_text = f"*{t_text}*"
                        text_runs.append(t_text)
                        
                full_text = "".join(text_runs).strip()
                if not full_text:
                    continue
                    
                style_lower = pStyle.lower()
                if "heading 1" in style_lower or "heading1" in style_lower or style_lower == "title":
                    elements.append({"type": "heading", "level": 1, "text": full_text})
                    headings.append({"level": 1, "text": full_text})
                elif "heading 2" in style_lower or "heading2" in style_lower:
                    elements.append({"type": "heading", "level": 2, "text": full_text})
                    headings.append({"level": 2, "text": full_text})
                elif "heading 3" in style_lower or "heading3" in style_lower:
                    elements.append({"type": "heading", "level": 3, "text": full_text})
                    headings.append({"level": 3, "text": full_text})
                elif "list" in style_lower or (pPr is not None and len(find_children_by_local(pPr, "numpr")) > 0):
                    elements.append({"type": "list_item", "text": full_text})
                else:
                    elements.append({"type": "paragraph", "text": full_text})
                    
            elif tag == "tbl":
                table_count += 1
                rows = []
                for tr in find_children_by_local(child, "tr"):
                    row_cells = []
                    for tc in find_children_by_local(tr, "tc"):
                        cell_texts = []
                        for p in find_children_by_local(tc, "p"):
                            p_texts = [t.text for t in iter_by_local(p, "t") if t.text]
                            if p_texts:
                                cell_texts.append("".join(p_texts))
                        row_cells.append("<br>".join(cell_texts).strip())
                    rows.append(row_cells)
                elements.append({"type": "table", "rows": rows})
                
    return {
        "headings": headings,
        "elements": elements,
        "table_count": table_count,
        "para_count": para_count,
        "image_count": image_count
    }

def parse_pptx(file_path: Path) -> Dict[str, Any]:
    """Parse .pptx document into slides and bullet points."""
    slides = []
    
    with zipfile.ZipFile(file_path, "r") as zf:
        slide_files = [f for f in zf.namelist() if f.lower().startswith("ppt/slides/slide") and f.lower().endswith(".xml")]
        slide_files.sort(key=lambda s: int(re.search(r"\d+", s).group()) if re.search(r"\d+", s) else 0)
        
        for idx, s_path in enumerate(slide_files, start=1):
            tree = ET.fromstring(zf.read(s_path))
            paras = []
            for p in iter_by_local(tree, "p"):
                texts = [t.text for t in iter_by_local(p, "t") if t.text]
                if texts:
                    paras.append("".join(texts).strip())
            slides.append({"slide_number": idx, "paragraphs": paras})
            
    return {
        "slide_count": len(slides),
        "slides": slides
    }

def iter_pdf_streams(raw: bytes):
    """Linear O(N) PDF stream parser avoiding catastrophic regex backtracking."""
    pos = 0
    raw_len = len(raw)
    while pos < raw_len:
        idx = raw.find(b"stream", pos)
        if idx == -1:
            break
        # Guard: ensure 'stream' is not part of 'endstream'
        if idx >= 3 and raw[idx-3:idx] == b"end":
            pos = idx + 6
            continue
        # Boundary check before 'stream': whitespace, newline, or dictionary delimiter '>'
        if idx > 0 and raw[idx-1:idx] not in b" \t\r\n>":
            pos = idx + 6
            continue
            
        start = idx + 6
        if start < raw_len and raw[start:start+2] == b"\r\n":
            start += 2
        elif start < raw_len and raw[start:start+1] in (b"\n", b"\r"):
            start += 1
            
        end = raw.find(b"endstream", start)
        if end == -1:
            break
            
        stream_bytes = raw[start:end].rstrip(b"\r\n")
        
        # Check dictionary snippet before stream
        header_start = max(0, idx - 250)
        header_snippet = raw[header_start:idx]
        is_image = b"/Subtype /Image" in header_snippet or b"/Subtype/Image" in header_snippet
        
        yield is_image, stream_bytes
        pos = end + 9

def read_pdf(file_path: Path) -> Dict[str, Any]:
    """Extract text from PDF using macOS native PDFKit via JXA, with fallback."""
    # Method 1: macOS JXA PDFKit
    jxa_script = f"""
    ObjC.import('PDFKit');
    ObjC.import('Foundation');
    var url = $.NSURL.fileURLWithPath('{str(file_path.resolve())}');
    var doc = $.PDFDocument.alloc.initWithURL(url);
    if (!doc || doc.isEqual(null)) {{
        JSON.stringify({{page_count: 0, pages: []}});
    }} else {{
        var count = doc.pageCount;
        var pList = [];
        for (var i = 0; i < count; i++) {{
            var page = doc.pageAtIndex(i);
            pList.push(page.string.js || '');
        }}
        JSON.stringify({{page_count: count, pages: pList}});
    }}
    """
    try:
        proc = subprocess.run(["osascript", "-l", "JavaScript", "-e", jxa_script], capture_output=True, text=True, timeout=10)
        output_str = proc.stdout.strip() or proc.stderr.strip()
        if output_str:
            data = json.loads(output_str)
            if "pages" in data and int(data.get("page_count", 0)) > 0:
                data["page_count"] = int(data["page_count"])
                return data
    except Exception:
        pass
        
    # Method 2: Pure Python basic stream text extractor
    try:
        import zlib
        content = file_path.read_bytes()
        # Count pages via /Type /Page
        page_matches = [m for m in re.finditer(rb'/Type\s*/Page\b', content) 
                        if not content[m.start():m.start()+15].startswith(b'/Type /Pages')]
        detected_pages = len(page_matches)
        
        extracted = []
        for is_image, s in iter_pdf_streams(content):
            if is_image:
                continue
            decompressed = None
            try:
                decompressed = zlib.decompress(s).decode("latin1", errors="ignore")
            except Exception:
                decompressed = s.decode("latin1", errors="ignore")
            if decompressed:
                matches = re.findall(r"\((.*?)\)\s*Tj", decompressed)
                if matches:
                    extracted.append(" ".join(matches))
                    
        page_count = max(detected_pages, 1 if extracted else 0)
        if extracted or page_count > 0:
            return {"page_count": page_count, "pages": ["\n".join(extracted)]}
    except Exception:
        pass
        
    return {"page_count": 0, "pages": []}

def read_doc_or_rtf_mac(file_path: Path) -> str:
    """Read .doc or .rtf using macOS /usr/bin/textutil."""
    if os.path.exists("/usr/bin/textutil"):
        try:
            proc = subprocess.run(["/usr/bin/textutil", "-convert", "txt", str(file_path), "-stdout"], capture_output=True, text=True, check=True)
            return proc.stdout.strip()
        except Exception:
            pass
    return ""

def format_markdown_table(rows: List[List[str]]) -> str:
    """Format a 2D list into a clean Markdown table."""
    if not rows:
        return ""
    clean_rows = []
    for r in rows:
        if any(str(c).strip() for c in r):
            clean_rows.append(r)
    if not clean_rows:
        return ""
        
    header = clean_rows[0]
    num_cols = len(header)
    col_widths = [len(str(c)) for c in header]
    
    for r in clean_rows[1:]:
        for i in range(num_cols):
            val = r[i] if i < len(r) else ""
            col_widths[i] = max(col_widths[i], len(str(val)))
            
    col_widths = [max(w, 3) for w in col_widths]
    
    lines = []
    # Header row
    h_str = "| " + " | ".join(str(header[i]).ljust(col_widths[i]) if i < len(header) else "".ljust(col_widths[i]) for i in range(num_cols)) + " |"
    sep_str = "| " + " | ".join("-" * col_widths[i] for i in range(num_cols)) + " |"
    lines.append(h_str)
    lines.append(sep_str)
    
    # Data rows
    for r in clean_rows[1:]:
        r_str = "| " + " | ".join(str(r[i]).replace("\n", " ").ljust(col_widths[i]) if i < len(r) else "".ljust(col_widths[i]) for i in range(num_cols)) + " |"
        lines.append(r_str)
        
    return "\n".join(lines)

# --- WRITERS (GENERATORS) ---

def parse_markdown_tables_with_headings(md_text: str) -> List[Dict[str, Any]]:
    """Parse Markdown text to extract tables associated with their nearest preceding heading."""
    lines = md_text.splitlines()
    sheets = []
    current_heading = "Sheet1"
    table_lines = []
    table_count = 0
    
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            h_text = stripped.lstrip("#").strip()
            h_text = re.sub(r"^Sheet\s*:\s*", "", h_text, flags=re.IGNORECASE)
            current_heading = clean_sheet_name(h_text)
            continue
            
        if stripped.startswith("|") and stripped.endswith("|"):
            table_lines.append(stripped)
        else:
            if table_lines:
                rows = []
                for t_line in table_lines:
                    inner = t_line.strip("|")
                    cells = [c.strip() for c in inner.split("|")]
                    if all(re.match(r"^:?-+:?$", c) for c in cells):
                        continue
                    rows.append(cells)
                if rows:
                    table_count += 1
                    s_name = current_heading if current_heading != "Sheet1" or table_count == 1 else f"Sheet{table_count}"
                    sheets.append({"name": s_name, "rows": rows})
                table_lines = []
                
    if table_lines:
        rows = []
        for t_line in table_lines:
            inner = t_line.strip("|")
            cells = [c.strip() for c in inner.split("|")]
            if all(re.match(r"^:?-+:?$", c) for c in cells):
                continue
            rows.append(cells)
        if rows:
            table_count += 1
            s_name = current_heading if current_heading != "Sheet1" or table_count == 1 else f"Sheet{table_count}"
            sheets.append({"name": s_name, "rows": rows})
            
    return sheets

def write_xlsx(sheets: List[Dict[str, Any]], output_path: Path):
    """Generate a 100% valid, styled OpenXML .xlsx spreadsheet."""
    if not sheets:
        sheets = [{"name": "Sheet1", "rows": [["No Data"]]}]
        
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        # 1. [Content_Types].xml
        ct_overrides = []
        for idx in range(1, len(sheets) + 1):
            ct_overrides.append(f'<Override PartName="/xl/worksheets/sheet{idx}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>')
        ct_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
  {"".join(ct_overrides)}
</Types>"""
        z.writestr("[Content_Types].xml", ct_xml.strip())
        
        # 2. _rels/.rels
        z.writestr("_rels/.rels", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>""".strip())

        # 3. xl/_rels/workbook.xml.rels
        wb_rels = []
        for idx in range(1, len(sheets) + 1):
            wb_rels.append(f'<Relationship Id="rId{idx}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{idx}.xml"/>')
        styles_rid = len(sheets) + 1
        wb_rels.append(f'<Relationship Id="rId{styles_rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>')
        
        z.writestr("xl/_rels/workbook.xml.rels", f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  {"".join(wb_rels)}
</Relationships>""".strip())

        # 4. xl/workbook.xml
        sheet_tags = []
        for idx, s in enumerate(sheets, start=1):
            s_name = escape_xml(clean_sheet_name(s.get("name", f"Sheet{idx}")))
            sheet_tags.append(f'<sheet name="{s_name}" sheetId="{idx}" r:id="rId{idx}"/>')
            
        z.writestr("xl/workbook.xml", f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    {"".join(sheet_tags)}
  </sheets>
</workbook>""".strip())

        # 5. xl/styles.xml (Professional Corporate Theme: #1B4D3E Dark Green)
        styles_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="2">
    <font><sz val="11"/><color theme="1"/><name val="Calibri"/><family val="2"/></font>
    <font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Calibri"/><family val="2"/></font>
  </fonts>
  <fills count="4">
    <fill><patternFill patternType="none"/></fill>
    <fill><patternFill patternType="gray125"/></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FF1B4D3E"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFF4F8F6"/><bgColor indexed="64"/></patternFill></fill>
  </fills>
  <borders count="2">
    <border><left/><right/><top/><bottom/><diagonal/></border>
    <border>
      <left style="thin"><color rgb="FFD9D9D9"/></left>
      <right style="thin"><color rgb="FFD9D9D9"/></right>
      <top style="thin"><color rgb="FFD9D9D9"/></top>
      <bottom style="thin"><color rgb="FFD9D9D9"/></bottom>
      <diagonal/>
    </border>
  </borders>
  <cellStyleXfs count="1">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0"/>
  </cellStyleXfs>
  <cellXfs count="5">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0"><alignment vertical="center"/></xf>
    <xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center"/></xf>
    <xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1" applyAlignment="1"><alignment horizontal="left" vertical="center"/></xf>
    <xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1" applyAlignment="1"><alignment horizontal="right" vertical="center"/></xf>
    <xf numFmtId="0" fontId="0" fillId="3" borderId="1" xfId="0" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="left" vertical="center"/></xf>
  </cellXfs>
</styleSheet>"""
        z.writestr("xl/styles.xml", styles_xml.strip())

        # 6. Worksheets
        for idx, s in enumerate(sheets, start=1):
            rows = s.get("rows", [])
            max_cols = max(len(r) for r in rows) if rows else 1
            
            # Auto-calculate column widths
            col_widths = [10] * max_cols
            for r in rows:
                for c_i, val in enumerate(r):
                    col_widths[c_i] = max(col_widths[c_i], len(str(val)) + 3)
            col_widths = [min(w, 60) for w in col_widths]
            
            cols_xml = []
            for c_i, w in enumerate(col_widths, start=1):
                cols_xml.append(f'<col min="{c_i}" max="{c_i}" width="{w}" customWidth="1"/>')
                
            rows_xml = []
            for r_i, r in enumerate(rows, start=1):
                is_header = (r_i == 1)
                is_zebra = (r_i % 2 == 0) and not is_header
                c_xml = []
                for c_i, val in enumerate(r, start=1):
                    cell_ref = f"{col_idx_to_letter(c_i)}{r_i}"
                    val_str = str(val).strip()
                    
                    if is_header:
                        c_xml.append(f'<c r="{cell_ref}" s="1" t="inlineStr"><is><t>{escape_xml(val_str)}</t></is></c>')
                    else:
                        is_num = False
                        if re.match(r"^-?\d+(\.\d+)?$", val_str) and not (val_str.startswith("0") and len(val_str) > 1 and not val_str.startswith("0.")):
                            is_num = True
                            
                        if is_num:
                            c_xml.append(f'<c r="{cell_ref}" s="3"><v>{val_str}</v></c>')
                        else:
                            style_id = "4" if is_zebra else "2"
                            c_xml.append(f'<c r="{cell_ref}" s="{style_id}" t="inlineStr"><is><t>{escape_xml(val_str)}</t></is></c>')
                            
                rows_xml.append(f'<row r="{r_i}">{"".join(c_xml)}</row>')
                
            sheet_content = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetViews>
    <sheetView tabSelected="{1 if idx == 1 else 0}" workbookViewId="0">
      <pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>
    </sheetView>
  </sheetViews>
  <cols>
    {"".join(cols_xml)}
  </cols>
  <sheetData>
    {"".join(rows_xml)}
  </sheetData>
</worksheet>"""
            z.writestr(f"xl/worksheets/sheet{idx}.xml", sheet_content.strip())
            
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(buf.getvalue())


def write_docx(md_text: str, output_path: Path, title: Optional[str] = None, base_dir: Optional[Path] = None):
    """Generate a 100% valid OpenXML .docx with corporate #004D40 styling and embedded images."""
    lines = md_text.splitlines()
    body_elements_xml = []
    image_records = []
    image_path_map = {}
    repo_root = Path(__file__).resolve().parents[4]

    def resolve_image(path_str: str) -> Optional[Path]:
        p_str = path_str.strip().strip("'\"")
        p = Path(p_str)
        if p.is_file():
            return p.resolve()
        if base_dir and (base_dir / p).is_file():
            return (base_dir / p).resolve()
        if (Path.cwd() / p).is_file():
            return (Path.cwd() / p).resolve()
        if (repo_root / p).is_file():
            return (repo_root / p).resolve()
        return None

    def get_image_info(img_path: Path):
        key = str(img_path.resolve())
        if key in image_path_map:
            return image_path_map[key]
        
        img_bytes = img_path.read_bytes()
        ext = img_path.suffix.lower()
        if not ext:
            ext = ".png"
        num = len(image_records) + 1
        rId = f"rIdImg{num}"
        filename = f"image{num}{ext}"
        
        w, h = 1280, 800
        if ext == ".png" and len(img_bytes) >= 24 and img_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
            try:
                w, h = struct.unpack(">II", img_bytes[16:24])
            except Exception:
                pass
        elif ext in (".jpg", ".jpeg"):
            try:
                idx = 2
                while idx < len(img_bytes):
                    if img_bytes[idx] != 0xFF:
                        idx += 1
                        continue
                    marker = img_bytes[idx+1]
                    if marker in (0xC0, 0xC1, 0xC2, 0xC3):
                        h, w = struct.unpack(">HH", img_bytes[idx+5:idx+9])
                        break
                    else:
                        length = struct.unpack(">H", img_bytes[idx+2:idx+4])[0]
                        idx += 2 + length
            except Exception:
                pass
                
        info = {
            "rId": rId,
            "num": num,
            "filename": filename,
            "bytes": img_bytes,
            "ext": ext,
            "w": w,
            "h": h
        }
        image_records.append(info)
        image_path_map[key] = info
        return info

    def build_drawing_xml(img_info: Dict[str, Any], caption: str = "", in_table: bool = False) -> str:
        rId = img_info["rId"]
        img_num = img_info["num"]
        w = img_info["w"]
        h = img_info["h"]
        
        max_w = 4600000 if in_table else 4900000
        aspect = (h / w) if w > 0 else 0.625
        cx = max_w
        cy = int(cx * aspect)
        if cy > 5200000:
            scale = 5200000 / cy
            cy = 5200000
            cx = int(cx * scale)
            
        return f"""<w:drawing>
          <wp:inline distT="0" distB="0" distL="0" distR="0">
            <wp:extent cx="{cx}" cy="{cy}"/>
            <wp:effectExtent l="0" t="0" r="0" b="0"/>
            <wp:docPr id="{img_num}" name="Picture {img_num}" descr="{escape_xml(caption)}"/>
            <wp:cNvGraphicFramePr>
              <a:graphicFrameLocks xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" noChangeAspect="1"/>
            </wp:cNvGraphicFramePr>
            <a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
              <a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">
                <pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">
                  <pic:nvPicPr>
                    <pic:cNvPr id="{img_num}" name="Picture {img_num}"/>
                    <pic:cNvPicPr/>
                  </pic:nvPicPr>
                  <pic:blipFill>
                    <a:blip r:embed="{rId}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"/>
                    <a:stretch><a:fillRect/></a:stretch>
                  </pic:blipFill>
                  <pic:spPr>
                    <a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>
                    <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
                  </pic:spPr>
                </pic:pic>
              </a:graphicData>
            </a:graphic>
          </wp:inline>
        </w:drawing>"""

    def render_runs(text: str, is_header: bool = False, is_label: bool = False) -> str:
        tokens = re.split(r"(\*\*.*?\*\*|\*[^*]+?\*|`[^`]+?`)", text)
        runs_xml = []
        for t in tokens:
            if not t:
                continue
            if t.startswith("**") and t.endswith("**"):
                inner = t[2:-2]
                color = "FFFFFF" if is_header else ("004D40" if inner == "PASSED" else "000000")
                runs_xml.append(f'<w:r><w:rPr><w:b/><w:sz w:val="20"/><w:color w:val="{color}"/></w:rPr><w:t xml:space="preserve">{escape_xml(inner)}</w:t></w:r>')
            elif t.startswith("*") and t.endswith("*"):
                inner = t[1:-1]
                color = "FFFFFF" if is_header else "555555"
                runs_xml.append(f'<w:r><w:rPr><w:i/><w:sz w:val="20"/><w:color w:val="{color}"/></w:rPr><w:t xml:space="preserve">{escape_xml(inner)}</w:t></w:r>')
            elif t.startswith("`") and t.endswith("`"):
                inner = t[1:-1]
                runs_xml.append(f'<w:r><w:rPr><w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/><w:sz w:val="19"/><w:color w:val="A31515"/></w:rPr><w:t xml:space="preserve">{escape_xml(inner)}</w:t></w:r>')
            else:
                color = "FFFFFF" if is_header else ("004D40" if (t.strip() == "PASSED") else "333333")
                bold = "<w:b/>" if (is_header or is_label or t.strip() == "PASSED") else ""
                runs_xml.append(f'<w:r><w:rPr>{bold}<w:sz w:val="20"/><w:color w:val="{color}"/></w:rPr><w:t xml:space="preserve">{escape_xml(t)}</w:t></w:r>')
        return "".join(runs_xml)

    def render_cell_paragraphs(cell_text: str, is_header: bool = False, is_label: bool = False, align: str = "left") -> str:
        lines_in_cell = re.split(r"<br\s*/?>|\n", cell_text)
        p_xmls = []
        for line in lines_in_cell:
            line_str = line.strip()
            if not line_str:
                continue
                
            img_matches = list(re.finditer(r"!\[([^\]]*)\]\(([^)]+)\)", line_str))
            if img_matches:
                last_pos = 0
                for m in img_matches:
                    before_text = line_str[last_pos:m.start()].strip()
                    if before_text:
                        p_xmls.append(f'<w:p><w:pPr><w:jc w:val="{align}"/><w:spacing w:before="40" w:after="40"/></w:pPr>{render_runs(before_text, is_header, is_label)}</w:p>')
                    
                    caption = m.group(1).strip()
                    img_path_str = m.group(2).strip()
                    resolved = resolve_image(img_path_str)
                    if resolved:
                        info = get_image_info(resolved)
                        drawing = build_drawing_xml(info, caption, in_table=True)
                        p_xmls.append(f'<w:p><w:pPr><w:jc w:val="center"/><w:spacing w:before="60" w:after="40"/></w:pPr><w:r>{drawing}</w:r></w:p>')
                        if caption:
                            p_xmls.append(f'<w:p><w:pPr><w:jc w:val="center"/><w:spacing w:before="0" w:after="60"/></w:pPr><w:r><w:rPr><w:i/><w:sz w:val="18"/><w:color w:val="555555"/></w:rPr><w:t xml:space="preserve">{escape_xml(caption)}</w:t></w:r></w:p>')
                    else:
                        p_xmls.append(f'<w:p><w:pPr><w:jc w:val="{align}"/><w:spacing w:before="40" w:after="40"/></w:pPr><w:r><w:rPr><w:i/><w:color w:val="999999"/></w:rPr><w:t>[Image not found: {escape_xml(img_path_str)}]</w:t></w:r></w:p>')
                    last_pos = m.end()
                    
                after_text = line_str[last_pos:].strip()
                if after_text:
                    p_xmls.append(f'<w:p><w:pPr><w:jc w:val="{align}"/><w:spacing w:before="40" w:after="40"/></w:pPr>{render_runs(after_text, is_header, is_label)}</w:p>')
            else:
                jc = "center" if (is_header and align == "center") or line_str.startswith("**7 Test") or line_str in ("PASSED", "PASS") else align
                p_xmls.append(f'<w:p><w:pPr><w:jc w:val="{jc}"/><w:spacing w:before="40" w:after="40"/></w:pPr>{render_runs(line_str, is_header, is_label)}</w:p>')
                
        if not p_xmls:
            p_xmls.append(f'<w:p><w:pPr><w:spacing w:before="40" w:after="40"/></w:pPr></w:p>')
        return "".join(p_xmls)

    if title:
        body_elements_xml.append(f"""
        <w:p>
          <w:pPr><w:pStyle w:val="Heading1"/><w:spacing w:before="360" w:after="180"/></w:pPr>
          <w:r><w:rPr><w:b/><w:sz w:val="38"/><w:color w:val="004D40"/></w:rPr><w:t>{escape_xml(title)}</w:t></w:r>
        </w:p>""")
        
    table_lines = []
    
    def flush_table():
        if not table_lines:
            return ""
        rows = []
        for t_line in table_lines:
            inner = t_line.strip("|")
            cells = [c.strip() for c in inner.split("|")]
            if all(re.match(r"^:?-+:?$", c) for c in cells):
                continue
            rows.append(cells)
            
        if not rows:
            return ""
            
        tr_xml = []
        is_two_col = (len(rows[0]) == 2) if rows else False
        num_cols = max(len(r) for r in rows) if rows else 1
        
        for r_i, r in enumerate(rows):
            is_banner_row = (r_i == 0 and (len(r) == 1 or (len(r) == 2 and not r[1].strip())))
            is_header = (r_i == 0) or is_banner_row
            is_even = (r_i % 2 == 0)
            
            # If row 0 was banner and row 1 looks like column headers
            if r_i == 1 and rows[0] and (len(rows[0]) <= 2) and len(r) > 2:
                is_sub_header = True
            else:
                is_sub_header = False
                
            tc_xml = []
            if is_banner_row:
                val = r[0].strip()
                cell_p = render_cell_paragraphs(val, is_header=True, align="center")
                tc_xml.append(f"""
                <w:tc>
                  <w:tcPr>
                    <w:gridSpan w:val="{num_cols}"/>
                    <w:shd w:val="clear" w:color="auto" w:fill="004D40"/>
                  </w:tcPr>
                  {cell_p}
                </w:tc>""")
            else:
                for c_i, val in enumerate(r):
                    is_cell_header = is_header or is_sub_header
                    is_label = (is_two_col and c_i == 0 and not is_cell_header)
                    
                    if is_cell_header:
                        fill = "004D40" if is_header else "1B4D3E"
                    elif is_label:
                        fill = "F4F8F6"
                    else:
                        fill = "F9FBF9" if is_even else "FFFFFF"
                        
                    cell_align = "center" if (is_cell_header or val.strip() in ("PASSED", "PASS", "FAILED")) else "left"
                    cell_p = render_cell_paragraphs(val, is_header=is_cell_header, is_label=is_label, align=cell_align)
                    
                    tc_xml.append(f"""
                    <w:tc>
                      <w:tcPr><w:shd w:val="clear" w:color="auto" w:fill="{fill}"/></w:tcPr>
                      {cell_p}
                    </w:tc>""")
                    
            tr_header = "<w:tblHeader/>" if is_header else ""
            tr_xml.append(f"""<w:tr><w:trPr>{tr_header}<w:cantSplit/></w:trPr>{"".join(tc_xml)}</w:tr>""")
            
        tbl_markup = f"""
        <w:tbl>
          <w:tblPr>
            <w:tblW w:w="5000" w:type="pct"/>
            <w:jc w:val="center"/>
            <w:tblBorders>
              <w:top w:val="single" w:sz="8" w:space="0" w:color="004D40"/>
              <w:left w:val="single" w:sz="6" w:space="0" w:color="004D40"/>
              <w:bottom w:val="single" w:sz="10" w:space="0" w:color="004D40"/>
              <w:right w:val="single" w:sz="6" w:space="0" w:color="004D40"/>
              <w:insideH w:val="single" w:sz="4" w:space="0" w:color="CCCCCC"/>
              <w:insideV w:val="single" w:sz="4" w:space="0" w:color="E0E0E0"/>
            </w:tblBorders>
            <w:tblCellMar>
              <w:top w:w="120" w:type="dxa"/>
              <w:bottom w:w="120" w:type="dxa"/>
              <w:left w:w="160" w:type="dxa"/>
              <w:right w:w="160" w:type="dxa"/>
            </w:tblCellMar>
          </w:tblPr>
          {"".join(tr_xml)}
        </w:tbl>"""
        return tbl_markup

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            table_lines.append(stripped)
            continue
        else:
            if table_lines:
                tbl = flush_table()
                if tbl:
                    body_elements_xml.append(tbl)
                table_lines = []
                
        if not stripped:
            continue
            
        if stripped in ("---", "***", "___", "<pagebreak/>", "\\pagebreak"):
            body_elements_xml.append("""
            <w:p>
              <w:pPr><w:spacing w:before="0" w:after="0"/></w:pPr>
              <w:r><w:br w:type="page"/></w:r>
            </w:p>""")
            continue
            
        img_match = re.match(r"^!\[([^\]]*)\]\(([^)]+)\)$", stripped)
        if img_match:
            caption = img_match.group(1).strip()
            img_path_str = img_match.group(2).strip()
            resolved = resolve_image(img_path_str)
            if resolved:
                info = get_image_info(resolved)
                drawing = build_drawing_xml(info, caption, in_table=False)
                body_elements_xml.append(f"""
                <w:p>
                  <w:pPr><w:jc w:val="center"/><w:spacing w:before="120" w:after="60"/></w:pPr>
                  <w:r>{drawing}</w:r>
                </w:p>""")
                if caption:
                    body_elements_xml.append(f"""
                    <w:p>
                      <w:pPr><w:jc w:val="center"/><w:spacing w:before="0" w:after="120"/></w:pPr>
                      <w:r><w:rPr><w:i/><w:sz w:val="18"/><w:color w:val="555555"/></w:rPr><w:t xml:space="preserve">{escape_xml(caption)}</w:t></w:r>
                    </w:p>""")
            continue
            
        if stripped.startswith("# "):
            h_text = stripped[2:].strip()
            body_elements_xml.append(f"""
            <w:p>
              <w:pPr><w:pStyle w:val="Heading1"/><w:spacing w:before="280" w:after="120"/></w:pPr>
              <w:r><w:rPr><w:b/><w:sz w:val="32"/><w:color w:val="004D40"/></w:rPr><w:t>{escape_xml(h_text)}</w:t></w:r>
            </w:p>""")
        elif stripped.startswith("## "):
            h_text = stripped[3:].strip()
            body_elements_xml.append(f"""
            <w:p>
              <w:pPr><w:pStyle w:val="Heading2"/><w:spacing w:before="220" w:after="100"/></w:pPr>
              <w:r><w:rPr><w:b/><w:sz w:val="26"/><w:color w:val="004D40"/></w:rPr><w:t>{escape_xml(h_text)}</w:t></w:r>
            </w:p>""")
        elif stripped.startswith("### "):
            h_text = stripped[4:].strip()
            body_elements_xml.append(f"""
            <w:p>
              <w:pPr><w:pStyle w:val="Heading3"/><w:spacing w:before="160" w:after="80"/></w:pPr>
              <w:r><w:rPr><w:b/><w:sz w:val="22"/><w:color w:val="2F4F4F"/></w:rPr><w:t>{escape_xml(h_text)}</w:t></w:r>
            </w:p>""")
        elif stripped.startswith("> "):
            quote_text = stripped[2:].strip()
            body_elements_xml.append(f"""
            <w:p>
              <w:pPr><w:pBdr><w:left w:val="single" w:sz="18" w:space="10" w:color="004D40"/></w:pBdr><w:ind w:left="320"/><w:spacing w:before="80" w:after="80"/></w:pPr>
              <w:r><w:rPr><w:i/><w:sz w:val="20"/><w:color w:val="444444"/></w:rPr><w:t>{escape_xml(quote_text)}</w:t></w:r>
            </w:p>""")
        elif stripped.startswith("- ") or stripped.startswith("* "):
            item_text = stripped[2:].strip()
            body_elements_xml.append(f"""
            <w:p>
              <w:pPr><w:ind w:left="360"/><w:spacing w:after="60"/></w:pPr>
              <w:r><w:rPr><w:sz w:val="20"/><w:color w:val="004D40"/></w:rPr><w:t>• </w:t></w:r>
              {render_runs(item_text)}
            </w:p>""")
        else:
            body_elements_xml.append(f"""
            <w:p>
              <w:pPr><w:spacing w:before="60" w:after="100"/></w:pPr>
              {render_runs(stripped)}
            </w:p>""")
            
    if table_lines:
        tbl = flush_table()
        if tbl:
            body_elements_xml.append(tbl)
            
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="png" ContentType="image/png"/>
  <Default Extension="jpg" ContentType="image/jpeg"/>
  <Default Extension="jpeg" ContentType="image/jpeg"/>
  <Default Extension="gif" ContentType="image/gif"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>""".strip())

        z.writestr("_rels/.rels", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>""".strip())

        rel_items = [
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
        ]
        for img in image_records:
            rel_items.append(
                f'<Relationship Id="{img["rId"]}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/{img["filename"]}"/>'
            )
        doc_rels_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  {"".join(rel_items)}
</Relationships>"""
        z.writestr("word/_rels/document.xml.rels", doc_rels_xml.strip())

        for img in image_records:
            z.writestr(f"word/media/{img['filename']}", img["bytes"])

        styles_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:docDefaults>
    <w:rPrDefault><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/><w:sz w:val="22"/><w:color w:val="333333"/></w:rPr></w:rPrDefault>
    <w:pPrDefault><w:pPr><w:spacing w:line="276" w:lineRule="auto"/></w:pPr></w:pPrDefault>
  </w:docDefaults>
  <w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:rPr><w:b/><w:sz w:val="32"/><w:color w:val="004D40"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:rPr><w:b/><w:sz w:val="26"/><w:color w:val="004D40"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Heading3"><w:name w:val="heading 3"/><w:rPr><w:b/><w:sz w:val="22"/><w:color w:val="2F4F4F"/></w:rPr></w:style>
</w:styles>"""
        z.writestr("word/styles.xml", styles_xml.strip())

        doc_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
            xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
            xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
            xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">
  <w:body>
    {"".join(body_elements_xml)}
    <w:sectPr>
      <w:pgSz w:w="11906" w:h="16838"/>
      <w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/>
    </w:sectPr>
  </w:body>
</w:document>"""
        z.writestr("word/document.xml", doc_xml.strip())
        
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(buf.getvalue())

def _load_simple_yaml(filepath: Path) -> Dict[str, Any]:
    """Load simple YAML config using PyYAML if available, else minimal stdlib parser."""
    if not filepath.is_file():
        return {}
    try:
        import yaml  # type: ignore
        with open(filepath, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except ImportError:
        repo_root = Path(__file__).resolve().parents[4]
        team_orch = repo_root / "cmd" / "team-orch"
        if team_orch.is_file():
            import importlib.machinery
            import importlib.util
            loader = importlib.machinery.SourceFileLoader("team_orch_yaml", str(team_orch))
            spec = importlib.util.spec_from_loader("team_orch_yaml", loader)
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                return mod.load_yaml(filepath) or {}
        return {}

def resolve_domain_info(domain_id: Optional[str] = None) -> tuple:
    """Resolve active Specific Domain ID, directory, and parsed domain.yaml manifest."""
    eff_id = (domain_id or os.environ.get("TEAM_ORCH_DOMAIN", "")).strip().lower()
    if not eff_id:
        active_file = Path.home() / ".gemini" / "team-orch" / "active-domain.yaml"
        if active_file.is_file():
            eff_id = str(_load_simple_yaml(active_file).get("active_domain", "base")).strip().lower()
    if not eff_id or eff_id in ("base", "none"):
        return "base", None, {}

    eff_id = re.sub(r"[^a-zA-Z0-9_-]", "-", eff_id)
    repo_root = Path(__file__).resolve().parents[4]
    candidates = [
        Path.cwd() / ".agents" / "domains" / eff_id,
        repo_root / ".agents" / "domains" / eff_id,
        Path.home() / ".gemini" / "team-orch" / "domains" / eff_id,
    ]
    for d_dir in candidates:
        m_file = d_dir / "domain.yaml"
        if m_file.is_file():
            return eff_id, d_dir, _load_simple_yaml(m_file)
    return eff_id, None, {}

def find_qad_template(custom_path: Optional[str] = None, domain_id: Optional[str] = None) -> Path:
    """Locate official QAD base template (.docx) via --template or active Specific Domain Pack."""
    if custom_path:
        p = Path(custom_path)
        if p.is_file():
            return p.resolve()
        raise FileNotFoundError(f"Specified template file not found: {custom_path}")

    eff_id, d_dir, d_manifest = resolve_domain_info(domain_id)
    if d_dir and isinstance(d_manifest, dict):
        tmpls = d_manifest.get("templates") or {}
        qad_rel = tmpls.get("qad_docx") if isinstance(tmpls, dict) else None
        if qad_rel:
            cand = (d_dir / qad_rel).resolve()
            if cand.is_file():
                return cand

    raise FileNotFoundError(
        f"No QAD template (.docx) found for active domain '{eff_id}'. "
        "Provide '--template <path/to/template.docx>' or activate a Specific Domain Pack with 'team-orch domain use <domain_id>'."
    )

def _load_qad_payload(data_path: Optional[Path]) -> Dict[str, Any]:
    """Load structured QAD specification payload from JSON or Markdown metadata."""
    if not data_path or not data_path.is_file():
        return {}
    if data_path.suffix.lower() == ".json":
        return json.loads(data_path.read_text(encoding="utf-8"))

    # Minimal Markdown fallback extraction
    text = data_path.read_text(encoding="utf-8")
    payload: Dict[str, Any] = {}
    m_title = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    if m_title:
        payload["title"] = m_title.group(1).strip()
    return payload

def populate_qad_template(template_path: Path, output_path: Path, data_path: Optional[Path] = None, base_dir: Optional[Path] = None, domain_id: Optional[str] = None):
    """Populate a structured QAD Word template (.docx) using data_path + active Specific Domain Pack."""
    W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    WP_NS = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
    A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
    PIC_NS = "http://schemas.openxmlformats.org/drawingml/2006/picture"
    R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

    _, _, d_manifest = resolve_domain_info(domain_id)
    d_org = (d_manifest.get("organization") or {}) if isinstance(d_manifest, dict) else {}
    d_officials = (d_manifest.get("officials") or []) if isinstance(d_manifest, dict) else []

    payload = _load_qad_payload(data_path)
    brand_hex = str(payload.get("brand_color") or d_org.get("brand_color") or "1B4D3E").lstrip("#").upper()
    org_name = str(payload.get("organization") or d_org.get("name") or "Organization Name")
    division_name = str(payload.get("division") or d_org.get("division") or "Engineering & QA Division")
    doc_title = str(payload.get("title") or "[TESTPLAN] Quality Assurance Document")
    project_no = str(payload.get("project_no") or "QAD-001")
    doc_date = str(payload.get("date") or datetime.now().strftime("%d %b %Y"))
    product_name = str(payload.get("product") or "Target Application")
    doc_version = str(payload.get("version") or "1.0")
    test_plan_link = str(payload.get("test_plan_link") or "-")
    background_text = str(payload.get("background") or "Ringkasan latar belakang fitur dan tujuan pengujian.")
    expected_overview = str(payload.get("expected_overview") or "Seluruh skenario pengujian memenuhi kriteria penerimaan.")
    notes_text = str(payload.get("notes") or "Catatan hasil pengujian dan observasi lingkungan.")
    result_banner = str(payload.get("result_summary") or "PASSED")

    def make_para(text: str, bold: bool = False, italic: bool = False, color: str = "000000", sz: int = 24, font: str = "Roboto", jc: str = "left", before: int = 0, after: int = 40):
        p = ET.Element(f"{{{W_NS}}}p")
        pPr = ET.SubElement(p, f"{{{W_NS}}}pPr")
        spacing = ET.SubElement(pPr, f"{{{W_NS}}}spacing")
        spacing.set(f"{{{W_NS}}}line", "240")
        spacing.set(f"{{{W_NS}}}lineRule", "auto")
        spacing.set(f"{{{W_NS}}}after", str(after))
        spacing.set(f"{{{W_NS}}}before", str(before))
        if jc != "left":
            jc_el = ET.SubElement(pPr, f"{{{W_NS}}}jc")
            jc_el.set(f"{{{W_NS}}}val", jc)

        rPr = ET.SubElement(pPr, f"{{{W_NS}}}rPr")
        rFonts = ET.SubElement(rPr, f"{{{W_NS}}}rFonts")
        rFonts.set(f"{{{W_NS}}}ascii", font)
        rFonts.set(f"{{{W_NS}}}hAnsi", font)
        rFonts.set(f"{{{W_NS}}}cs", font)
        if bold:
            b_el = ET.SubElement(rPr, f"{{{W_NS}}}b")
            b_el.set(f"{{{W_NS}}}val", "1")
        if italic:
            i_el = ET.SubElement(rPr, f"{{{W_NS}}}i")
            i_el.set(f"{{{W_NS}}}val", "1")
        if color:
            c_el = ET.SubElement(rPr, f"{{{W_NS}}}color")
            c_el.set(f"{{{W_NS}}}val", color)
        sz_el = ET.SubElement(rPr, f"{{{W_NS}}}sz")
        sz_el.set(f"{{{W_NS}}}val", str(sz))
        szCs_el = ET.SubElement(rPr, f"{{{W_NS}}}szCs")
        szCs_el.set(f"{{{W_NS}}}val", str(sz))

        r = ET.SubElement(p, f"{{{W_NS}}}r")
        r_rPr = ET.SubElement(r, f"{{{W_NS}}}rPr")
        r_rFonts = ET.SubElement(r_rPr, f"{{{W_NS}}}rFonts")
        r_rFonts.set(f"{{{W_NS}}}ascii", font)
        r_rFonts.set(f"{{{W_NS}}}hAnsi", font)
        r_rFonts.set(f"{{{W_NS}}}cs", font)
        if bold:
            b2 = ET.SubElement(r_rPr, f"{{{W_NS}}}b")
            b2.set(f"{{{W_NS}}}val", "1")
        if italic:
            i2 = ET.SubElement(r_rPr, f"{{{W_NS}}}i")
            i2.set(f"{{{W_NS}}}val", "1")
        if color:
            c2 = ET.SubElement(r_rPr, f"{{{W_NS}}}color")
            c2.set(f"{{{W_NS}}}val", color)
        s2 = ET.SubElement(r_rPr, f"{{{W_NS}}}sz")
        s2.set(f"{{{W_NS}}}val", str(sz))
        s2c = ET.SubElement(r_rPr, f"{{{W_NS}}}szCs")
        s2c.set(f"{{{W_NS}}}val", str(sz))

        t = ET.SubElement(r, f"{{{W_NS}}}t")
        t.text = text
        if text.startswith(" ") or text.endswith(" "):
            t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")

        return p

    def make_drawing_para(rId: str, filename: str, cx: int, cy: int, doc_pr_id: int):
        p = ET.Element(f"{{{W_NS}}}p")
        pPr = ET.SubElement(p, f"{{{W_NS}}}pPr")
        spacing = ET.SubElement(pPr, f"{{{W_NS}}}spacing")
        spacing.set(f"{{{W_NS}}}line", "240")
        spacing.set(f"{{{W_NS}}}lineRule", "auto")
        spacing.set(f"{{{W_NS}}}after", "120")
        spacing.set(f"{{{W_NS}}}before", "60")

        r = ET.SubElement(p, f"{{{W_NS}}}r")
        drawing = ET.SubElement(r, f"{{{W_NS}}}drawing")
        inline = ET.SubElement(drawing, f"{{{WP_NS}}}inline")
        inline.set("distT", "0")
        inline.set("distB", "0")
        inline.set("distL", "0")
        inline.set("distR", "0")

        extent = ET.SubElement(inline, f"{{{WP_NS}}}extent")
        extent.set("cx", str(cx))
        extent.set("cy", str(cy))

        effectExtent = ET.SubElement(inline, f"{{{WP_NS}}}effectExtent")
        effectExtent.set("b", "0")
        effectExtent.set("l", "0")
        effectExtent.set("r", "0")
        effectExtent.set("t", "0")

        docPr = ET.SubElement(inline, f"{{{WP_NS}}}docPr")
        docPr.set("id", str(doc_pr_id))
        docPr.set("name", filename)

        graphic = ET.SubElement(inline, f"{{{A_NS}}}graphic")
        graphicData = ET.SubElement(graphic, f"{{{A_NS}}}graphicData")
        graphicData.set("uri", "http://schemas.openxmlformats.org/drawingml/2006/picture")

        pic = ET.SubElement(graphicData, f"{{{PIC_NS}}}pic")
        nvPicPr = ET.SubElement(pic, f"{{{PIC_NS}}}nvPicPr")
        cNvPr = ET.SubElement(nvPicPr, f"{{{PIC_NS}}}cNvPr")
        cNvPr.set("id", "0")
        cNvPr.set("name", filename)
        cNvPicPr = ET.SubElement(nvPicPr, f"{{{PIC_NS}}}cNvPicPr")
        cNvPicPr.set("preferRelativeResize", "0")

        blipFill = ET.SubElement(pic, f"{{{PIC_NS}}}blipFill")
        blip = ET.SubElement(blipFill, f"{{{A_NS}}}blip")
        blip.set(f"{{{R_NS}}}embed", rId)
        srcRect = ET.SubElement(blipFill, f"{{{A_NS}}}srcRect")
        srcRect.set("b", "0")
        srcRect.set("l", "0")
        srcRect.set("r", "0")
        srcRect.set("t", "0")
        stretch = ET.SubElement(blipFill, f"{{{A_NS}}}stretch")
        ET.SubElement(stretch, f"{{{A_NS}}}fillRect")

        spPr = ET.SubElement(pic, f"{{{PIC_NS}}}spPr")
        xfrm = ET.SubElement(spPr, f"{{{A_NS}}}xfrm")
        off = ET.SubElement(xfrm, f"{{{A_NS}}}off")
        off.set("x", "0")
        off.set("y", "0")
        ext = ET.SubElement(xfrm, f"{{{A_NS}}}ext")
        ext.set("cx", str(cx))
        ext.set("cy", str(cy))
        prstGeom = ET.SubElement(spPr, f"{{{A_NS}}}prstGeom")
        prstGeom.set("prst", "rect")
        ET.SubElement(spPr, f"{{{A_NS}}}ln")

        return p

    def set_cell_paragraphs(cell, paragraphs):
        tcPr = cell.find(f"{{{W_NS}}}tcPr")
        cell.clear()
        if tcPr is not None:
            cell.append(tcPr)
        for p in paragraphs:
            cell.append(p)

    def set_cell_text(cell, text: str, bold: bool = False, color: str = "000000", sz: int = 24, font: str = "Roboto", jc: str = "left"):
        p = make_para(text, bold=bold, color=color, sz=sz, font=font, jc=jc)
        set_cell_paragraphs(cell, [p])

    repo_root = Path(__file__).resolve().parents[4]
    resolve_roots = [
        base_dir or Path.cwd(),
        Path.cwd(),
        repo_root,
    ]

    with zipfile.ZipFile(template_path, "r") as z_in:
        namelist = z_in.namelist()
        doc_xml_str = z_in.read("word/document.xml")
        rels_xml_str = z_in.read("word/_rels/document.xml.rels")

        other_files = {}
        for name in namelist:
            if name not in ("word/document.xml", "word/_rels/document.xml.rels"):
                if name.startswith("word/media/") and name != "word/media/image5.png":
                    continue
                other_files[name] = z_in.read(name)

    doc_root = ET.fromstring(doc_xml_str)
    body = doc_root.find(f"{{{W_NS}}}body")

    rels_root = ET.fromstring(rels_xml_str)
    used_ids = set()
    rels_to_keep = []
    for rel in rels_root:
        r_id = rel.get("Id", "")
        t = rel.get("Type", "")
        if any(core in t for core in ("theme", "settings", "fontTable", "numbering", "styles", "customXml", "header", "footer")):
            rels_to_keep.append(rel)
            if r_id.startswith("rId") and r_id[3:].isdigit():
                used_ids.add(int(r_id[3:]))

    rels_root.clear()
    for rel in rels_to_keep:
        rels_root.append(rel)

    next_rid = max(used_ids) + 1 if used_ids else 13
    next_doc_pr_id = 900001
    new_images = {}

    def register_image(img_path_input: Any) -> tuple:
        nonlocal next_rid, next_doc_pr_id
        resolved = None
        p = Path(img_path_input)
        if p.is_file():
            resolved = p.resolve()
        else:
            for root in resolve_roots:
                cand = (root / p).resolve()
                if cand.is_file():
                    resolved = cand
                    break

        if not resolved or not resolved.is_file():
            raise FileNotFoundError(f"Evidence image not found: {img_path_input}")

        rel_key = str(resolved)
        if rel_key in new_images:
            return new_images[rel_key]

        rId = f"rId{next_rid}"
        next_rid += 1
        doc_pr_id = next_doc_pr_id
        next_doc_pr_id += 1

        img_bytes = resolved.read_bytes()
        ext = resolved.suffix.lower() or ".png"
        zip_filename = f"image_evidence_{len(new_images) + 1}{ext}"
        zip_path = f"word/media/{zip_filename}"

        w, h = 1280, 800
        if len(img_bytes) >= 24 and img_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
            try:
                w, h = struct.unpack(">II", img_bytes[16:24])
            except Exception:
                pass

        cx = 5238750
        cy = int(cx * h / w)

        rel_el = ET.SubElement(rels_root, "{http://schemas.openxmlformats.org/package/2006/relationships}Relationship")
        rel_el.set("Id", rId)
        rel_el.set("Type", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image")
        rel_el.set("Target", f"media/{zip_filename}")

        other_files[zip_path] = img_bytes
        info = (rId, zip_filename, cx, cy, doc_pr_id)
        new_images[rel_key] = info
        return info

    # 1. Update Cover Table (body[11])
    if len(body) > 11:
        tbl11 = body[11]
        tbl11_rows = tbl11.findall(f"{{{W_NS}}}tr")
        if len(tbl11_rows) >= 2:
            c00 = tbl11_rows[0].findall(f"{{{W_NS}}}tc")[0]
            p00_0 = make_para(org_name, bold=True, color=brand_hex, sz=28, font="Roboto")
            p00_1 = make_para(division_name, bold=False, color="444444", sz=22, font="Roboto")
            set_cell_paragraphs(c00, [p00_0, p00_1])

            c10 = tbl11_rows[1].findall(f"{{{W_NS}}}tc")[0]
            p10_0 = make_para(doc_title, bold=True, color=brand_hex, sz=32, font="Roboto", before=200, after=100)
            p10_1 = make_para("Quality Assurance Document", bold=True, color="333333", sz=26, font="Roboto", after=100)
            p10_2 = make_para(f"Nomor: {project_no}", bold=False, color="555555", sz=22, font="Roboto", after=60)
            p10_3 = make_para(f"Ver {doc_version} {doc_date}", bold=False, color="777777", sz=20, font="Roboto", after=60)
            set_cell_paragraphs(c10, [p10_0, p10_1, p10_2, p10_3])

    # 2. Update Metadata Table (body[14])
    if len(body) > 14:
        tbl14 = body[14]
        r14_rows = tbl14.findall(f"{{{W_NS}}}tr")
        if len(r14_rows) >= 8:
            set_cell_text(r14_rows[1].findall(f"{{{W_NS}}}tc")[1], project_no, bold=True, font="Roboto")
            set_cell_text(r14_rows[2].findall(f"{{{W_NS}}}tc")[1], doc_title, bold=True, font="Roboto")
            set_cell_text(r14_rows[3].findall(f"{{{W_NS}}}tc")[1], doc_date, font="Roboto")
            set_cell_text(r14_rows[4].findall(f"{{{W_NS}}}tc")[1], division_name, font="Roboto")
            set_cell_text(r14_rows[5].findall(f"{{{W_NS}}}tc")[1], product_name, bold=True, font="Roboto")
            set_cell_text(r14_rows[6].findall(f"{{{W_NS}}}tc")[1], doc_version, font="Roboto")
            set_cell_text(r14_rows[7].findall(f"{{{W_NS}}}tc")[1], test_plan_link, font="Roboto")

        if len(r14_rows) > 8:
            nested_tbl = r14_rows[8].findall(f"{{{W_NS}}}tc")[1].find(f"{{{W_NS}}}tbl")
            if nested_tbl is not None:
                nested_rows = nested_tbl.findall(f"{{{W_NS}}}tr")
                if len(nested_rows) >= 4:
                    set_cell_text(nested_rows[0].findall(f"{{{W_NS}}}tc")[0], "[  ]", font="Roboto", jc="center")
                    set_cell_text(nested_rows[0].findall(f"{{{W_NS}}}tc")[1], "Project Plan", font="Roboto")
                    set_cell_text(nested_rows[1].findall(f"{{{W_NS}}}tc")[0], "[✔]", bold=True, color=brand_hex, font="Roboto", jc="center")
                    set_cell_text(nested_rows[1].findall(f"{{{W_NS}}}tc")[1], "PRD (01-requirements.md)", bold=True, font="Roboto")
                    set_cell_text(nested_rows[2].findall(f"{{{W_NS}}}tc")[0], "[✔]", bold=True, color=brand_hex, font="Roboto", jc="center")
                    set_cell_text(nested_rows[2].findall(f"{{{W_NS}}}tc")[1], "Technical Spec / SDD (02-technical-spec.md)", bold=True, font="Roboto")
                    set_cell_text(nested_rows[3].findall(f"{{{W_NS}}}tc")[0], "[  ]", font="Roboto", jc="center")
                    set_cell_text(nested_rows[3].findall(f"{{{W_NS}}}tc")[1], "Other", font="Roboto")

    def _set_body_para(idx: int, txt: str):
        if len(body) > idx:
            el = body[idx]
            el.clear()
            pPr = ET.SubElement(el, f"{{{W_NS}}}pPr")
            sp = ET.SubElement(pPr, f"{{{W_NS}}}spacing")
            sp.set(f"{{{W_NS}}}line", "240")
            sp.set(f"{{{W_NS}}}lineRule", "auto")
            sp.set(f"{{{W_NS}}}after", "100")
            rPr = ET.SubElement(pPr, f"{{{W_NS}}}rPr")
            rf = ET.SubElement(rPr, f"{{{W_NS}}}rFonts")
            rf.set(f"{{{W_NS}}}ascii", "Roboto")
            rf.set(f"{{{W_NS}}}hAnsi", "Roboto")
            rf.set(f"{{{W_NS}}}cs", "Roboto")
            r = ET.SubElement(el, f"{{{W_NS}}}r")
            r_rPr = ET.SubElement(r, f"{{{W_NS}}}rPr")
            r_rf = ET.SubElement(r_rPr, f"{{{W_NS}}}rFonts")
            r_rf.set(f"{{{W_NS}}}ascii", "Roboto")
            r_rf.set(f"{{{W_NS}}}hAnsi", "Roboto")
            r_rf.set(f"{{{W_NS}}}cs", "Roboto")
            t = ET.SubElement(r, f"{{{W_NS}}}t")
            t.text = txt

    # 3. Update Overview (body[21] Background & body[23] Expected Result)
    _set_body_para(21, background_text)
    _set_body_para(23, expected_overview)

    # 4. Update Scenario Test Table (body[46])
    scenarios = payload.get("scenarios") or [
        {"num": 1, "title": "[POSITIVE] Sample Verification Scenario", "expected": "Then system returns expected output", "result": "PASSED", "note": "TC-1"}
    ]
    if len(body) > 46:
        tbl46 = body[46]
        r46_all = tbl46.findall(f"{{{W_NS}}}tr")
        if len(r46_all) >= 2:
            row_template = copy.deepcopy(r46_all[1])
            for tr in r46_all[1:]:
                tbl46.remove(tr)
            for sc in scenarios:
                tr_clone = copy.deepcopy(row_template)
                cells = tr_clone.findall(f"{{{W_NS}}}tc")
                set_cell_text(cells[0], str(sc.get("num", "")), font="Roboto", jc="center")
                set_cell_text(cells[1], str(sc.get("title", "")), font="Roboto")
                set_cell_text(cells[2], str(sc.get("expected", "")), font="Roboto")
                set_cell_text(cells[3], str(sc.get("result", "PASSED")), bold=True, color=brand_hex, font="Roboto", jc="center")
                set_cell_text(cells[4], str(sc.get("note", "")), font="Roboto")
                tbl46.append(tr_clone)

    # 5. Build Test Case Report Tables
    test_cases_data = payload.get("test_cases") or [
        {
            "id": "TC-1",
            "title": "[POSITIVE] Sample Verification Scenario",
            "preconditions": "Target service is running",
            "details": ["Given service is UP", "When endpoint is probed", "Then HTTP 200 OK returned"],
            "actual_items": [{"type": "text", "value": "1. Verification completed."}],
            "result": "PASSED",
            "note": "Verified."
        }
    ]

    if len(body) > 50:
        tbl50_template = copy.deepcopy(body[50])
        new_report_elements = []
        for tc in test_cases_data:
            tbl = copy.deepcopy(tbl50_template)
            rows = tbl.findall(f"{{{W_NS}}}tr")
            c0 = rows[0].findall(f"{{{W_NS}}}tc")[0]
            set_cell_text(c0, f"Test Case {tc.get('id', 'TC-1')}", bold=True, color="ffffff", sz=24, font="Roboto")
            set_cell_text(rows[1].findall(f"{{{W_NS}}}tc")[1], str(tc.get("title", "")), bold=True, font="Roboto")
            set_cell_text(rows[2].findall(f"{{{W_NS}}}tc")[1], str(tc.get("preconditions", "")), font="Roboto")

            detail_ps = [make_para(str(line), font="Roboto", after=30) for line in tc.get("details", [])]
            set_cell_paragraphs(rows[3].findall(f"{{{W_NS}}}tc")[1], detail_ps or [make_para("-", font="Roboto")])

            actual_ps = []
            for item in tc.get("actual_items", []):
                if isinstance(item, dict):
                    itype, ival = item.get("type", "text"), item.get("value", "")
                elif isinstance(item, (list, tuple)) and len(item) >= 2:
                    itype, ival = item[0], item[1]
                else:
                    itype, ival = "text", str(item)
                if itype == "text":
                    actual_ps.append(make_para(str(ival), font="Roboto", after=40))
                elif itype == "image":
                    rId, fn, cx, cy, dpid = register_image(ival)
                    actual_ps.append(make_drawing_para(rId, fn, cx, cy, dpid))
            set_cell_paragraphs(rows[4].findall(f"{{{W_NS}}}tc")[1], actual_ps or [make_para("-", font="Roboto")])

            r5_cells = rows[5].findall(f"{{{W_NS}}}tc")
            set_cell_text(r5_cells[0], "Final Result", bold=True, font="Roboto")
            set_cell_text(r5_cells[1], str(tc.get("result", "PASSED")), bold=True, color=brand_hex, font="Roboto", jc="center")
            set_cell_text(r5_cells[2], f"Note: {tc.get('note', '')}", font="Roboto")

            new_report_elements.append(tbl)
            new_report_elements.append(make_para("", font="Roboto", after=100))

        report_idx = -1
        catatan_idx = -1
        for idx, el in enumerate(body):
            txt = "".join(el.itertext()).strip()
            if txt == "REPORT":
                report_idx = idx
            elif txt == "CATATAN" and report_idx != -1:
                catatan_idx = idx
                break

        if report_idx != -1 and catatan_idx != -1:
            for _ in range(catatan_idx - (report_idx + 1)):
                del body[report_idx + 1]
            for offset, elem in enumerate(new_report_elements):
                body.insert(report_idx + 1 + offset, elem)

    result_idx = -1
    persetujuan_idx = -1
    revision_idx = -1
    catatan_new_idx = -1
    for idx, el in enumerate(body):
        txt = "".join(el.itertext()).strip()
        if txt == "CATATAN":
            catatan_new_idx = idx
        elif "RESULT" in txt and el.tag.endswith("tbl"):
            result_idx = idx
        elif "LEMBAR PERSETUJUAN" in txt and el.tag.endswith("tbl"):
            persetujuan_idx = idx
        elif ("PIC" in txt or "Deskripsi" in txt) and el.tag.endswith("tbl"):
            revision_idx = idx

    if catatan_new_idx != -1 and catatan_new_idx + 1 < len(body):
        _set_body_para(catatan_new_idx + 1, notes_text)

    if result_idx != -1:
        tbl_res = body[result_idx]
        r1_c0 = tbl_res.findall(f"{{{W_NS}}}tr")[1].findall(f"{{{W_NS}}}tc")[0]
        set_cell_text(r1_c0, result_banner, bold=True, color=brand_hex, sz=28, font="Roboto", jc="center")

    approvals = payload.get("approvals") or []
    if not approvals:
        approvals = [
            {"role": "Tester", "name": "QA Engineer", "date": doc_date, "status": "(Signed)"},
            {"role": "Reviewer", "name": "Senior Lead Engineer / Analyst", "date": doc_date, "status": "(Signed)"},
        ]
        for off in d_officials:
            if isinstance(off, dict):
                approvals.append({"role": off.get("role", "Approver"), "name": off.get("name", "[PIC]"), "date": doc_date, "status": ""})

    if persetujuan_idx != -1:
        tbl_p = body[persetujuan_idx]
        p_rows = tbl_p.findall(f"{{{W_NS}}}tr")
        for idx_a, app in enumerate(approvals):
            row_i = idx_a + 2
            if row_i < len(p_rows):
                c = p_rows[row_i].findall(f"{{{W_NS}}}tc")
                set_cell_text(c[0], str(idx_a + 1), font="Roboto", jc="center")
                set_cell_text(c[1], str(app.get("role", "")), font="Roboto")
                set_cell_text(c[2], str(app.get("name", "")), font="Roboto")
                set_cell_text(c[3], str(app.get("date", doc_date)), font="Roboto", jc="center")
                st_txt = str(app.get("status", ""))
                set_cell_text(c[4], st_txt, bold=bool(st_txt), color=brand_hex if st_txt else "000000", font="Roboto", jc="center")

    revisions = payload.get("revisions") or [
        {"no": 1, "pic": "QA Engineer", "desc": f"Initial QAD Document - {product_name}", "version": doc_version, "date": doc_date}
    ]
    if revision_idx != -1:
        tbl_rev = body[revision_idx]
        rev_rows = tbl_rev.findall(f"{{{W_NS}}}tr")
        if len(rev_rows) > 1 and revisions:
            rev0 = revisions[0]
            c = rev_rows[1].findall(f"{{{W_NS}}}tc")
            set_cell_text(c[0], str(rev0.get("no", 1)), font="Roboto", jc="center")
            set_cell_text(c[1], str(rev0.get("pic", "QA Engineer")), font="Roboto")
            set_cell_text(c[2], str(rev0.get("desc", doc_title)), font="Roboto")
            set_cell_text(c[3], str(rev0.get("version", doc_version)), font="Roboto", jc="center")
            set_cell_text(c[4], str(rev0.get("date", doc_date)), font="Roboto", jc="center")

    new_doc_xml = ET.tostring(doc_root, encoding="utf-8", xml_declaration=True)
    new_rels_xml = ET.tostring(rels_root, encoding="utf-8", xml_declaration=True)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as z_out:
        for fname, content in other_files.items():
            z_out.writestr(fname, content)
        z_out.writestr("word/document.xml", new_doc_xml)
        z_out.writestr("word/_rels/document.xml.rels", new_rels_xml)

def write_html(md_text: str, output_path: Path, title: Optional[str] = None):
    """Generate standalone styled HTML document."""
    doc_title = title or "Document"
    lines = md_text.splitlines()
    html_parts = []
    table_lines = []
    
    def flush_table_html():
        if not table_lines:
            return ""
        rows = []
        for t in table_lines:
            cells = [c.strip() for c in t.strip("|").split("|")]
            if all(re.match(r"^:?-+:?$", c) for c in cells):
                continue
            rows.append(cells)
        if not rows:
            return ""
        out = ["<table>"]
        out.append("<thead><tr>" + "".join(f"<th>{html.escape(c)}</th>" for c in rows[0]) + "</tr></thead>")
        out.append("<tbody>")
        for r in rows[1:]:
            out.append("<tr>" + "".join(f"<td>{html.escape(c)}</td>" for c in r) + "</tr>")
        out.append("</tbody></table>")
        return "\n".join(out)

    for line in lines:
        s = line.strip()
        if s.startswith("|") and s.endswith("|"):
            table_lines.append(s)
            continue
        else:
            if table_lines:
                html_parts.append(flush_table_html())
                table_lines = []
        if not s:
            continue
        if s.startswith("# "):
            html_parts.append(f"<h1>{html.escape(s[2:])}</h1>")
        elif s.startswith("## "):
            html_parts.append(f"<h2>{html.escape(s[3:])}</h2>")
        elif s.startswith("### "):
            html_parts.append(f"<h3>{html.escape(s[4:])}</h3>")
        elif s.startswith("- ") or s.startswith("* "):
            html_parts.append(f"<li>{html.escape(s[2:])}</li>")
        else:
            html_parts.append(f"<p>{html.escape(s)}</p>")
            
    if table_lines:
        html_parts.append(flush_table_html())
        
    full_html = f"""<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="utf-8">
  <title>{html.escape(doc_title)}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #333; max-width: 900px; margin: 40px auto; padding: 0 20px; }}
    h1, h2, h3 {{ color: #1B4D3E; }}
    table {{ width: 100%; border-collapse: collapse; margin: 25px 0; font-size: 0.95em; box-shadow: 0 0 10px rgba(0,0,0,0.05); }}
    table thead tr {{ background-color: #1B4D3E; color: #ffffff; text-align: left; font-weight: bold; }}
    table th, table td {{ padding: 12px 15px; border-bottom: 1px solid #dddddd; }}
    table tbody tr:nth-of-type(even) {{ background-color: #f8faf9; }}
    table tbody tr:last-of-type {{ border-bottom: 2px solid #1B4D3E; }}
  </style>
</head>
<body>
  {"".join(html_parts)}
</body>
</html>"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(full_html, encoding="utf-8")

# --- MAIN COMMAND HANDLERS ---

def handle_inspect(args):
    """Execute inspect command."""
    file_path = Path(args.file)
    if not file_path.exists():
        print(json.dumps({"error": f"File does not exist: {file_path}"}))
        sys.exit(1)
        
    ext = file_path.suffix.lower()
    stat = file_path.stat()
    summary = {
        "file_name": file_path.name,
        "extension": ext,
        "file_size_bytes": stat.st_size,
        "file_size_human": f"{stat.st_size / 1024:.1f} KB"
    }
    
    if ext == ".xlsx":
        sheets = parse_xlsx_sheets(file_path)
        summary["sheet_count"] = len(sheets)
        summary["sheets"] = [
            {"name": s["name"], "rows": s["row_count"], "columns": s["col_count"]}
            for s in sheets
        ]
    elif ext == ".docx":
        docx_data = parse_docx(file_path)
        summary["paragraph_count"] = docx_data["para_count"]
        summary["table_count"] = docx_data["table_count"]
        summary["headings"] = docx_data["headings"]
        if docx_data.get("image_count", 0) > 0:
            summary["image_count"] = docx_data["image_count"]
    elif ext == ".pptx":
        pptx_data = parse_pptx(file_path)
        summary["slide_count"] = pptx_data["slide_count"]
    elif ext == ".pdf":
        pdf_data = read_pdf(file_path)
        summary["page_count"] = pdf_data.get("page_count", 0)
    elif ext in [".csv", ".tsv"]:
        lines = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        summary["row_count"] = len(lines)
    elif ext == ".json":
        try:
            j_data = json.loads(file_path.read_text(encoding="utf-8"))
            if isinstance(j_data, list):
                summary["record_count"] = len(j_data)
            elif isinstance(j_data, dict):
                summary["keys"] = list(j_data.keys())
        except Exception:
            pass
            
    print(json.dumps(summary, indent=2))

def handle_read(args):
    """Execute read command."""
    file_path = Path(args.file)
    if not file_path.exists():
        print(f"Error: File does not exist: {file_path}", file=sys.stderr)
        sys.exit(1)
        
    ext = file_path.suffix.lower()
    out_lines = []
    
    if ext == ".xlsx":
        sheets = parse_xlsx_sheets(file_path)
        target_sheet = args.sheet
        max_rows = args.max_rows
        
        for s in sheets:
            if target_sheet:
                if str(target_sheet).lower() != s["name"].lower() and str(target_sheet) != str(sheets.index(s) + 1):
                    continue
                    
            out_lines.append(f"## Sheet: {s['name']}")
            rows = s["rows"]
            if max_rows and len(rows) > max_rows:
                rows = rows[:max_rows]
                out_lines.append(f"> *(Menampilkan {max_rows} dari {s['row_count']} baris)*\n")
            tbl_md = format_markdown_table(rows)
            out_lines.append(tbl_md)
            out_lines.append("")
            
    elif ext == ".docx":
        docx_data = parse_docx(file_path)
        for el in docx_data["elements"]:
            e_type = el["type"]
            if e_type == "heading":
                prefix = "#" * el["level"]
                out_lines.append(f"{prefix} {el['text']}\n")
            elif e_type == "list_item":
                out_lines.append(f"- {el['text']}")
            elif e_type == "paragraph":
                out_lines.append(f"{el['text']}\n")
            elif e_type == "table":
                out_lines.append(format_markdown_table(el["rows"]))
                out_lines.append("")
                
    elif ext in [".doc", ".rtf"]:
        text = read_doc_or_rtf_mac(file_path)
        out_lines.append(text)
        
    elif ext == ".pptx":
        pptx_data = parse_pptx(file_path)
        for s in pptx_data["slides"]:
            out_lines.append(f"## Slide {s['slide_number']}")
            for p in s["paragraphs"]:
                out_lines.append(f"- {p}")
            out_lines.append("")
            
    elif ext == ".pdf":
        pdf_data = read_pdf(file_path)
        for idx, p_text in enumerate(pdf_data.get("pages", []), start=1):
            out_lines.append(f"## Halaman {idx}")
            out_lines.append(p_text.strip())
            out_lines.append("")
            
    elif ext in [".csv", ".tsv"]:
        delimiter = "\t" if ext == ".tsv" else ","
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        reader = csv.reader(io.StringIO(content), delimiter=delimiter)
        rows = list(reader)
        out_lines.append(format_markdown_table(rows))
        
    elif ext == ".json":
        data = json.loads(file_path.read_text(encoding="utf-8"))
        if isinstance(data, list) and data and isinstance(data[0], dict):
            headers = list(data[0].keys())
            rows = [headers]
            for item in data:
                rows.append([str(item.get(h, "")) for h in headers])
            out_lines.append(format_markdown_table(rows))
        else:
            out_lines.append("```json")
            out_lines.append(json.dumps(data, indent=2))
            out_lines.append("```")
            
    result = "\n".join(out_lines).strip()
    
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(result, encoding="utf-8")
        print(f"[✓] Output ditulis ke: {out_path}")
    else:
        print(result)

def handle_write(args):
    """Execute write command."""
    input_path = Path(args.input)
    output_path = Path(args.output)
    
    if not input_path.exists():
        print(f"Error: Input file does not exist: {input_path}", file=sys.stderr)
        sys.exit(1)
        
    in_ext = input_path.suffix.lower()
    out_ext = output_path.suffix.lower()
    
    if in_ext in [".csv", ".tsv"]:
        delimiter = "\t" if in_ext == ".tsv" else ","
        content = input_path.read_text(encoding="utf-8", errors="ignore")
        reader = csv.reader(io.StringIO(content), delimiter=delimiter)
        rows = list(reader)
        sheets = [{"name": clean_sheet_name(input_path.stem), "rows": rows}]
        md_text = format_markdown_table(rows)
    elif in_ext == ".json":
        data = json.loads(input_path.read_text(encoding="utf-8"))
        if isinstance(data, list) and data and isinstance(data[0], dict):
            headers = list(data[0].keys())
            rows = [headers]
            for item in data:
                rows.append([str(item.get(h, "")) for h in headers])
            sheets = [{"name": clean_sheet_name(input_path.stem), "rows": rows}]
            md_text = format_markdown_table(rows)
        else:
            md_text = f"```json\n{json.dumps(data, indent=2)}\n```"
            sheets = [{"name": "Data", "rows": [["JSON Content"], [json.dumps(data)]]}]
    else:
        md_text = input_path.read_text(encoding="utf-8")
        sheets = parse_markdown_tables_with_headings(md_text)
        
    if out_ext == ".xlsx":
        write_xlsx(sheets, output_path)
        print(f"[✓] Berhasil membuat spreadsheet Excel: {output_path} ({len(sheets)} sheet)")
    elif out_ext == ".docx":
        if args.template:
            tmpl_path = find_qad_template(args.template, domain_id=getattr(args, "domain", None))
            populate_qad_template(tmpl_path, output_path, data_path=input_path, base_dir=input_path.parent, domain_id=getattr(args, "domain", None))
            print(f"[✓] Berhasil membuat dokumen Word dari template: {output_path}")
        else:
            write_docx(md_text, output_path, title=args.title, base_dir=input_path.parent)
            print(f"[✓] Berhasil membuat dokumen Word: {output_path}")
    elif out_ext == ".html":
        write_html(md_text, output_path, title=args.title)
        print(f"[✓] Berhasil membuat dokumen HTML: {output_path}")
    else:
        print(f"Error: Format output tidak didukung: {out_ext} (hanya .xlsx, .docx, .html)", file=sys.stderr)
        sys.exit(1)

def handle_write_qad(args):
    output_path = Path(args.output).resolve()
    domain_id = getattr(args, "domain", None)
    tmpl_path = find_qad_template(args.template, domain_id=domain_id)
    data_path = Path(args.data).resolve() if args.data else None
    base_dir = Path(args.base_dir).resolve() if args.base_dir else (data_path.parent if data_path else Path.cwd())
    populate_qad_template(tmpl_path, output_path, data_path=data_path, base_dir=base_dir, domain_id=domain_id)
    print(f"[✓] Berhasil membuat dokumen QAD: {output_path}")

def main():
    parser = argparse.ArgumentParser(
        description="Token-Efficient Office Document Suite CLI (Zero-Dependency Resilient)",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="subcommand", help="Subcommand to execute")
    
    # 1. inspect
    p_inspect = subparsers.add_parser("inspect", help="Inspect document structure (metadata, sheets, headings, pages)")
    p_inspect.add_argument("file", help="Path to document file (.xlsx, .docx, .pptx, .pdf, .csv, .json)")
    
    # 2. read
    p_read = subparsers.add_parser("read", help="Extract document content into clean Markdown")
    p_read.add_argument("file", help="Path to document file to read")
    p_read.add_argument("--sheet", help="Specific sheet name or 1-based index (for .xlsx)")
    p_read.add_argument("--max-rows", type=int, help="Limit rows per sheet (for token economy)")
    p_read.add_argument("--output", "-o", help="Write Markdown output to specified file instead of stdout")
    
    # 3. write
    p_write = subparsers.add_parser("write", help="Convert Markdown/CSV/JSON to styled .xlsx, .docx, or .html")
    p_write.add_argument("input", help="Source file (.md, .csv, .tsv, .json)")
    p_write.add_argument("output", help="Target output file (.xlsx, .docx, .html)")
    p_write.add_argument("--title", help="Optional document title (for .docx / .html)")
    p_write.add_argument("--template", help="Optional Word template (.docx)")
    p_write.add_argument("--domain", help="Optional Specific Domain ID for template/brand resolution")
    
    # 4. write-qad
    p_write_qad = subparsers.add_parser("write-qad", help="Populate an official QAD Word template (.docx) from structured data and active Specific Domain Pack")
    p_write_qad.add_argument("output", help="Target output file (.docx)")
    p_write_qad.add_argument("--template", help="Path to base template (.docx), defaults to active Specific Domain template")
    p_write_qad.add_argument("--data", help="Path to JSON or Markdown test specifications")
    p_write_qad.add_argument("--base-dir", help="Base directory to resolve evidence images")
    p_write_qad.add_argument("--domain", help="Specific Domain ID (defaults to active domain)")

    args = parser.parse_args()
    
    if args.subcommand == "inspect":
        handle_inspect(args)
    elif args.subcommand == "read":
        handle_read(args)
    elif args.subcommand == "write":
        handle_write(args)
    elif args.subcommand == "write-qad":
        handle_write_qad(args)
    else:
        parser.print_help()
        sys.exit(0)

if __name__ == "__main__":
    main()
