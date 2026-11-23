#!/usr/bin/env python3
"""Fix G6505 (Ωρ: Hur / Mount Hor) and 12 other proper-name homonym/dual-sense entries in GBL-EPV."""
import glob
import os
import re
import sqlite3
import zipfile

OUT_TAG = "2026-11-23_0805"
OUT_TWM = f"GBL-EPV_{OUT_TAG}.dct.twm"
OUT_ZIP = f"GBL-EPV_{OUT_TAG}.dct.zip"


def rtf_escape(text):
    out = []
    for ch in text:
        code = ord(ch)
        if ch in ("\\", "{", "}"):
            out.append("\\" + ch)
        elif code < 128:
            out.append(ch)
        elif code < 32768:
            out.append(f"\\u{code} ")
        else:
            out.append(f"\\u{code - 65536} ")
    return "".join(out)


def brace_depth(s):
    depth = 0
    i = 0
    n = len(s)
    while i < n:
        if s[i] == "\\" and i + 1 < n and s[i + 1] in ("\\", "{", "}"):
            i += 2
            continue
        if s[i] == "{":
            depth += 1
        elif s[i] == "}":
            depth -= 1
        i += 1
    return depth


def make_def_block(lines):
    parts = [r"\pard\sb0\sa120\li0\fi0 {\plain\f0\fs20\b Definition:}\par"]
    for ln in lines:
        parts.append(
            r"\pard\sb0\sa120\li360\fi-360 {\plain\f0\fs20 " + rtf_escape(ln) + r"}\par"
        )
    return "\n".join(parts)


REPLACE_DEF = {
    "G9761": (
        "proper name",
        [
            "1) Eshtemoa (location), a Levitical town in the hill country of Judah, named as founded by Ishbah of the line of Ezra (1 Chr 4:17).",
            "2) Eshtemoa the Maacathite (person), a Judahite clan head listed among the descendants of Hodiah's wife (1 Chr 4:19).",
        ],
    ),
    "G10466": (
        "proper name masculine",
        [
            "Amon (LXX Emer; Hebrew H526 אָמוֹן), governor of the city of Samaria, to whom King Ahab committed the prophet Micaiah to be kept in prison on meager rations of bread and water (1 Kgs 22:26; 2 Chr 18:25).",
        ],
    ),
}

