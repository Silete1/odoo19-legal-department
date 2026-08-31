{
    "name": "Legal Department - Legal Opinions",
    "summary": "الآراء والاستشارات القانونية - an issue-then-freeze advisory workflow with a precedent library",
    "description": """
Legal Department - Legal Opinions (الآراء والاستشارات القانونية)
================================================================

The advisory desk of the legal department, made into a record rather than a
Word file on somebody's laptop.

A legal opinion is not a letter and it is not a case. It is an **answer** a
department asks for - may we forfeit this tender guarantee, is this termination
lawful - and the value of the answer is entirely in its being *the* answer,
quotable months later, unchanged since the day it was signed. Three things
follow, and they are the whole design.

**An issued opinion is frozen.** The moment the approver issues it, the analysis
and the conclusion are photographed into a snapshot and the fields go read-only.
A signed opinion whose text can still be edited is worth nothing, because the
copy on the requester's desk and the copy in the system would silently diverge.

**A change is a revision, not an edit.** When the law moves or a fact was wrong,
the opinion is not reopened - a new opinion is drafted that *supersedes* the old
one, exactly as a document renews rather than mutates. The chain stays visible,
so "what did we advise then, and what do we advise now" is always answerable.

**An issued opinion is also a register entry.** Issuing allocates an outgoing
number from the correspondence register and links it back, so the same act that
freezes the artifact also books it into the صادر. The opinion is at once a
frozen precedent and a numbered line in the book.

The issued opinions form a **precedent library** - searchable, grouped by
department, and the first place a researcher looks before drafting the next one.
""",
    "version": "19.0.1.0.0",
    "category": "Services/Legal",
    "license": "LGPL-3",
    "author": "Legal Department",
    "depends": ["legal_correspondence"],
    "data": [
        "security/ir.model.access.csv",
        "security/legal_opinion_rules.xml",
        "data/legal_opinion_sequence.xml",
        "views/legal_opinion_views.xml",
        "views/legal_opinion_menus.xml",
    ],
    "installable": True,
    "application": True,
    "auto_install": False,
}
