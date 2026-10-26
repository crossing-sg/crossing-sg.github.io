"""Generate desktop wireframes (1440 px wide) as SVG files that import into Figma
with named layers (each id becomes a layer name). Run: python make_wireframes.py"""
import os
from xml.sax.saxutils import escape

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wireframes")
FONT = "Inter, Arial, sans-serif"
INK, MID, SOFT, LINE, FILL, MAPBG, ROAD = "#1A1A1A", "#6B6B6B", "#9E9E9E", "#D6D6D6", "#EFEFEF", "#F3F3F1", "#DCDCDC"
W = 1440


class Frame:
    def __init__(self, name, h=1024):
        self.name, self.h, self.parts, self._ids = name, h, [], {}

    def uid(self, s):
        n = self._ids.get(s, 0)
        self._ids[s] = n + 1
        return escape(s if n == 0 else f"{s} {n + 1}", {'"': "&quot;"})

    def add(self, s):
        self.parts.append(s)

    def group(self, name):
        self.add(f'<g id="{self.uid(name)}">')

    def end(self):
        self.add("</g>")

    def rect(self, x, y, w, h, fill=FILL, stroke="none", sw=1, rx=6, name="Rectangle", dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.add(f'<rect id="{self.uid(name)}" x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{d}/>')

    def text(self, x, y, s, size=15, weight=400, fill=INK, anchor="start"):
        self.add(f'<text id="{self.uid(s[:40])}" x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}">{escape(s)}</text>')

    def lines(self, x, y, rows, size=15, weight=400, fill=INK, gap=None):
        gap = gap or round(size * 1.5)
        for i, s in enumerate(rows):
            self.text(x, y + i * gap, s, size, weight, fill)
        return y + len(rows) * gap

    def line(self, x1, y1, x2, y2, stroke=ROAD, sw=10, name="Line", dash=None, cap="butt"):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.add(f'<line id="{self.uid(name)}" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{stroke}" stroke-width="{sw}" stroke-linecap="{cap}"{d}/>')

    def poly(self, pts, stroke, sw=3, name="Route", dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        p = " ".join(f"{a},{b}" for a, b in pts)
        self.add(f'<polyline id="{self.uid(name)}" points="{p}" fill="none" stroke="{stroke}" stroke-width="{sw}" stroke-linejoin="round" stroke-linecap="round"{d}/>')

    def circle(self, x, y, r, fill=INK, stroke="none", sw=1, name="Point"):
        self.add(f'<circle id="{self.uid(name)}" cx="{x}" cy="{y}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')

    def placeholder(self, x, y, w, n=3, gap=18):
        self.group("Text placeholder")
        for i in range(n):
            self.rect(x, y + i * gap, w if i < n - 1 else int(w * 0.62), 10, "#E2E2E2", rx=4, name="Placeholder line")
        self.end()

    def button(self, x, y, label, primary=True, w=None, h=44, size=15):
        w = w or int(len(label) * size * 0.58 + 48)
        self.group(f"Button / {label}")
        self.rect(x, y, w, h, INK if primary else "#FFFFFF", INK, 1.5, 6, "Button background")
        self.text(x + w / 2, y + h / 2 + size * 0.35, label, size, 600, "#FFFFFF" if primary else INK, "middle")
        self.end()
        return x + w

    def checkbox(self, x, y, label, on=True, radio=False):
        self.group(f"{'Radio' if radio else 'Checkbox'} / {label}")
        if radio:
            self.circle(x + 8, y - 5, 8, "#FFFFFF", INK, 1.5, "Radio outline")
            if on:
                self.circle(x + 8, y - 5, 4, INK, name="Radio dot")
        else:
            self.rect(x, y - 13, 16, 16, INK if on else "#FFFFFF", INK, 1.5, 3, "Box")
            if on:
                self.poly([(x + 4, y - 5), (x + 7, y - 2), (x + 12, y - 9)], "#FFFFFF", 2, "Check")
        self.text(x + 26, y, label, 14)
        self.end()

    def nav(self, active):
        self.group("Navigation bar")
        self.rect(0, 0, W, 72, "#FFFFFF", rx=0, name="Bar background")
        self.line(0, 72, W, 72, LINE, 1, "Bar divider")
        # Class topnav pattern with the links aligned to the right, active link filled
        items = ["Home", "Map", "Propose", "Methodology", "About"]
        x = W - 40 - sum(int(len(i) * 9.6) + 40 for i in items)
        for item in items:
            on = item == active
            w = int(len(item) * 9.6) + 36
            if on:
                self.rect(x, 18, w, 38, INK, rx=0, name="Active link background")
            self.text(x + w / 2, 43, item, 16, 600 if on else 400, "#FFFFFF" if on else INK, "middle")
            x += w + 4
        self.end()

    def map_base(self, x, y, w, h, seed=0, name="Map background"):
        self.group(name)
        self.rect(x, y, w, h, MAPBG, rx=0, name="Map canvas")
        self.add(f'<clipPath id="clip{self.uid("c")}"><rect x="{x}" y="{y}" width="{w}" height="{h}"/></clipPath>')
        for i, (a, b) in enumerate([(0.12, 0.03), (0.45, -0.02), (0.78, 0.04)]):
            self.line(x + w * a, y, x + w * (a + b), y + h, ROAD, 12 if i == 1 else 8, "Road")
        for a, b in [(0.22, 0.05), (0.58, -0.03), (0.86, 0.02)]:
            self.line(x, y + h * a, x + w, y + h * (a + b), ROAD, 9, "Road")
        self.end()

    def card(self, x, y, w, h, name="Card"):
        self.rect(x, y, w, h, "#FFFFFF", LINE, 1, 8, name)

    def svg(self):
        body = "\n".join(self.parts)
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{self.h}" viewBox="0 0 {W} {self.h}">\n'
                f'<rect id="Page background" width="{W}" height="{self.h}" fill="#FFFFFF"/>\n{body}\n</svg>\n')


def story_frame(fname, step, title, body, draw_map, link_label):
    f = Frame(fname)
    f.nav("Home")
    f.map_base(0, 72, W, 952)
    draw_map(f)
    f.group("Story card")
    f.card(80, 200, 440, 420, "Card background")
    f.text(112, 248, f"STEP {step} OF 5", 12, 600, MID)
    y = f.lines(112, 290, title, 28, 700, INK, 36)
    y = f.lines(112, y + 14, body, 15, 400, "#3A3A3A", 24)
    f.text(112, 590, link_label, 14, 600, INK)
    f.end()
    f.group("Scroll progress")
    for i in range(5):
        f.circle(1380, 420 + i * 26, 5, INK if i == step - 1 else "#FFFFFF", INK, 1.5, "Progress dot")
    f.end()
    return f


def legend(f, x, y, title, rows, swatch="line"):
    f.group(f"Legend / {title}")
    f.card(x, y, 260, 40 + 26 * len(rows), "Legend background")
    f.text(x + 16, y + 26, title, 12, 600, MID)
    for i, (c, label) in enumerate(rows):
        yy = y + 52 + i * 26
        if swatch == "line":
            f.line(x + 16, yy - 5, x + 46, yy - 5, c, 6, "Swatch")
        else:
            f.circle(x + 26, yy - 5, 6, c, "#FFFFFF", 1.5, "Swatch")
        f.text(x + 58, yy, label, 13)
    f.end()


def build():
    frames = []

    # 01 Home hero
    f = Frame("01_Home_-_Hero")
    f.nav("Home")
    f.group("Hero image")
    f.rect(0, 72, W, 600, "#4A4A4A", rx=0, name="Photo placeholder (asset/hero.jpg, zebra crossing, dark wash)")
    f.line(260, 72, 520, 672, "#5E5E5E", 70, "Zebra stripe")
    f.line(460, 72, 720, 672, "#5E5E5E", 70, "Zebra stripe")
    f.line(660, 72, 920, 672, "#5E5E5E", 70, "Zebra stripe")
    f.text(1410, 640, "Photo: Myznik Egor, Unsplash", 11, 400, "#DDDDDD", "end")
    f.end()
    f.group("Hero text")
    f.text(720, 250, "PEDESTRIAN CROSSINGS IN SINGAPORE", 12, 700, "#FFFFFF", "middle")
    f.text(720, 318, "Where residents want to cross the road", 52, 700, "#FFFFFF", "middle")
    f.text(720, 362, "Crowdsourced crossing proposals and pedestrian detours in Singapore", 22, 400, "#FFFFFF", "middle")
    f.text(720, 410, "Residents mark where a new crossing is needed. Their proposals are compared with the walking", 16, 400, "#FFFFFF", "middle")
    f.text(720, 436, "detours and crossing gaps of the existing pedestrian network across Singapore.", 16, 400, "#FFFFFF", "middle")
    f.group("Button / Propose a crossing")
    f.rect(522, 478, 190, 46, "#FFFFFF", "#FFFFFF", 1.5, 6, "Button background")
    f.text(617, 507, "Propose a crossing", 15, 600, INK, "middle")
    f.end()
    f.group("Button / Explore the map")
    f.rect(728, 478, 190, 46, "none", "#FFFFFF", 1.5, 6, "Button outline")
    f.text(823, 507, "Explore the map", 15, 600, "#FFFFFF", "middle")
    f.end()
    f.end()
    f.group("Summary cards")
    cards = [("353", ["pedestrian accidents outside", "crossings in 2024, up 23%"], "Singapore Police Force (2025)"),
             ("XXX", ["proposals from residents", "XX road segments shown"], "Live count"),
             ("DD Mon", ["last proposal received"], "Updated automatically")]
    for i, (num, lab, src) in enumerate(cards):
        cx = 202 + i * 352
        f.group(f"Stat card {i + 1}")
        f.card(cx, 612, 332, 180, "Card background")
        f.text(cx + 24, 672, num, 36, 700)
        f.lines(cx + 24, 706, lab, 15, 400, INK, 22)
        f.text(cx + 24, 772, src, 12, 400, MID)
        f.end()
    f.end()
    f.group("Scroll hint")
    f.text(720, 850, "Scroll to read the story", 13, 500, MID, "middle")
    f.poly([(712, 866), (720, 874), (728, 866)], MID, 2, "Chevron")
    f.end()
    frames.append(f)

    # 02 Story: accidents
    def m_incidents(f):
        f.group("Layer / Reported fatal cases")
        for x, y in [(860, 300), (1010, 520), (1120, 410), (930, 700), (1240, 610)]:
            f.circle(x, y, 9, "#C62828", "#FFFFFF", 2, "Case point")
        f.end()
        legend(f, 1100, 860, "REPORTED FATAL CASES", [("#C62828", "2017 to 2024, news and court")], "dot")
    frames.append(story_frame("02_Home_-_Step_1_Reported_cases", 1,
        ["Reported fatal cases,", "2017 to 2024"],
        ["News and court reports describe five fatal", "cases. Official statistics do not record", "where accidents happen.", "",
         "Two cases happened at signalised crossings.", "Points mark the road or junction named in", "the report, not the exact spot."], m_incidents, "Sources for each case  >"))

    # 03 Story: crossing gap
    def m_gap(f):
        f.group("Layer / Crossing gap")
        segs = [(640, 330, 760, 334, "#DADCE0"), (760, 334, 900, 338, "#F7D774"), (900, 338, 1060, 342, "#EE8B2B"),
                (1060, 342, 1300, 348, "#C62828"), (1300, 348, 1440, 350, "#C62828")]
        for x1, y1, x2, y2, c in segs:
            f.line(x1, y1, x2, y2, c, 10, "Segment")
        f.end()
        f.group("Layer / Existing crossings")
        for x, y in [(632, 333), (905, 339), (1062, 342)]:
            f.rect(x - 5, y - 15, 10, 30, "#00B8D9", rx=2, name="Crossing marker")
        f.end()
        f.group("Layer / Bukit Batok cases")
        for x, y, fill in [(910, 360, "#C62828"), (1066, 362, "#C62828"), (780, 560, "#C62828"), (1180, 600, "#FFFFFF"), (1185, 600, "#FFFFFF")]:
            f.circle(x, y, 9, fill, "#C62828" if fill == "#FFFFFF" else "#FFFFFF", 2, "Case point")
        f.end()
        legend(f, 1100, 800, "DISTANCE TO NEAREST CROSSING", [("#DADCE0", "Under 50 m"), ("#F7D774", "50 to 100 m"),
                                                              ("#EE8B2B", "100 to 200 m"), ("#C62828", "Over 200 m")])
    frames.append(story_frame("03_Home_-_Step_2_Bukit_Batok", 2,
        ["Reported cases in", "Bukit Batok"],
        ["Bukit Batok has the most reported cases in", "the news sample, five in total, three fatal.", "Four are within 20 m of a crossing.", "",
         "20% of road length in Bukit Batok is more", "than 200 m from a crossing (33% for", "Singapore)."], m_gap, "See all roads on the map  >"))

    # 04 Story: detour
    def m_detour(f):
        f.group("Layer / Example block")
        f.rect(700, 560, 60, 44, "#2F6DB3", rx=4, name="HDB block")
        f.text(730, 626, "Blk 121", 13, 600, INK, "middle")
        f.end()
        f.group("Layer / Routes")
        f.line(760, 570, 1080, 300, "#1A1A1A", 2, "Straight line", "8 6")
        f.poly([(760, 590), (900, 600), (1010, 600), (1060, 470), (1090, 380), (1084, 304)], "#C23B3B", 4, "Walking route")
        f.end()
        f.group("Layer / Destination")
        f.rect(1070, 280, 34, 22, "#FFFFFF", INK, 1.5, 4, "Bus stop marker")
        f.text(1087, 296, "Bus", 11, 600, INK, "middle")
        f.end()
        f.group("Distance panel")
        f.card(1100, 700, 260, 150, "Panel background")
        f.text(1120, 734, "STRAIGHT LINE", 11, 600, MID)
        f.text(1120, 762, "96 m", 22, 700)
        f.text(1240, 734, "WALKING ROUTE", 11, 600, MID)
        f.text(1240, 762, "548 m", 22, 700)
        f.line(1120, 784, 1340, 784, LINE, 1, "Divider")
        f.text(1120, 820, "Detour ratio  5.7", 16, 700)
        f.end()
    frames.append(story_frame("04_Home_-_Step_3_Detour", 3,
        ["Walking distance", "from Blk 121"],
        ["Blk 121 is 84 m from case V01. The bus stop", "opposite Blk 120 is 96 m away in a straight", "line (dashed) and 548 m on foot (red).", "",
         "Mean detour ratio of Blk 121 is 2.9. The", "mean for all HDB blocks is 1.9."], m_detour, "Look up another block  >"))

    # 05 Story: voices
    def m_voices(f):
        f.group("Layer / Resident experiences")
        for x, y in [(820, 300), (980, 450), (1150, 360), (900, 640), (1210, 690), (1060, 560)]:
            f.circle(x, y, 8, "#3C8DD0", "#FFFFFF", 2, "Experience point")
        f.end()
        f.group("Experience card")
        f.card(1000, 180, 340, 150, "Card background")
        f.text(1020, 214, "Near Bukit Batok Central", 13, 600, MID)
        f.placeholder(1020, 236, 300, 3)
        f.text(1020, 312, "Reason: stairs at the overhead bridge", 13, 500)
        f.end()
    frames.append(story_frame("05_Home_-_Step_4_Resident_voices", 4,
        ["Experiences from", "residents"],
        ["Short accounts shared through the", "proposal form. Each one is reviewed by the", "team and placed on the nearest road", "segment, never at a home address."],
        m_voices, "Read more on the map  >"))

    # 06 Story: call to action
    f = Frame("06_Home_-_Step_5_Propose")
    f.nav("Home")
    f.map_base(0, 72, W, 952)
    f.group("Layer / Proposals")
    for x1, y1, x2, y2, c in [(560, 330, 660, 333, "#9CC7E8"), (900, 338, 1000, 340, "#3C8DD0"), (1180, 345, 1280, 347, "#0B4F8F"),
                              (640, 560, 740, 566, "#3C8DD0")]:
        f.line(x1, y1, x2, y2, c, 10, "Proposal segment")
    f.end()
    f.group("Closing card")
    f.card(420, 380, 600, 300, "Card background")
    f.text(720, 440, "STEP 5 OF 5", 12, 600, MID, "middle")
    f.text(720, 488, "Propose a crossing", 30, 700, INK, "middle")
    f.lines(560, 528, ["Mark two points across a road. A segment is", "shown once it has three proposals."], 15, 400, "#3A3A3A", 24)
    f.button(512, 600, "Propose a crossing", w=200)
    f.button(728, 600, "Explore the map", False, w=200)
    f.end()
    frames.append(f)

    # 07 Map: proposals layer
    def map_page(fname, mode):
        f = Frame(fname)
        f.nav("Map")
        f.group("Side panel")
        f.rect(0, 72, 380, 952, "#FFFFFF", rx=0, name="Panel background")
        f.line(380, 72, 380, 1024, LINE, 1, "Panel divider")
        f.text(32, 124, "Explore the map", 24, 700)
        f.text(32, 168, "MAP LAYER", 11, 600, MID)
        layers = [("Crossing gap", "gap"), ("Walking detour", "detour"), ("Resident proposals", "prop")]
        for i, (lab, key) in enumerate(layers):
            f.checkbox(32, 200 + i * 30, lab, key == mode, radio=True)
        f.rect(32, 300, 316, 76, FILL, rx=6, name="Layer explanation box")
        expl = {"prop": ["Road pieces coloured by the number of", "proposals. Pieces with fewer than three", "proposals are not shown."],
                "detour": ["Blocks coloured by how much longer the", "walk is than the straight distance. 2.0", "means twice as far."]}[mode]
        f.lines(46, 324, expl, 13, 400, "#3A3A3A", 20)
        f.text(32, 410, "LEGEND", 11, 600, MID)
        rows = {"prop": [("#9CC7E8", "3 to 4 proposals"), ("#3C8DD0", "5 to 9"), ("#0B4F8F", "10 or more")],
                "detour": [("#CFE3F3", "Under 1.5"), ("#7DB0DA", "1.5 to 2.0"), ("#2F6DB3", "2.0 to 2.5"), ("#0E2F5A", "Over 2.5")]}[mode]
        for i, (c, lab) in enumerate(rows):
            f.line(32, 435 + i * 26, 62, 435 + i * 26, c, 6, "Swatch")
            f.text(74, 440 + i * 26, lab, 13)
        y0 = 560
        f.line(32, y0 - 24, 348, y0 - 24, LINE, 1, "Divider")
        f.text(32, y0, "REFERENCE POINTS (ZOOM IN TO SEE)", 11, 600, MID)
        for i, lab in enumerate(["Bus stops", "MRT exits", "Existing crossings", "Overhead bridges", "Underpasses"]):
            f.checkbox(32, y0 + 32 + i * 28, lab, i in (2, 3))
        f.line(32, 760, 348, 760, LINE, 1, "Divider")
        f.text(32, 790, "DATA", 11, 600, MID)
        f.text(32, 816, "Download aggregated data (CSV, GeoJSON)", 13, 500)
        f.text(32, 840, "How these maps are made  >", 13, 500)
        f.end()
        f.map_base(381, 72, 1059, 952)
        f.group("Search")
        f.card(412, 100, 420, 44, "Search box")
        f.text(432, 128, "Search a block, road or postal code", 14, 400, SOFT)
        f.end()
        f.group("Zoom controls")
        f.card(1380, 100, 36, 72, "Zoom background")
        f.text(1398, 128, "+", 18, 500, INK, "middle")
        f.text(1398, 162, "-", 18, 500, INK, "middle")
        f.end()
        if mode == "prop":
            f.group("Layer / Proposals")
            for x1, y1, x2, y2, c in [(520, 296, 620, 300, "#9CC7E8"), (880, 312, 980, 315, "#0B4F8F"), (1160, 330, 1260, 333, "#3C8DD0"),
                                      (860, 690, 960, 700, "#3C8DD0"), (1220, 610, 1320, 614, "#9CC7E8")]:
                f.line(x1, y1, x2, y2, c, 10, "Proposal segment")
            f.line(905, 250, 960, 380, "#C23B3B", 7, "Representative crossing line", cap="round")
            f.end()
            f.group("Segment card")
            f.card(990, 400, 380, 330, "Card background")
            f.text(1012, 436, "[Road name], segment XX", 17, 700)
            f.text(1348, 436, "x", 16, 500, MID, "middle")
            f.text(1012, 474, "PROPOSALS", 11, 600, MID)
            f.text(1012, 506, "12", 28, 700)
            f.text(1130, 474, "SUPPORT", 11, 600, MID)
            f.text(1130, 506, "34", 28, 700)
            f.text(1240, 474, "NEAREST CROSSING", 11, 600, MID)
            f.text(1240, 506, "XXX m", 28, 700)
            f.line(1012, 526, 1348, 526, LINE, 1, "Divider")
            f.text(1012, 556, "Most requested type", 12, 500, MID)
            f.text(1012, 578, "Zebra crossing (7 of 12)", 15, 600)
            f.text(1012, 606, "Most common reason", 12, 500, MID)
            f.text(1012, 628, "Stairs at the overhead bridge (5 of 12)", 15, 600)
            f.button(1012, 660, "I need a crossing here too", w=220, h=40, size=13)
            f.button(1244, 660, "Propose here", False, w=104, h=40, size=13)
            f.end()
        else:
            f.group("Layer / Blocks")
            for i, (x, y) in enumerate([(560, 200), (700, 420), (1000, 230), (1180, 500), (620, 760), (1080, 820), (860, 560)]):
                f.rect(x, y, 34, 24, ["#CFE3F3", "#7DB0DA", "#2F6DB3", "#0E2F5A"][i % 4], rx=3, name="Block")
            f.end()
            f.group("Layer / Routes of selected block")
            f.line(877, 572, 1090, 320, "#1A1A1A", 2, "Straight line", "8 6")
            f.poly([(877, 584), (960, 590), (1020, 590), (1070, 470), (1092, 330)], "#C23B3B", 4, "Walking route")
            f.line(877, 572, 700, 660, "#1A1A1A", 2, "Straight line", "8 6")
            f.poly([(860, 584), (800, 640), (720, 650), (702, 664)], "#C23B3B", 4, "Walking route")
            f.end()
            f.group("Block panel")
            f.card(1060, 560, 330, 400, "Card background")
            f.text(1082, 596, "Blk XXX [Street]", 17, 700)
            f.text(1082, 620, "Mean detour ratio X.X  (X destinations)", 13, 500, MID)
            f.line(1082, 640, 1368, 640, LINE, 1, "Divider")
            for i, (d, s, r) in enumerate([("Bus stop XXXXX", "XXX m", "X,XXX m"), ("Bus stop XXXXX", "XXX m", "XXX m"), ("MRT exit X", "XXX m", "X,XXX m")]):
                yy = 676 + i * 70
                f.text(1082, yy, d, 14, 600)
                f.text(1082, yy + 24, f"Straight {s}   Walk {r}", 13, 400, MID)
                f.rect(1082, yy + 36, 280, 6, FILL, rx=3, name="Bar track")
                f.rect(1082, yy + 36, 120 + i * 50, 6, "#C23B3B", rx=3, name="Bar value")
            f.end()
        return f
    frames.append(map_page("07_Map_-_Resident_proposals", "prop"))
    frames.append(map_page("08_Map_-_Detour_block_selected", "detour"))

    # 09 Propose form
    f = Frame("09_Propose_-_Form", 1180)
    f.nav("Propose")
    f.group("Instructions")
    f.text(80, 130, "Propose a crossing", 32, 700)
    f.text(80, 166, "Takes about two minutes. No login and no personal details are collected.", 15, 400, MID)
    f.end()
    f.map_base(80, 200, 760, 900, name="Map for marking points")
    f.group("Marked points")
    f.line(400, 470, 470, 600, "#C23B3B", 4, "Proposed crossing line", "6 5", "round")
    f.circle(400, 470, 12, "#FFFFFF", INK, 3, "Point A")
    f.text(400, 475, "A", 12, 700, INK, "middle")
    f.circle(470, 600, 12, "#FFFFFF", INK, 3, "Point B")
    f.text(470, 605, "B", 12, 700, INK, "middle")
    f.card(100, 220, 330, 44, "Map hint")
    f.text(118, 248, "Tap one side of the road, then the other", 13, 500)
    f.end()
    f.group("Form")
    x0 = 900
    f.text(x0, 230, "1  Where", 18, 700)
    f.text(x0, 258, "Point A and point B marked on [Road name]", 14, 400, MID)
    f.text(x0, 310, "2  Type of crossing", 18, 700)
    for i, lab in enumerate(["Zebra crossing", "Signalised crossing", "Overhead bridge with lift", "Underpass", "Not sure"]):
        f.checkbox(x0, 346 + i * 30, lab, i == 0, radio=True)
    f.text(x0, 530, "3  Main reason", 18, 700)
    for i, lab in enumerate(["Nearest crossing is too far", "Stairs at the overhead bridge", "Long wait at the lights",
                             "Existing crossing is not on the way", "Other"]):
        f.checkbox(x0, 566 + i * 30, lab, i == 1, radio=True)
    f.text(x0, 750, "4  Your experience (optional)", 18, 700)
    f.text(x0, 776, "Reviewed before it appears on the map. Do not include names.", 13, 400, MID)
    f.rect(x0, 790, 460, 120, "#FFFFFF", LINE, 1, 6, "Text area")
    f.text(x0 + 14, 818, "What makes crossing here difficult?", 14, 400, SOFT)
    f.text(x0 + 446, 900, "0 / 300", 12, 400, SOFT, "end")
    f.button(x0, 950, "Submit proposal", w=460, h=48)
    f.text(x0, 1030, "By submitting, you agree that the proposal is shown in aggregated form.", 12, 400, MID)
    f.end()
    frames.append(f)

    # 10 Thank you
    f = Frame("10_Propose_-_Submitted")
    f.nav("Propose")
    f.group("Confirmation")
    f.circle(720, 260, 36, FILL, name="Icon background")
    f.poly([(704, 260), (716, 272), (738, 248)], INK, 4, "Check icon")
    f.text(720, 350, "Thank you, your proposal is recorded", 32, 700, INK, "middle")
    f.text(720, 392, "[Road name], segment XX", 16, 500, MID, "middle")
    f.card(470, 430, 500, 150, "Progress card")
    f.text(720, 474, "This segment now has 2 proposals", 18, 700, INK, "middle")
    for i in range(3):
        f.rect(610 + i * 76, 498, 68, 10, INK if i < 2 else "#E2E2E2", rx=5, name="Progress step")
    f.text(720, 546, "One more proposal and it appears on the public map.", 14, 400, MID, "middle")
    x = f.button(500, 620, "Share this link", w=210)
    f.button(x + 20, 620, "See the map", False, w=210)
    f.text(720, 720, "Propose another crossing", 14, 600, INK, "middle")
    f.end()
    frames.append(f)

    # 11 Methodology
    f = Frame("11_Methodology", 1300)
    f.nav("Methodology")
    f.group("Page contents")
    f.text(80, 140, "Methodology", 36, 700)
    f.group("Table of contents")
    for i, lab in enumerate(["Data sources", "Crossing gap", "Walking detour", "Resident proposals", "Moderation and privacy", "Limits", "Download"]):
        f.text(80, 210 + i * 34, lab, 15, 600 if i == 0 else 400, INK if i == 0 else MID)
    f.end()
    secs = [("Data sources", 4), ("Crossing gap", 3), ("Walking detour", 3), ("Resident proposals", 3), ("Moderation and privacy", 3), ("Limits", 3)]
    y = 210
    for title, n in secs:
        f.group(f"Section / {title}")
        f.text(400, y, title, 22, 700)
        if title == "Walking detour":
            f.rect(400, y + 20, 520, 60, FILL, rx=6, name="Formula box")
            f.text(660, y + 58, "Detour ratio = walking distance / straight distance", 15, 600, INK, "middle")
            f.placeholder(400, y + 104, 860, n)
            y += 104 + n * 18 + 50
        else:
            f.placeholder(400, y + 28, 860, n)
            y += 28 + n * 18 + 50
        f.end()
    f.group("Section / Download")
    f.text(400, y, "Download", 22, 700)
    for i, lab in enumerate(["Crossing gap segments (GeoJSON)", "Detour by block (CSV)", "Proposals by segment, aggregated (CSV)"]):
        f.card(400 + i * 290, y + 24, 270, 70, "Download card")
        f.text(420 + i * 290, y + 66, lab, 13, 600)
    f.end()
    f.end()
    frames.append(f)

    # 12 About
    f = Frame("12_About")
    f.nav("About")
    f.group("Page contents")
    f.text(80, 140, "About", 36, 700)
    f.placeholder(80, 180, 700, 3)
    f.text(80, 290, "Team", 22, 700)
    for i, name in enumerate(["Gangsar Dwi Saputro", "Xia Ruize", "Yuan Zhiyi"]):
        f.circle(140 + i * 300, 380, 48, FILL, name="Photo placeholder")
        f.text(200 + i * 300, 372, name, 16, 600)
        f.text(200 + i * 300, 396, "Role", 13, 400, MID)
    f.text(80, 500, "Course", 22, 700)
    f.text(80, 532, "DEP5118 Community Data Gathering and Visualization, National University of Singapore", 15, 400, "#3A3A3A")
    f.text(80, 610, "Management plan", 22, 700)
    for i, (k, v) in enumerate([("Proposals", "Saved automatically, checked by the team every week"),
                                ("Experiences", "Shown only after review"), ("Network data", "Updated with each LTA DataMall release"),
                                ("Code", "Open source on GitHub")]):
        f.text(80, 650 + i * 32, k, 15, 600)
        f.text(260, 650 + i * 32, v, 15, 400, "#3A3A3A")
    f.text(80, 830, "Contact the team  >", 15, 600)
    f.end()
    frames.append(f)

    # 13 Review queue (Google Sheet)
    f = Frame("13_Review_-_Google_Sheet_team_only")
    f.group("Sheet window")
    f.rect(0, 0, W, 56, FILL, rx=0, name="Sheet toolbar")
    f.text(24, 36, "Crossing proposals (team only)", 16, 600)
    f.text(1416, 36, "Shared with 3 team members", 13, 400, MID, "end")
    f.group("Tabs")
    for i, lab in enumerate(["proposals", "experiences", "support"]):
        f.rect(24 + i * 140, 980, 130, 32, "#FFFFFF" if i == 1 else FILL, LINE, 1, 4, "Tab")
        f.text(89 + i * 140, 1001, lab, 13, 600 if i == 1 else 400, INK, "middle")
    f.end()
    cols = [("received", 140), ("seg_id", 100), ("road", 220), ("type", 170), ("reason", 240), ("text", 380), ("status", 140)]
    x = 24
    for c, w in cols:
        f.rect(x, 80, w, 36, FILL, LINE, 1, 0, "Header cell")
        f.text(x + 10, 103, c, 13, 600)
        x += w
    rows = [("pending", "#F7D774"), ("approved", "#BFE3C8"), ("pending", "#F7D774"), ("rejected", "#F3C1C1"), ("approved", "#BFE3C8")]
    for r, (st, col) in enumerate(rows):
        x = 24
        for j, (c, w) in enumerate(cols):
            f.rect(x, 116 + r * 40, w, 40, col if c == "status" else "#FFFFFF", LINE, 1, 0, "Cell")
            if c == "status":
                f.text(x + 10, 141 + r * 40, st, 13, 600)
            elif c == "text":
                f.rect(x + 10, 132 + r * 40, w - 60, 8, "#E2E2E2", rx=4, name="Text placeholder")
            else:
                f.text(x + 10, 141 + r * 40, "xxxx", 13, 400, MID)
            x += w
    f.card(24, 380, 560, 120, "Note")
    f.lines(44, 416, ["Experiences appear on the map only when status is approved.",
                      "Proposals are counted at once, and rejected rows are removed",
                      "from the count the next time the map loads."], 13, 400, "#3A3A3A", 22)
    f.end()
    frames.append(f)

    os.makedirs(OUT, exist_ok=True)
    for fr in frames:
        with open(os.path.join(OUT, fr.name + ".svg"), "w", encoding="utf-8") as fh:
            fh.write(fr.svg())
    with open(os.path.join(OUT, "index.html"), "w", encoding="utf-8") as fh:
        fh.write("<!doctype html><meta charset='utf-8'><title>Wireframes</title><body style='margin:0;background:#888;font-family:Arial'>"
                 + "".join(f"<h3 style='color:#fff;padding:24px 24px 0'>{fr.name}</h3><img src='{fr.name}.svg' style='width:100%;display:block'>" for fr in frames)
                 + "</body>")
    print("\n".join(fr.name for fr in frames))


if __name__ == "__main__":
    build()