INSERT_DEF = {
    "G6505": (
        "proper name",
        [
            "1) Hur (person; Hebrew H2354 חוּר): (a) companion of Moses and Aaron who went up the hill with them and helped hold up Moses' hands during the battle against Amalek (Exod 17:10, 12), and who was left in charge alongside Aaron to judge disputes while Moses ascended Mount Sinai (Exod 24:14); (b) son of Caleb and Ephrathah of the tribe of Judah, father of Uri, grandfather of Bezalel (chief craftsman of the Tabernacle), and ancestor of Bethlehem (Exod 31:2; 35:30; 1 Chr 2:19-20, 50; 4:1, 4; 2 Chr 1:5); (c) a Benjamite (1 Chr 7:12 Brenton, Hebrew Ir).",
            "2) Mount Hor (location; Hebrew H2023 הֹר): (a) the mountain on the border of Edom where Aaron died and was succeeded by Eleazar (Num 20:22-27; 21:4; 27:13; 33:37-41; Deut 32:50); (b) a mountain landmark on the northern border of Canaan (Num 34:7-8).",
        ],
    ),
    "G5787": (
        "proper name",
        [
            "1) Ellasar (location; Hebrew H495 אֶלָּסָר), the kingdom ruled by King Arioch, ally of Chedorlaomer in the war of the kings (Gen 14:1, 9).",
            "2) Tiglath-pileser III (person; LXX Θαγλαθφελλασαρ, tagged under this number in 2 Kgs 15:29; 16:7, 10; 2 Chr 28:20), king of Assyria who deported northern Israel and received tribute from King Ahaz of Judah.",
        ],
    ),
    "G6095": (
        "proper name",
        [
            "1) Alvah / Aliah (person; LXX Γωλα; Hebrew H5933 עַלְוָה), a chief (duke) of Edom descended from Esau (Gen 36:40; 1 Chr 1:51).",
            "2) Giloh (location; Hebrew H1542 גִּלֹה), the town in the hill country of Judah that was the home of David's counselor Ahithophel (2 Sam 15:12).",
            "3) Golan (location; Hebrew H1474 גּוֹלָן), a Levitical city of refuge in Bashan allotted to the Gershonites from Manasseh (1 Chr 6:71); also a western border landmark of Zebulun (Josh 19:11).",
        ],
    ),
    "G6126": (
        "proper name",
        [
            "1) Shelah (person; Hebrew H7956 שֵׁלָה), youngest son of Judah by Bath-shua and ancestor of the Shelanite clan (Gen 38:5, 11, 14, 26; 46:12; Num 26:20; 1 Chr 2:3; 4:21).",
            "2) Shiloh (location; Hebrew H7887 שִׁלוֹ / שִׁילֹה), the central Israelite sanctuary city in Ephraim where the Tabernacle and Ark of the Covenant stood during the days of Joshua, the Judges, Eli, and Samuel (Josh 18:1; 1 Sam 1:21, 24; 2:14; 3:21; Jer 26:6, 9 [LXX 33:6, 9]).",
        ],
    ),
    "G6130": (
        "proper name",
        [
            "1) Enan (person; Hebrew H5881 עֵינָן), father of Ahira, the leader of the tribe of Naphtali during the wilderness census and offerings (Num 1:15; 2:29; 7:78, 83; 10:27).",
            "2) Enaim (location; Hebrew H5879 עֵינַיִם), a town at the entrance to the road to Timnah where Tamar waited for Judah (Gen 38:14, 21); also Anem (1 Chr 6:73), a Levitical city in Issachar.",
        ],
    ),
    "G7339": (
        "adverb / proper name feminine",
        [
            "1) μάλα (adverb): very, exceedingly; καὶ μάλα, indeed, truly, certainly (2 Sam 14:5; 1 Kgs 1:43; 2 Kgs 4:14; Dan 10:21).",
            "2) Mahlah (proper name feminine; LXX Μαλα; Hebrew H4244 מַחְלָה): eldest of the five daughters of Zelophehad of the tribe of Manasseh, who petitioned Moses for their father's inheritance (Num 26:37 [MT 26:33]; 27:1).",
        ],
    ),
    "G7428": (
        "proper name",
        [
            "1) Rimmon the Beerothite (person; Hebrew H7417 רִמּוֹן), a Benjamite, father of Rechab and Baanah who assassinated Ish-bosheth (2 Sam 4:2, 5, 9).",
            "2) Rimmon (location): (a) Rimmon-perez, a wilderness encampment of Israel (Num 33:19-20); (b) the Rock of Rimmon in Benjamin where 600 surviving Benjamites took refuge (Judg 20:45, 47; 21:13); (c) a southern Judah/Simeon landmark (Zech 14:10).",
            "3) Rimmon (deity), the Aramean storm-god worshipped in Damascus (2 Kgs 5:18).",
        ],
    ),
    "G7448": (
        "proper name",
        [
            "1) Ai (location; Hebrew H5857 עַי), the ancient Canaanite city east of Bethel conquered by Joshua (Josh 7-8; 10:1-2; 12:9; Ezra 2:28; Neh 7:32).",
            "2) Gai / the Valley (location; Hebrew H1516 גַּיְא): Iye-abarim / the valley in Moab near Beth-peor where Israel camped and Moses was buried (Num 33:44-45; Deut 34:6), and a valley near Ibleam (2 Kgs 9:27).",
            "3) Hegai (person; LXX Γαι; Hebrew H1896 הֵגַי), eunuch of King Ahasuerus and keeper of the women in Susa, who showed favor to Esther (Esth 2:8, 14-15).",
        ],
    ),
    "G7857": (
        "proper name",
        [
            "1) Shaphan (person; Hebrew H8227 שָׁפָן), the royal scribe (secretary) of King Josiah who received and read the newly found Book of the Law to the king, and father of Ahikam, Gemariah, Elasah, and Jaazaniah (2 Kgs 22:3-14; 25:22; 2 Chr 34:8, 15-20; Jer 26:24 [LXX 33:24]; 29:3 [LXX 36:3]; 36:10-12).",
            "2) Zaphon (location; Hebrew H6829 צָפוֹן), a town in the Jordan valley allotted to the tribe of Gad (Josh 13:27).",
        ],
    ),
    "G9159": (
        "proper name",
        [
            "1) Elath (location; Hebrew H359 אֵילַת), a strategic port town on the Gulf of Aqaba (Red Sea) in Edom, near Ezion-geber (1 Kgs 9:26; 2 Kgs 16:6; 2 Chr 8:17; 26:2).",
            "2) Ailath (person; LXX Αιλαθ), a descendant listed among the sons of Lotan in the Horite genealogy (1 Chr 1:39 LXX).",
        ],
    ),
    "G9171": (
        "proper name",
        [
            "1) Tekoa (location; Hebrew H8620 תְּקוֹעַ), a town in the hill country of Judah south of Bethlehem, hometown of the prophet Amos (Jer 6:1; Amos 1:1); also Kue / Tekoa in Solomon's horse trade (1 Kgs 10:28).",
            "2) Tikvah (person; LXX Θεκουε; Hebrew H8616 תִּקְוָה): (a) father of Shallum, husband of the prophetess Huldah (2 Kgs 22:14); (b) father of Jahzeiah, who opposed Ezra's procedure regarding foreign marriages (Ezra 10:15).",
        ],
    ),
}


