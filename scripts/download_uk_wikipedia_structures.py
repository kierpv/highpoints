import csv
import json
import re
import urllib.request
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data"
URL = "https://en.wikipedia.org/wiki/List_of_tallest_structures_in_the_United_Kingdom"


class WikiTableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables = []
        self.current_section = ""
        self.in_heading = False
        self.heading_level = None
        self.heading_text = []
        self.in_table = False
        self.table_depth = 0
        self.table_class = ""
        self.current_table = None
        self.in_row = False
        self.current_row = None
        self.in_cell = False
        self.current_cell = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {"h2", "h3"}:
            self.in_heading = True
            self.heading_level = tag
            self.heading_text = []
        if tag == "table":
            class_name = attrs.get("class", "")
            if "wikitable" in class_name:
                self.in_table = True
                self.table_depth = 1
                self.table_class = class_name
                self.current_table = {"section": self.current_section, "rows": []}
            elif self.in_table:
                self.table_depth += 1
        elif self.in_table and tag == "tr":
            self.in_row = True
            self.current_row = []
        elif self.in_row and tag in {"th", "td"}:
            self.in_cell = True
            self.current_cell = []

    def handle_endtag(self, tag):
        if self.in_heading and tag == self.heading_level:
            text = clean(" ".join(self.heading_text))
            text = re.sub(r"\[edit\].*$", "", text).strip()
            if text:
                self.current_section = text
            self.in_heading = False
            self.heading_level = None
        if self.in_cell and tag in {"th", "td"}:
            self.current_row.append(clean(" ".join(self.current_cell)))
            self.current_cell = None
            self.in_cell = False
        elif self.in_row and tag == "tr":
            if self.current_row:
                self.current_table["rows"].append(self.current_row)
            self.current_row = None
            self.in_row = False
        elif self.in_table and tag == "table":
            self.table_depth -= 1
            if self.table_depth == 0:
                self.tables.append(self.current_table)
                self.current_table = None
                self.in_table = False

    def handle_data(self, data):
        if self.in_heading:
            self.heading_text.append(data)
        if self.in_cell:
            self.current_cell.append(data)


def clean(value):
    return re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()


def height_m(value):
    match = re.search(r"(\d+(?:\.\d+)?)\s*m\b", value)
    return float(match.group(1)) if match else None


def coords(value):
    matches = re.findall(r"(-?\d{1,3}\.\d+)\s*;\s*(-?\d{1,3}\.\d+)", value)
    if not matches:
        return None, None
    lat, lng = matches[0]
    return float(lat), float(lng)


def normalize_type(primary_use, construction_type):
    combined = f"{primary_use} {construction_type}".upper()
    if "CHIMNEY" in combined:
        return "CHIMNEY"
    if "SKYSCRAPER" in combined or "BUILDING" in combined or "OFFICE" in combined or "RESIDENTIAL" in combined:
        return "BUILDING"
    if "TOWER" in combined and "COMMUNICATION" in combined:
        return "TOWER_COMMUNICATION"
    if "MAST" in combined and "COMMUNICATION" in combined:
        return "MAST_COMMUNICATION"
    if "MAST" in combined:
        return "MAST"
    if "TOWER" in combined:
        return "TOWER"
    return "OTHER"


def parse_tables(html):
    parser = WikiTableParser()
    parser.feed(html)
    records = []
    wanted_sections = {
        "Structures taller than 300 metres",
        "Structures 250 to 300 metres tall",
        "Structures 200 to 250 metres tall",
        "Structures 150 to 200 metres tall",
    }
    for table in parser.tables:
        if table["section"] not in wanted_sections or not table["rows"]:
            continue
        header = [clean(h).lower() for h in table["rows"][0]]
        for row in table["rows"][1:]:
            if len(row) < 2:
                continue
            item = {header[i]: row[i] for i in range(min(len(header), len(row)))}
            h = height_m(item.get("pinnacle height", ""))
            if h is None:
                continue
            lat, lng = coords(item.get("coordinates", ""))
            primary_use = item.get("primary use") or item.get("primary use ", "")
            construction_type = item.get("construction type") or item.get("construction type ", "")
            records.append(
                {
                    "section": table["section"],
                    "name": item.get("name", ""),
                    "height_m": h,
                    "year": item.get("year", ""),
                    "primary_use": primary_use,
                    "town": item.get("town", ""),
                    "construction_type": construction_type,
                    "lat": lat,
                    "lng": lng,
                    "type": normalize_type(primary_use, construction_type),
                    "remarks": item.get("remarks", ""),
                    "source": URL,
                }
            )
    return records


def write_outputs(records):
    OUT_DIR.mkdir(exist_ok=True)
    json_path = OUT_DIR / "uk_tallest_structures_wikipedia.json"
    csv_path = OUT_DIR / "uk_tallest_structures_wikipedia.csv"
    json_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    return json_path, csv_path


def main():
    request = urllib.request.Request(URL, headers={"User-Agent": "highpoints-data-import/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        html = response.read().decode("utf-8")
    records = parse_tables(html)
    if not records:
        raise SystemExit("No records parsed")
    json_path, csv_path = write_outputs(records)
    print(f"records: {len(records)}")
    print(f"json: {json_path}")
    print(f"csv: {csv_path}")
    for record in sorted(records, key=lambda item: item["height_m"], reverse=True)[:15]:
        print(f"{record['height_m']}m {record['type']} {record['name']} {record['lat']},{record['lng']}")


if __name__ == "__main__":
    main()
