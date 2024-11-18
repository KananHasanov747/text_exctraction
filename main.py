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


def is_valid_chapter(level, dots):
    return level.count(".") == dots or (
        level.count(".") == dots + 1 and level[-1] == "."
    )


def toc_rec(lst, dots=1):
    if not lst:
        return {}

    dct = {}
    start, id = None, None

    for idx, (lvl, title, page) in enumerate(lst):
        chapter = re.search(
            r"""
            (\d[\d.]*) # returns the 'hierarchical level' (group(1))
            \s+ # checks the whitespace between 'level' and 'title'
            (.*) # returns the 'title' (group(2))
            """,
            title,
            re.VERBOSE,
        )

        if chapter and is_valid_chapter(chapter.group(1), dots):
            # Handles subsections for previous chapter if necessary
            if start is not None:
                subsections = toc_rec(
                    lst[start + 1 : idx if idx < len(lst) else None], dots + 1
                )
                if subsections:
                    dct[id]["subsections"] = subsections

            # Updates the start and current chapter ID
            start, id = idx, chapter.group(1)

            # Stores the chapter information
            dct[id] = {"title": chapter.group(2)}

    return dct


def toc_sec_prep(tbl, pdf):  # toc sections preparation
    sections = dict.fromkeys([str(k) for k in range(1, len(tbl) + 1)], str())

    idx = 0
    flag = False
    for page in pdf:
        text = page.get_text()
        if re.search(
            rf'''
                ^(
                ГЛАВА # checks if the text starts with "ГЛАВА"
                \s # checks if there's a whitespace
                \d+ # checks the number
                \s+ # checks if there's a whitespace
                {tbl[str(idx + 1)]['title'].replace(' ', r'\s+')} # checks the title's name
                )
            ''',
            text,
            re.IGNORECASE | re.MULTILINE | re.VERBOSE,
        ):
            idx += 1
            sections[str(idx)] += text
            flag = True

        elif flag is True:
            sections[str(idx)] += text

    for _ in sections.keys():
        sections[_] = sections[_].strip().replace(" \n \n \n", "")
    return sections


def toc_text_rec(tbl, text):
    start, id = None, 0
    keys = list(tbl.keys())

    while id <= len(keys):
        if start is not None:
            if "subsections" not in tbl[keys[id - 1]]:
                subtext = text[start : text.find(keys[id]) if id < len(keys) else None]
                title = tbl[keys[id - 1]]["title"].replace(" ", r"\s+")
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
            # start = re.search(keys[id], text).end()
        id += 1

    return tbl


def toc_text(tbl, pdf):  # here, tbl is toc and pdf is doc
    sections = toc_sec_prep(tbl, pdf)  # '1': {}, '2': {}, ...
    for key in sections.keys():
        if "sections" not in tbl[key].keys():
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
    chapters = [
        (_, x) for _, x in enumerate(toc_raw) if "Глава" in x[1]
    ]  # filters chapters for "Глава" -> [(1, [1, 'Глава 1', 14]), (30, [1, 'Глава 2', 27]), ...]

    toc = {
        re.search(r"\d+", start[1][1]).group(): {
            "title": toc_raw[start[0] + 1][1],
            **(
                {"sections": toc_res}
                if (toc_res := toc_rec(toc_raw[start[0] : end[0]]))
                else {}
            ),
        }
        for start, end in zip(chapters, chapters[1:] + [(None,)])
    }

    toc = toc_text(toc, doc)

    json.dump(toc, out_file, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
