from typing import Dict, List

import spacy


_NLP = None


def _get_nlp():
    global _NLP

    if _NLP is None:
        try:
            _NLP = spacy.load("en_core_web_sm")
        except OSError as error:
            raise RuntimeError(
                "spaCy model 'en_core_web_sm' is not installed. "
                "Run: python -m spacy download en_core_web_sm"
            ) from error

    return _NLP


def _clean_chunk(chunk) -> str:
    text = chunk.text.strip().lower()

    if len(text) < 3:
        return ""

    if all(token.is_stop or token.is_punct for token in chunk):
        return ""

    return text


def _find_connecting_verb(doc, source_span, target_span) -> str:
    start = min(source_span.end, target_span.end)
    end = max(source_span.start, target_span.start)

    if start >= end:
        return "related_to"

    for token in doc[start:end]:
        if token.pos_ == "VERB":
            return token.lemma_.lower()

    return "related_to"


def extract_entities_and_relationships(
    text: str,
    max_sentences: int = 200
) -> Dict[str, List]:
    nlp = _get_nlp()
    doc = nlp(text)

    entities = set()
    relationships = []

    for sentence in list(doc.sents)[:max_sentences]:
        sentence_chunks = []

        for chunk in sentence.noun_chunks:
            cleaned = _clean_chunk(chunk)

            if cleaned:
                sentence_chunks.append((cleaned, chunk))
                entities.add(cleaned)

        for i in range(len(sentence_chunks)):
            for j in range(i + 1, len(sentence_chunks)):
                source_text, source_span = sentence_chunks[i]
                target_text, target_span = sentence_chunks[j]

                if source_text == target_text:
                    continue

                relationship = _find_connecting_verb(doc, source_span, target_span)

                relationships.append({
                    "source": source_text,
                    "target": target_text,
                    "relationship": relationship,
                    "evidence": sentence.text.strip()
                })

    return {
        "entities": sorted(entities),
        "relationships": relationships
    }
