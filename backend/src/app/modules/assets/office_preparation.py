"""M03 native DOCX/XLSX strategies. Legacy formats need a separately enabled converter."""

from io import BytesIO
from pathlib import PurePosixPath
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZipFile

from app.modules.recognition.facts import ParagraphLocation, SheetLocation
from app.modules.recognition.model import ModelRequest, PreparedSource

WORD = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
SHEET = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


def xml(archive, name):
    info = archive.getinfo(name)
    if info.file_size > 10_000_000 or info.file_size > max(info.compress_size, 1) * 500:
        raise ValueError("Office XML exceeds preparation limit")
    data = archive.read(name)
    if b"<!DOCTYPE" in data or b"<!ENTITY" in data:
        raise ValueError("Unsupported XML declaration")
    return ET.fromstring(data)


def docx_request(source, data):
    try:
        with ZipFile(BytesIO(data)) as archive:
            tree = xml(archive, "word/document.xml")
        text = "\n".join("".join(node.itertext()) for node in tree.iter(WORD + "t"))
        if not text.strip():
            raise ValueError("Empty Office document")
        # Explicit paragraph path denotes the complete body; no invented page number.
        location = ParagraphLocation(
            kind="paragraph",
            file_id=source.file_id,
            file_version_id=source.file_version_id,
            path="word/document.xml/body",
        )
        return ModelRequest(
            (PreparedSource("body", location, text, preparation_profile="docx-native-v1"),)
        )
    except (BadZipFile, KeyError, ET.ParseError):
        raise ValueError("Unsupported DOCX") from None


def xlsx_sheets(data):
    try:
        with ZipFile(BytesIO(data)) as archive:
            strings = []
            if "xl/sharedStrings.xml" in archive.namelist():
                strings = [
                    "".join(t.text or "" for t in item.iter(SHEET + "t"))
                    for item in xml(archive, "xl/sharedStrings.xml").iter(SHEET + "si")
                ]
            workbook = xml(archive, "xl/workbook.xml")
            links = {
                r.attrib["Id"]: r.attrib["Target"]
                for r in xml(archive, "xl/_rels/workbook.xml.rels")
            }
            result = {}
            for sheet in workbook.iter(SHEET + "sheet"):
                target = links.get(sheet.attrib.get(REL + "id"))
                if not target or ".." in PurePosixPath(target).parts:
                    raise ValueError("Unsupported sheet relationship")
                path = target.lstrip("/") if target.startswith("/") else "xl/" + target
                cells = []
                for cell in xml(archive, path).iter(SHEET + "c"):
                    address = cell.attrib.get("r", "")
                    value = cell.find(SHEET + "v")
                    kind = cell.attrib.get("t")
                    value = value.text if value is not None else None
                    if kind == "s" and value is not None:
                        value = strings[int(value)]
                    elif kind == "inlineStr":
                        value = "".join(t.text or "" for t in cell.iter(SHEET + "t"))
                    elif kind == "b" and value is not None:
                        value = value == "1"
                    formula = cell.find(SHEET + "f")
                    cells.append(
                        {
                            "address": address,
                            "value": value,
                            "formula": formula.text if formula is not None else None,
                            "known_state": "known"
                            if value is not None
                            else "unreadable"
                            if formula is not None
                            else "missing",
                        }
                    )
                    if len(cells) > 50_000:
                        raise ValueError("Too many spreadsheet cells")
                result[sheet.attrib["name"]] = cells
            return result
    except (BadZipFile, KeyError, ET.ParseError, IndexError):
        raise ValueError("Unsupported XLSX") from None


def xlsx_request(source, data):
    sources = []
    for name, cells in xlsx_sheets(data).items():
        text = "\n".join(f"{c['address']}: {c['value']}" for c in cells if c["value"] is not None)
        if not text.strip():
            continue
        location = SheetLocation(
            kind="sheet",
            file_id=source.file_id,
            file_version_id=source.file_version_id,
            sheet=name,
            cell_range=cells[0]["address"] + ":" + cells[-1]["address"],
        )
        sources.append(
            PreparedSource(
                "sheet-" + str(len(sources) + 1),
                location,
                text,
                preparation_profile="xlsx-native-v1/cached-values-no-formula-evaluation",
            )
        )
    if not sources:
        raise ValueError("Empty spreadsheet")
    return ModelRequest(tuple(sources))
