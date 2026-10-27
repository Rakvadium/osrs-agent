"""Minimal Markdown to HTML for plan reports (stdlib only).

Covers what planning answers use: #-### headings, paragraphs, bullet and
numbered lists (nested by indentation), pipe tables, horizontal rules, fenced
code, **bold**, *italic*, `code` and [links](url). Raw HTML is escaped.

A line holding only {{loadout}} or {{route}} is a placeholder: card.py puts
the loadout panels or the route maps there.
"""
import html
import re

PLACEHOLDER = re.compile(r"^\s*\{\{\s*(loadout|route)\s*\}\}\s*$")


def inline(text):
    text = html.escape(text, quote=False)
    code = []
    text = re.sub(r"`([^`]+)`", lambda m: code.append(m.group(1)) or "\x00{}\x00".format(len(code) - 1), text)
    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", lambda m: '<a href="{}">{}</a>'.format(html.escape(m.group(2)), m.group(1)), text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", text)
    text = re.sub(r"(?<!\w)_(?!\s)(.+?)(?<!\s)_(?!\w)", r"<em>\1</em>", text)
    return re.sub(r"\x00(\d+)\x00", lambda m: "<code>{}</code>".format(code[int(m.group(1))]), text)


def _table(rows):
    cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
    head, body = cells[0], [r for r in cells[2:]]
    out = ['<div class="table"><table><thead><tr>']
    out += ["<th>{}</th>".format(inline(c)) for c in head]
    out.append("</tr></thead><tbody>")
    for r in body:
        out.append("<tr>" + "".join("<td>{}</td>".format(inline(c)) for c in r) + "</tr>")
    out.append("</tbody></table></div>")
    return "".join(out)


LIST_RE = re.compile(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$")


def _list(lines):
    """Nested lists from indented '- ' / '1. ' lines; a change of marker starts a new list."""
    items = []  # [indent, tag, html]
    for line in lines:
        m = LIST_RE.match(line)
        if m:
            indent = len(m.group(1).replace("	", "    "))
            items.append([indent, "ol" if m.group(2)[0].isdigit() else "ul", inline(m.group(3))])
        elif items:
            items[-1][2] += " " + inline(line.strip())
    pos = 0

    def block(level):
        nonlocal pos
        out = []
        while pos < len(items) and items[pos][0] >= level:
            indent, tag = items[pos][0], items[pos][1]
            out.append("<{}>".format(tag))
            while pos < len(items) and items[pos][0] == indent and items[pos][1] == tag:
                text = items[pos][2]
                pos += 1
                child = block(items[pos][0]) if pos < len(items) and items[pos][0] > indent else ""
                out.append("<li>{}{}</li>".format(text, child))
            out.append("</{}>".format(tag))
        return "".join(out)

    out = []
    while pos < len(items):
        out.append(block(items[pos][0]))
    return "".join(out)


def render(markdown, slots=None):
    """HTML for `markdown`; `slots` maps placeholder names to HTML to insert."""
    slots = slots or {}
    lines = markdown.replace("\r\n", "\n").split("\n")
    out, i, used = [], 0, set()
    while i < len(lines):
        line = lines[i]
        m = PLACEHOLDER.match(line)
        if m:
            out.append(slots.get(m.group(1), ""))
            used.add(m.group(1))
            i += 1
        elif not line.strip():
            i += 1
        elif line.startswith("```"):
            j = i + 1
            while j < len(lines) and not lines[j].startswith("```"):
                j += 1
            out.append("<pre>{}</pre>".format(html.escape("\n".join(lines[i + 1:j]))))
            i = j + 1
        elif re.match(r"^#{1,4}\s", line):
            level = len(line) - len(line.lstrip("#"))
            # #, ## and ### are section headings; #### and below are subheadings.
            out.append("<h{0}>{1}</h{0}>".format(3 if level <= 3 else 4, inline(line.lstrip("#").strip())))
            i += 1
        elif re.match(r"^\s*(-{3,}|\*{3,})\s*$", line):
            out.append("<hr>")
            i += 1
        elif line.lstrip().startswith("|") and i + 1 < len(lines) and re.match(r"^\s*\|?[\s:|-]+\|[\s:|-]*$", lines[i + 1]):
            j = i
            while j < len(lines) and lines[j].lstrip().startswith("|"):
                j += 1
            out.append(_table(lines[i:j]))
            i = j
        elif LIST_RE.match(line):
            j = i
            while j < len(lines) and (LIST_RE.match(lines[j]) or (lines[j].startswith("  ") and lines[j].strip() and not PLACEHOLDER.match(lines[j]))):
                j += 1
            out.append(_list(lines[i:j]))
            i = j
        else:
            j = i
            while j < len(lines) and lines[j].strip() and not LIST_RE.match(lines[j]) and not lines[j].startswith(("#", "|", "```")) and not PLACEHOLDER.match(lines[j]):
                j += 1
            out.append("<p>{}</p>".format(inline(" ".join(l.strip() for l in lines[i:j]))))
            i = j
    return "".join(out), used
