"""Build safe FTS5 queries for multilingual keyword retrieval."""

import re


WORD = re.compile(r"\w+", re.UNICODE)

# FTS5 trigram 中文索引。
def build_fts_query(query: str) -> str | None:
    terms: list[str] = []
    for word in WORD.findall(query.lower()):
        if len(word) < 3:
            continue
        if any(ord(character) > 127 for character in word):
            terms.extend(word[index : index + 3] for index in range(len(word) - 2))
        else:
            terms.append(word)
    unique_terms = tuple(dict.fromkeys(terms))[:32]
    if not unique_terms:
        return None
    return " OR ".join(f'"{term}"' for term in unique_terms)
