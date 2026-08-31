"""Stamp ``o_legal_view`` onto the arch root of the legal suite's own views.

Odoo copies a view root's ``class`` attribute onto the rendered controller
(``computeViewClassName`` in ``web/static/src/views/utils.js``), which is the
framework's own mechanism for scoping a stylesheet to *these* views rather than
to every list in the database. ``legal_native.scss`` hangs entirely off that
class, so a legal module never restyles the accounting list.

Only primary views are touched. An inherited view's arch root is a ``<data>``
or an ``<xpath>``, or carries a ``position`` attribute, and none of those reach
``computeViewClassName`` - stamping one would be inert at best.

Idempotent: running it twice changes nothing. Run from the repository root::

    python scripts/legal_stamp_view_class.py [--check]
"""

import argparse
import glob
import re
import sys

CLASS = "o_legal_view"
# calendar and activity reject a `class` attribute under Odoo's RelaxNG schema.
ROOTS = ("list", "form", "kanban", "graph", "pivot")

# The arch root sits immediately inside <field name="arch" type="xml">. Match
# that opening tag rather than any <list> anywhere, so a <list> nested in a
# one2many field inside a form is left alone: it is not the controller root.
ARCH = re.compile(
    r'(<field\s+name="arch"\s+type="xml"\s*>\s*)<(' + "|".join(ROOTS) + r')(\s[^>]*?|)(/?)>',
    re.S,
)


def stamp(text):
    changed = 0

    def repl(match):
        nonlocal changed
        head, tag, attrs, selfclose = match.groups()
        if "position=" in attrs:
            return match.group(0)
        existing = re.search(r'\sclass="([^"]*)"', attrs)
        if existing:
            classes = existing.group(1).split()
            if CLASS in classes:
                return match.group(0)
            classes.append(CLASS)
            attrs = attrs[: existing.start()] + f' class="{" ".join(classes)}"' \
                + attrs[existing.end():]
        else:
            attrs = f'{attrs} class="{CLASS}"' if attrs.strip() else f' class="{CLASS}"'
        changed += 1
        return f"{head}<{tag}{attrs}{selfclose}>"

    return ARCH.sub(repl, text), changed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true",
                        help="report what would change and exit non-zero if anything would")
    args = parser.parse_args()

    total, touched = 0, []
    patterns = ["custom_addons/legal_*/views/*.xml",
                "custom_addons/legal_*/wizard/*.xml",
                "custom_addons/legal_*/report/*.xml"]
    for pattern in patterns:
        for path in sorted(glob.glob(pattern)):
            with open(path, encoding="utf-8") as handle:
                text = handle.read()
            new, count = stamp(text)
            if count:
                total += count
                touched.append((path, count))
                if not args.check:
                    with open(path, "w", encoding="utf-8", newline="") as handle:
                        handle.write(new)

    for path, count in touched:
        print(f"{count:3d}  {path}")
    print(f"{'would stamp' if args.check else 'stamped'} {total} view roots "
          f"in {len(touched)} files")
    if args.check and total:
        sys.exit(1)


if __name__ == "__main__":
    main()
