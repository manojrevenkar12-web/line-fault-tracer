"""Finding the manual section or the past ticket that helps, for questions written the way people on a line write them:
alarm codes, German, nicknames, typos.

Three ways to rank, and the one the assistant uses:
  identifiers   documents that mention the asset ids and alarm codes in the question (from the knowledge graph)
  words         BM25 over words, with the plant glossary adding the plant's own names (Waage -> checkweigher W4)
  spelling      character n-grams (TF-IDF cosine), which survive typos and compound words
  hybrid        reciprocal rank fusion of the three

Superseded manual sections are not returned; the section that replaced them is. Document text is data: it is ranked
and quoted, never followed.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from . import graph
from .store import Store

STOP = set(
    "the a an and or of to on in at is are be for with what how why when wie was ist der die das und zu an".split()
)


@dataclass
class Hit:
    id: str
    kind: str
    title: str
    text: str
    score: float


SUFFIXES = ("ing", "ig", "en", "er", "ed", "es", "e", "s")


def stem(t: str) -> str:
    for s in SUFFIXES:
        if t.endswith(s) and len(t) - len(s) >= 4:
            return t[: -len(s)]
    return t


def split_compound(t: str, glossary: dict[str, str]) -> list[str]:
    """German compounds made of glossary words: greifervakuum -> greifer vakuum."""
    for i in range(4, len(t) - 3):
        a, b = t[:i], t[i:]
        if a in glossary and (b in glossary or stem(b) in glossary):
            return [a, b]
    return [t]


def words(text: str, glossary: dict[str, str]) -> list[str]:
    toks = [t for t in re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)?", graph.fold(text)) if t not in STOP]
    parts = [p for t in toks for p in (split_compound(t, glossary) if t not in glossary else [t])]
    out = []
    for t in parts:
        out.append(stem(t))
        out += [stem(x) for x in graph.fold(glossary.get(t, glossary.get(stem(t), ""))).split()]
    return out


class Index:
    def __init__(self, store: Store, cfg: dict):
        self.store = store
        self.cfg = cfg
        self.glossary = {graph.fold(k): v for k, v in cfg["glossary"].items()}
        rows = store.q("SELECT id, kind, title, text FROM documents WHERE superseded_by IS NULL ORDER BY id")
        self.docs = [Hit(r[0], r[1], r[2], r[3], 0.0) for r in rows]
        self.ids = [d.id for d in self.docs]
        self.mentions: dict[str, set[str]] = {}
        for doc, ent in store.q("SELECT doc, entity FROM mentions"):
            self.mentions.setdefault(doc, set()).add(ent)
        # a ticket's title is the start of its text; indexing both would count those words twice
        body = [d.title + " " + d.text if d.kind == "manual" else d.text for d in self.docs]
        self.toks = [words(b, self.glossary) for b in body]
        self.df = Counter(t for toks in self.toks for t in set(toks))
        self.avg = float(np.mean([len(t) for t in self.toks])) if self.toks else 1.0
        lo, hi = cfg["ngram"]
        self.vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(lo, hi), preprocessor=graph.fold, sublinear_tf=True)
        self.mat = self.vec.fit_transform(body) if self.docs else None

    # ------------------------------------------------------------------------------------------ the three rankers

    def by_identifiers(self, q: str) -> list[tuple[str, float]]:
        ents = graph.entities(self.store, q, self.glossary)
        if not ents:
            return []
        out = []
        for d in self.ids:
            m = self.mentions.get(d, set())
            s = sum((2.0 if "-" in e else 1.0) * (1.0 if how == "id" else 0.5) for e, how in ents.items() if e in m)
            if s:
                out.append((d, s))
        return sorted(out, key=lambda x: (-x[1], x[0]))

    def by_words(self, q: str) -> list[tuple[str, float]]:
        qt = words(q, self.glossary)
        n = len(self.docs)
        k1, b = self.cfg["bm25_k1"], self.cfg["bm25_b"]
        out = []
        for d, toks in zip(self.ids, self.toks, strict=True):
            tf = Counter(toks)
            s = 0.0
            for t in set(qt):
                if t in tf:
                    idf = math.log(1 + (n - self.df[t] + 0.5) / (self.df[t] + 0.5))
                    s += idf * tf[t] * (k1 + 1) / (tf[t] + k1 * (1 - b + b * len(toks) / self.avg))
            if s > 0:
                out.append((d, s))
        return sorted(out, key=lambda x: (-x[1], x[0]))

    def by_spelling(self, q: str) -> list[tuple[str, float]]:
        if self.mat is None:
            return []
        sims = (self.mat @ self.vec.transform([q]).T).toarray().ravel()
        order = np.argsort(-sims, kind="stable")
        return [(self.ids[i], float(sims[i])) for i in order if sims[i] > 0]

    # ------------------------------------------------------------------------------------------ what callers use

    def search(self, q: str, method: str = "hybrid", k: int | None = None) -> list[Hit]:
        k = k or self.cfg["k"]
        if method == "identifiers":
            ranked = self.by_identifiers(q)
        elif method == "words":
            ranked = self.by_words(q)
        elif method == "spelling":
            ranked = self.by_spelling(q)
        elif method == "hybrid":
            top = 1.0 / (self.cfg["rrf_k"] + 1)
            fused: Counter = Counter()
            for r in (self.by_words(q), self.by_spelling(q)):
                for rank, (d, _) in enumerate(r[:50]):
                    fused[d] += 1.0 / (self.cfg["rrf_k"] + rank + 1)
            # identifiers typed in the question decide: an alarm code counts as a top rank, an asset id as half of
            # one. Machines a glossary word points at only widen the word search above.
            typed = {e for e, how in graph.entities(self.store, q).items() if how == "id"}
            for d in fused:
                m = self.mentions.get(d, set())
                fused[d] += sum(top if "-" in e else top / 2 for e in typed if e in m)
            ranked = sorted(fused.items(), key=lambda x: (-x[1], x[0]))
        else:
            raise ValueError(f"unknown method {method!r}")
        by_id = {d.id: d for d in self.docs}
        return [Hit(by_id[d].id, by_id[d].kind, by_id[d].title, by_id[d].text, round(s, 4)) for d, s in ranked[:k]]
