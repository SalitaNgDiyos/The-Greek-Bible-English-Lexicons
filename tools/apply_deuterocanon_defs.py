#!/usr/bin/env python3
"""Apply full multi-book Deuterocanon definitions (30 entries + grammar polish) to GBL-EPV."""
import glob
import os
import re
import sqlite3
import zipfile

OUT_TAG = "2026-11-23_0645"
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
    "G11259": [
        "1) Dositheus, the priest and Levite who brought the Greek letter of Purim to Egypt in the fourth year of Ptolemy and Cleopatra (Esth 10:3, Greek addition).",
        "2) Dositheus, an officer under Judas Maccabaeus who, together with Sosipater, captured the garrison of Timotheus and later captured Timotheus himself (2 Macc 12:19, 24); also a strong horseman of Bacenor's troop who seized Gorgias by his cloak and was wounded by a Thracian horseman (2 Macc 12:35).",
        "3) Dositheus son of Drimylus, a Jew by birth who later abandoned the ancestral law and customs, and who saved King Ptolemy IV Philopator by moving him out of his tent before Theodotus's assassination attempt (3 Macc 1:3).",
    ],
    "G11258": [
        "1) Cleopatra, queen and wife of King Ptolemy, named in the colophon dating the Greek translation of Esther (Esth 10:3, Greek addition).",
        "2) Cleopatra Thea, daughter of King Ptolemy VI Philometor of Egypt, given in marriage first to Alexander Balas at Ptolemais (1 Macc 10:57-58) and later transferred by her father to Demetrius II (1 Macc 11:12).",
    ],
    "G11260": [
        "1) Lysimachus son of Ptolemy, of Jerusalem, named in the colophon as the translator of the Greek Book of Esther (Esth 10:3, Greek addition).",
        "2) Lysimachus, brother of the high priest Menelaus, left as deputy in the high priesthood; he plundered the temple vessels and was killed near the treasury by an outraged crowd in Jerusalem (2 Macc 4:29, 39-42).",
    ],
    "G9162": [
        "Ophir (Souphir), a renowned gold-producing region from which King Solomon's and Hiram's ships brought gold, almug wood, and precious stones (1 Kgs 10:11; 1 Chr 29:4; 2 Chr 9:10); in Tobit's canticle of the rebuilt Jerusalem, its streets are said to be paved with beryl, carbuncle, and stones of Ophir (Tob 13:17).",
    ],
    "G10443": [
        "1) Shelomith, a child of King Rehoboam and Maacah (2 Chr 11:20); also an Israelite woman (Lev 24:11) and a daughter of Zerubbabel (1 Chr 3:19).",
        "2) Shelomith (Salimoth / Assalimoth), son of Josiphiah of the clan of Bani, who returned from Babylon with Ezra along with 160 men (1 Esdras 8:36; parallel to Ezra 8:10).",
    ],
    "G10854": [
        "1) Hassenaah (Hebrew הַסְּנָאָה), a family whose sons built the Fish Gate of Jerusalem (Neh 3:3); also Senuah, father of Judah, second over the city (Neh 11:9).",
        "2) Assana, ancestor of a family of temple servants (Nethinim) whose descendants returned from Babylon with Zerubbabel (1 Esdras 5:31; parallel to Ezra 2:50).",
    ],
    "G13516": [
        "Assyria, the ancient Mesopotamian empire along the Tigris River, remembered in 4 Maccabees in connection with the fiery furnace and Daniel's companions (4 Macc 13:9; cf. 2 Kgs 15-19).",
    ],
    "G13641": [
        "Bosora (Bossora), a fortified city in Gilead captured and burned by Judas Maccabaeus during his campaign to rescue the Jews east of the Jordan (1 Macc 5:26, 36).",
    ],
    "G13657": [
        "Galatians (Gauls), the Celtic people of Asia Minor and Europe: noted for being subdued and made tributary by the Romans (1 Macc 8:2) and for a battle in Babylonia in which 8,000 Jews with 4,000 Macedonians defeated 120,000 Galatians (2 Macc 8:20).",
    ],
    "G14314": [
        "Judith, the devout, wealthy, and courageous widow of Bethulia (daughter of Merari), heroine of the Book of Judith, who prayed to God and delivered Israel by slaying the Assyrian general Holofernes (Jdt 8:1; 9:1).",
    ],
    "G14345": [
        "Kadmiel (Cadmiel), ancestor of a Levitical family that returned from Babylon with Zerubbabel and joined in overseeing the rebuilding of the temple (1 Esdras 5:26, 58; parallel to Ezra 2:40; 3:9).",
    ],
    "G14631": [
        "Media, the highland region east of Assyria and Babylonia containing Ecbatana and Rages: the setting of Tobit's family journey and Sarah's home (Tob 1:14; 3:7; 4:1; 5:6; 6:6; 14:4, 12, 14-15), part of the Medo-Persian empire under Darius (1 Esdras 3:1, 9, 14; 6:22), and the region into which King Demetrius II marched before being captured by Arsaces (1 Macc 6:56; 14:1-2).",
    ],
    "G14632": [
        "Media (variant spelling of Μηδεία), the highland region east of Assyria and Babylonia where Ecbatana and Rages lay, prominent in the narrative of Tobit (Tob 1:14; 4:1; 14:12-15) and in the campaigns of 1 Maccabees (1 Macc 6:56; 14:1-2).",
    ],
    "G14682": [
        "Moses, the great lawgiver, prophet, and deliverer of Israel: praised in Sirach as beloved of God and men, ordained by God to teach Jacob the Law (Sir 45:1, 15), and cited in 4 Maccabees as an example of devout reason mastering anger and as the mediator of the Law (4 Macc 2:17; 17:19).",
    ],
    "G15090": [
        "Zadok (Sadduk), son of Ahitub and ancestor of Ezra the scribe in the Aaronic priestly genealogy (1 Esdras 8:2; parallel to Ezra 7:2).",
    ],
    "G15284": [
        "Tarsians, the citizens of Tarsus in Cilicia, who together with the people of Mallus revolted because their cities had been given as a gift to Antiochis, concubine of King Antiochus IV Epiphanes (2 Macc 4:30).",
    ],
}