def set_pos(s, new_pos):
    pat = re.compile(
        r"(\\pard[^\n]*\{\\plain\\f0\\fs20\\b Part of Speech: \}\{\\plain\\f0\\fs20 )([^}]*)(\}\\par)"
    )
    m = pat.search(s)
    if m:
        return s[: m.start(2)] + rtf_escape(new_pos) + s[m.end(2) :]
    return s


def main():
    zips = sorted(z for z in glob.glob("GBL-EPV_*.dct.zip") if z != OUT_ZIP)
    assert zips, "No base GBL-EPV_*.dct.zip found!"
    base_zip = zips[-1]
    print(f"Base archive: {base_zip}")
    with zipfile.ZipFile(base_zip, "r") as zf:
        twms = [n for n in zf.namelist() if n.endswith(".twm")]
        assert twms, "No .twm inside base zip!"
        with open(OUT_TWM, "wb") as f:
            f.write(zf.read(twms[0]))

    con = sqlite3.connect(OUT_TWM)
    cur = con.cursor()
    updated = 0

    def update_entry(subj, transform_fn):
        nonlocal updated
        row = cur.execute(
            "SELECT t.id, c.data FROM topics t JOIN content c ON t.id=c.topic_id WHERE t.subject=?",
            (subj,),
        ).fetchone()
        assert row, f"{subj} not found!"
        tid, raw = row
        was_bytes = isinstance(raw, bytes)
        s = raw.decode("utf-8", errors="replace") if was_bytes else raw
        orig_depth = brace_depth(s)
        new_s = transform_fn(s)
        assert new_s != s, f"{subj} unchanged!"
        assert brace_depth(new_s) == orig_depth, f"{subj} brace mismatch"
        cur.execute(
            "UPDATE content SET data=? WHERE topic_id=?",
            (new_s.encode("utf-8") if was_bytes else new_s, tid),
        )
        updated += 1

    def make_replacer(new_pos, lines):
        def fn(s):
            s = set_pos(s, new_pos)
            pat = re.compile(
                r"\\pard[^\n]*\{\\plain\\f0\\fs20\\b Definition:\}\\par\r?\n"
                r"(?:\\pard[^\n]*\\li360\\fi-360[^\n]*\\par\r?\n?)+",
                re.S,
            )
            m = pat.search(s)
            assert m, "Definition block not found"
            return s[: m.start()] + make_def_block(lines) + "\n" + s[m.end() :]
        return fn

    def make_inserter(subj, new_pos, lines):
        def fn(s):
            s = set_pos(s, new_pos)
            pat = re.compile(
                r"(\\pard[^\n]*\{\\plain\\f0\\fs20\\b (?:LSJ Definition:|BDB Definition:|Thayer Definition:|Online Bible Abridged BDB:|ISBE Definition:|OT \(LXX\) Occurrences:))"
            )
            m = pat.search(s)
            assert m, f"Insertion anchor not found in {subj}"
            return s[: m.start()] + make_def_block(lines) + "\n" + s[m.start() :]
        return fn

    for subj, (new_pos, lines) in REPLACE_DEF.items():
        update_entry(subj, make_replacer(new_pos, lines))
    for subj, (new_pos, lines) in INSERT_DEF.items():
        update_entry(subj, make_inserter(subj, new_pos, lines))

    con.commit()
    assert cur.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    con.close()

    with zipfile.ZipFile(OUT_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(OUT_TWM, arcname=OUT_TWM)
    os.remove(OUT_TWM)
    print(f"SUCCESS: updated {updated} entries, built {OUT_ZIP} ({os.path.getsize(OUT_ZIP):,} bytes)")


if __name__ == "__main__":
    main()
