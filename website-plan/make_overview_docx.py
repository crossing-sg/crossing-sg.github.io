"""Convert TEAM_OVERVIEW.md into TEAM_OVERVIEW.docx with only the Python standard library.
Handles the parts used in that file: headings, paragraphs, numbered lists, tables, **bold** and `code`.
Run: python make_overview_docx.py"""
import os
import re
import zipfile
from xml.sax.saxutils import escape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "TEAM_OVERVIEW.md")
OUT = os.path.join(ROOT, "TEAM_OVERVIEW.docx")
PAGE_W = 11906 - 2 * 1134   # A4 width minus 2 cm margins, in twentieths of a point


def runs(text, size=None):
    parts = re.split(r"(\*\*[^*]+\*\*|`[^`]+`)", text)
    xml = ""
    for p in parts:
        if not p:
            continue
        props = ""
        if p.startswith("**"):
            p, props = p[2:-2], "<w:b/>"
        elif p.startswith("`"):
            p, props = p[1:-1], '<w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/><w:sz w:val="19"/>'
        if size and "w:sz" not in props:
            props += f'<w:sz w:val="{size}"/>'
        xml += f'<w:r><w:rPr>{props}</w:rPr><w:t xml:space="preserve">{escape(p)}</w:t></w:r>'
    return xml


def para(text, style=None, size=None, indent=None, after=None):
    ppr = ""
    if style:
        ppr += f'<w:pStyle w:val="{style}"/>'
    if after is not None:
        ppr += f'<w:spacing w:after="{after}"/>'
    if indent:
        ppr += f'<w:ind w:left="{indent}" w:hanging="300"/>'
    return f"<w:p><w:pPr>{ppr}</w:pPr>{runs(text, size)}</w:p>"


def table(rows):
    n = len(rows[0])
    # First column narrower when the table has 3 or more columns
    widths = [PAGE_W // n] * n
    if n >= 3:
        widths = [int(PAGE_W * 0.34)] + [int(PAGE_W * 0.66 / (n - 1))] * (n - 1)
    widths[-1] += PAGE_W - sum(widths)
    border = "".join(f'<w:{s} w:val="single" w:sz="4" w:space="0" w:color="999999"/>'
                     for s in ["top", "left", "bottom", "right", "insideH", "insideV"])
    xml = (f'<w:tbl><w:tblPr><w:tblW w:w="{PAGE_W}" w:type="dxa"/><w:tblBorders>{border}</w:tblBorders>'
           f'<w:tblCellMar><w:left w:w="90" w:type="dxa"/><w:right w:w="90" w:type="dxa"/></w:tblCellMar></w:tblPr>'
           "<w:tblGrid>" + "".join(f'<w:gridCol w:w="{w}"/>' for w in widths) + "</w:tblGrid>")
    for r, row in enumerate(rows):
        xml += "<w:tr>" + ("<w:trPr><w:tblHeader/></w:trPr>" if r == 0 else "")
        for c, cell in enumerate(row):
            shade = '<w:shd w:val="clear" w:color="auto" w:fill="E8E8E8"/>' if r == 0 else ""
            text = f"**{cell}**" if r == 0 and cell else cell
            xml += (f'<w:tc><w:tcPr><w:tcW w:w="{widths[c]}" w:type="dxa"/>{shade}</w:tcPr>'
                    f"{para(text, size=19, after=40)}</w:tc>")
        xml += "</w:tr>"
    return xml + "</w:tbl>" + para("", after=0)


def body():
    lines = open(SRC, encoding="utf-8").read().splitlines()
    xml, i = "", 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                if not re.match(r"^\|[\s\-|]+\|$", lines[i]):
                    rows.append([c.strip() for c in lines[i].strip("|").split("|")])
                i += 1
            xml += table(rows)
            continue
        h = re.match(r"^(#+) (.*)", line)
        n = re.match(r"^(\d+)\. (.*)", line)
        if h:
            xml += para(h.group(2), "Heading" + str(len(h.group(1))))
        elif n:
            xml += para(f"{n.group(1)}.  {n.group(2)}", indent=360, after=60)
        elif line.strip():
            xml += para(line)
        i += 1
    return xml


STYLES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:cs="Calibri"/><w:sz w:val="22"/></w:rPr></w:rPrDefault>
<w:pPrDefault><w:pPr><w:spacing w:after="120" w:line="264" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>
<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/>
<w:pPr><w:keepNext/><w:spacing w:before="0" w:after="200"/><w:outlineLvl w:val="0"/></w:pPr><w:rPr><w:b/><w:sz w:val="36"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/>
<w:pPr><w:keepNext/><w:spacing w:before="320" w:after="120"/><w:outlineLvl w:val="1"/></w:pPr><w:rPr><w:b/><w:sz w:val="28"/></w:rPr></w:style>
</w:styles>"""

DOC = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>{body}
<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134" w:header="567" w:footer="567" w:gutter="0"/></w:sectPr>
</w:body></w:document>"""

TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>"""

RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""

DOC_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""

with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr("[Content_Types].xml", TYPES)
    z.writestr("_rels/.rels", RELS)
    z.writestr("word/_rels/document.xml.rels", DOC_RELS)
    z.writestr("word/styles.xml", STYLES)
    z.writestr("word/document.xml", DOC.format(body=body()))
print(OUT, os.path.getsize(OUT), "bytes")