INSERT_DEF = {
    "G1695": [
        "1) Emmaus (NT), a village about sixty stadia from Jerusalem where the risen Lord appeared to two disciples (Luke 24:13).",
        "2) Emmaus (Deuterocanon), the town in the Judean plain (Emmaus-Nicopolis) where Gorgias encamped with Seleucid troops, where Judas Maccabaeus won a decisive victory (1 Macc 3:40, 57; 4:3), and which Bacchides later fortified (1 Macc 9:50).",
    ],
    "G4681": [
        "1) Spain (NT), the Iberian peninsula in western Europe, which the apostle Paul planned to visit (Rom 15:24, 28).",
        "2) Spain (Deuterocanon), noted in 1 Maccabees for the Romans' conquest of the region and its rich silver and gold mines (1 Macc 8:3).",
    ],
    "G5642": [
        "Pishon (Pheison), one of the four rivers of Eden flowing around the land of Havilah (Gen 2:11); in Sirach, Wisdom is compared to the Pishon overflowing with understanding in the days of the firstfruits (Sir 24:25).",
    ],
    "G5988": [
        "1) to deprive of, to bereave of; in the passive, to be deprived of or left destitute of (e.g. Gen 30:2; 48:11; Ps 84:11; in 2 Macc 3:29, of Heliodorus lying speechless and bereft of all hope and deliverance).",
    ],
    "G9909": [
        "1) Jeriel (OT), a chief of the tribe of Issachar, son of Tola (1 Chr 7:2).",
        "2) Jeriel (1 Esdras), a priest of the sons of Emmer who agreed to put away his foreign wife during Ezra's reform (1 Esdras 9:21; parallel to Jehiel in Ezra 10:21).",
    ],
    "G10310": [
        "1) Jeremoth / Jerimoth (OT), the name of several Benjamites, Levites, and post-exilic Israelites (1 Chr 7:7-8; 8:14; 23:23; 25:4; Ezra 10:26-27, 29).",
        "2) Jeremoth (1 Esdras), two Israelites who agreed to put away their foreign wives at Ezra's assembly — one of the sons of Elam (1 Esdras 9:27) and one of the sons of Mani (1 Esdras 9:30).",
    ],
    "G10683": [
        "1) Darius (OT), the name of Persian and Median kings in Scripture: Darius the Mede (Dan 5:31; 6:1; 9:1) and Darius I Hystaspes who authorized the rebuilding of the temple (Ezra 4-6; Hag 1:1; Zech 1:1; 1 Esdras 3-6).",
        "2) Darius III Codomannus (Deuterocanon), the last king of the Persians and Medes, defeated by Alexander the Great of Macedon who then reigned in his stead (1 Macc 1:1).",
    ],
    "G10745": [
        "Hakkatan (Akatan), father of Johanan of the sons of Azgad, who returned from Babylon with Ezra along with 110 men (Ezra 8:12; 1 Esdras 8:38).",
    ],
    "G10946": [
        "Chephirah (Capheira), one of the four Gibeonite cities later allotted to Benjamin (Josh 9:17; 18:26), whose returning exiles were numbered with those of Kiriath-jearim and Beeroth (Ezra 2:25; Neh 7:29; 1 Esdras 5:19).",
    ],
    "G11026": [
        "1) Hashabiah (OT), the name of several Levites, temple musicians, and post-exilic leaders (1 Chr 6:45; 25:3, 19; Ezra 8:19, 24; Neh 3:17; 10:11).",
        "2) Hashabiah (Asebias), a Levite of the sons of Merari who joined Ezra at the river Ahava for temple service (1 Esdras 8:47-48; parallel to Ezra 8:19).",
    ],
    "G11071": [
        "1) Jaddua (OT), a chief of the people who sealed Nehemiah's covenant (Neh 10:22) and a high priest in the Persian period (Neh 12:11, 22).",
        "2) Jaddus (1 Esdras), ancestor of a priestly family descended through a daughter of Barzillai (Pharzelaeus), excluded from the priesthood for lacking genealogical proof (1 Esdras 5:38; parallel to Ezra 2:61).",
    ],
    "G11257": [
        "1) Ptolemy (Esther), the Ptolemaic king of Egypt named with Queen Cleopatra in the colophon dating the Greek translation of Esther (Esth 10:3, Greek addition).",
        "2) Ptolemy (1-3 Maccabees), the name of several Ptolemaic kings of Egypt — including Ptolemy IV Philopator (3 Macc 1:1-7:1) and Ptolemy VI Philometor (1 Macc 1:18; 10:51-58; 11:1-18) — as well as Seleucid and Judean officials such as Ptolemy son of Dorymenes (1 Macc 3:38; 2 Macc 4:45), Ptolemy Macron (2 Macc 10:12), and Ptolemy son of Abubus (1 Macc 16:11-22).",
    ],
    "G12356": [
        "1) Kittim (1 Maccabees), Macedonia and Greece (the land of Kittim), from which Alexander son of Philip came forth to defeat Darius king of the Persians and Medes (1 Macc 1:1; cf. 1 Macc 8:5).",
        "2) Tahtim-hodshi (2 Sam 24:6, LXX Χεττιείμ Καδής), a northern border location visited during David's census.",
    ],
    "G12520": [
        "1) Charmis (Judith), son of Melchiel, one of the elders and magistrates of Bethulia alongside Uzziah and Chabris (Jdt 6:15; cf. Jdt 8:10; 10:6).",
        "2) Carchemish (OT, BDB cross-reference), the major ancient city on the Euphrates River (2 Chr 35:20; Isa 10:9; Jer 46:2).",
    ],
}


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
        new_s = transform_fn(s).replace(": 1 verses, e.g.", ": 1 verse, e.g.")
        assert new_s != s, f"{subj} unchanged!"
        assert brace_depth(new_s) == orig_depth, f"{subj} brace mismatch"
        cur.execute(
            "UPDATE content SET data=? WHERE topic_id=?",
            (new_s.encode("utf-8") if was_bytes else new_s, tid),
        )
        updated += 1

    def make_replacer(lines):
        def fn(s):
            pat = re.compile(
                r"\\pard[^\n]*\{\\plain\\f0\\fs20\\b Definition:\}\\par\r?\n"
                r"(?:\\pard[^\n]*\\li360\\fi-360[^\n]*\\par\r?\n?)+",
                re.S,
            )
            m = pat.search(s)
            assert m, "Definition block not found"
            return s[: m.start()] + make_def_block(lines) + "\n" + s[m.end() :]
        return fn

    def make_inserter(subj, lines):
        def fn(s):
            if subj == "G5642":
                s = s.replace("noun masculine}", "proper name location}", 1)
            if subj == "G5988":
                m_head = re.search(r"(\\pard[^\n]*\\fs24\\b\\cf1[^\n]*\\par\r?\n)", s)
                assert m_head, "G5988 headword not found"
                pos_line = r"\pard\sb0\sa120\li0\fi0 {\plain\f0\fs20\b Part of Speech: }{\plain\f0\fs20 verb}\par" + "\n"
                s = s[: m_head.end()] + pos_line + s[m_head.end() :]
            pat = re.compile(
                r"(\\pard[^\n]*\{\\plain\\f0\\fs20\\b (?:LSJ Definition:|BDB Definition:|Thayer Definition:|Online Bible Abridged BDB:|ISBE Definition:|OT \(LXX\) Occurrences:))"
            )
            m = pat.search(s)
            assert m, f"Insertion anchor not found in {subj}"
            return s[: m.start()] + make_def_block(lines) + "\n" + s[m.start() :]
        return fn

    for subj, lines in REPLACE_DEF.items():
        update_entry(subj, make_replacer(lines))
    for subj, lines in INSERT_DEF.items():
        update_entry(subj, make_inserter(subj, lines))

    for tid, raw in cur.execute(
        "SELECT topic_id, data FROM content WHERE data LIKE '%: 1 verses, e.g.%'"
    ).fetchall():
        was_bytes = isinstance(raw, bytes)
        s = raw.decode("utf-8", errors="replace") if was_bytes else raw
        s2 = s.replace(": 1 verses, e.g.", ": 1 verse, e.g.")
        if s2 != s:
            cur.execute(
                "UPDATE content SET data=? WHERE topic_id=?",
                (s2.encode("utf-8") if was_bytes else s2, tid),
            )

    con.commit()
    assert cur.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    stubs = cur.execute(
        "SELECT count(*) FROM content WHERE lower(data) LIKE '%occurring in the deuterocanonical books%'"
    ).fetchone()[0]
    assert stubs == 0, f"Remaining stubs: {stubs}"
    con.close()

    with zipfile.ZipFile(OUT_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(OUT_TWM, arcname=OUT_TWM)
    os.remove(OUT_TWM)
    print(f"SUCCESS: updated {updated} entries, built {OUT_ZIP} ({os.path.getsize(OUT_ZIP):,} bytes)")


if __name__ == "__main__":
    main()
