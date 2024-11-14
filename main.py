import pymupdf
import re
import json
import argparse

parser = argparse.ArgumentParser(
    prog="ToC filtering",
    description="Track and manage your tasks",
)

parser.add_argument("filename")
args = parser.parse_args()

pattern = (
    r"(\d[\d.]*)\s+(.*)"  # separates hierarchical levels (group(1)) and text (group(2))
)


def is_valid_chapter(chapter, dots):
    chapter_number = chapter.group(1)
    return chapter_number.count(".") == dots or (
        chapter_number.count(".") == dots + 1 and chapter_number[-1] == "."
    )


def toc_rec(lst, dots=1):
    if not lst:
        return {}

    dct = {}
    start, id = None, None

    for idx, (lvl, title, page) in enumerate(lst):
        chapter = re.search(pattern, title)

        if chapter and is_valid_chapter(chapter, dots):
            # Handles subsections for previous chapter if necessary
            if start is not None:
                subsections = toc_rec(lst[start + 1 : idx], dots + 1)
                if subsections:
                    dct[id]["subsections"] = subsections

            # Updates the start and current chapter ID
            start, id = idx, chapter.group(1)

            # Stores the chapter information
            dct[id] = {"title": chapter.group(2)}

    # Handles subsections for the last chapter
    if start is not None:
        subsections = toc_rec(lst[start + 1 :], dots + 1)
        if subsections:
            dct[id]["subsections"] = subsections

    return dct


def toc_sec_prep(tbl, pdf):  # toc sections preparation
    sections = dict.fromkeys([str(k) for k in range(1, len(tbl) + 1)], str())

    idx = 0
    flag = False
    for page in pdf:
        text = page.get_text()
        if "ГЛАВА" in text and tbl[str(idx + 1)]["title"].upper() in text.replace(
            "\n", ""
        ):
            idx += 1
            sections[str(idx)] += text
            flag = True

        elif flag is True:
            sections[str(idx)] += text

    for _ in sections.keys():
        sections[_] = sections[_].strip().replace("\n \n \n", "")
    return sections


def toc_text_rec(tbl, text):
    start, id = None, 0
    keys = list(tbl.keys())

    while id <= len(keys):
        if start is not None:
            if "subsections" not in tbl[keys[id - 1]]:
                subtext = text[start : text.find(keys[id]) if id < len(keys) else None]
                title = tbl[keys[id - 1]]["title"].split()
                title = "".join(
                    [
                        rf"\s+{title[_]}" if _ > 0 else title[_]
                        for _ in range(len(title))
                    ]
                )
                subtext = re.sub(rf"\s*{title}\s*", "", subtext, flags=re.IGNORECASE)

                tbl[keys[id - 1]]["text"] = subtext
                tbl[keys[id - 1]]["length"] = len(subtext)
            else:
                tbl[keys[id - 1]]["subsections"] = toc_text_rec(
                    tbl[keys[id - 1]]["subsections"],
                    text[start : text.find(keys[id]) if id < len(keys) else None],
                )

        if id < len(keys):
            start = text.find(keys[id]) + len(keys[id])
        id += 1

    return tbl


def toc_text(tbl, pdf):  # here, tbl is toc and pdf is doc
    sections = toc_sec_prep(tbl, pdf)  # '1': {}, '2': {}, ...
    for key in sections.keys():
        if "sections" not in tbl[key].keys():
            # text = "".join(sections[key])
            text = sections[key].replace(f"ГЛАВА {key}", "")
            for _ in tbl[key]["title"].split():
                text = text.replace(_.upper(), "")
            text = text.strip(" \n")
            tbl[key]["text"] = text
            tbl[key]["length"] = len(text)

        else:
            tbl[key]["sections"] = toc_text_rec(tbl[key]["sections"], sections[key])
    return tbl


def main():
    doc = pymupdf.open(args.filename)
    toc_raw = doc.get_toc()  # raw table of contents
    out_file = open("structure.json", "w")  # output file 'structure.json'
    chapters = list(
        filter(lambda x: "Глава" in x[1][1], enumerate(toc_raw))
    )  # filters chapters for "Глава"

    toc = {
        re.findall(r"\d+", chapters[_][1][1])[0]: {
            "title": toc_raw[chapters[_][0] + 1][1],
            **(
                {"sections": toc_res}
                if (
                    toc_res := toc_rec(
                        toc_raw[chapters[_][0] : chapters[_ + 1][0]]
                        if _ < len(chapters) - 1
                        else toc_raw[chapters[_][0] :]
                    )
                )
                else {}
            ),
        }
        for _ in range(len(chapters))
    }

    toc = toc_text(toc, doc)

    json.dump(toc, out_file, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
