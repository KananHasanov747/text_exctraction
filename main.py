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

doc = pymupdf.open(args.filename)
doc = doc.get_toc()
out_file = open("structure.json", "w")
chapters = list(filter(lambda x: "Глава" in x[1][1], enumerate(doc)))


def toc_rec(lst, dots=1):
    if not lst:
        return {}
    dct = dict()
    pattern = r"(\d[\d.]*)\s+(.*)"
    start, id = None, None
    for content in enumerate(lst):
        idx, (lvl, title, page) = content
        chapter = re.search(pattern, title)
        if chapter and (
            chapter.group(1).count(".") == dots
            or (chapter.group(1).count(".") == dots + 1 and chapter.group(1)[-1] == ".")
        ):
            if start:
                subsections = toc_rec(lst[start + 1 : idx], dots + 1)
                if subsections:
                    dct[id]["subsections"] = subsections
            start, id = idx, chapter.group(1)
            dct[id] = {
                "title": chapter.group(2),
            }

    subsections = toc_rec(lst[start + 1 :], dots + 1) if start else None
    if subsections:
        dct[id]["subsections"] = subsections
    return dct


def main():
    toc = {
        re.findall(r"\d+", chapters[_][1][1])[0]: {
            "title": doc[chapters[_][0] + 1][1],
            "sections": toc_rec(
                doc[chapters[_][0] : chapters[_ + 1][0]]
                if _ < len(chapters) - 1
                else doc[chapters[_][0] :]
            ),
        }
        for _ in range(len(chapters))
    }

    json.dump(toc, out_file, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
