# Questions Folder

This folder contains JSON configuration files used by the LAS retrieval evaluation scripts.

---

## `ibm_expert_questions.json`

A list of expert evaluation questions with ground-truth document annotations.

**Loaded by:** `test_expert_questions_fixed.py`  
**Override path via:** env var `LAS_QUESTIONS_FILE`

### Format

```json
[
  {
    "id": "IBM-001",
    "vendor": "IBM",
    "difficulty": "EINFACH",
    "question_de": "German question text",
    "question_en": null,
    "expected_doc": "some_document.pdf",
    "expected_pages": [2, 3],
    "expected_section": "Section Name",
    "expected_answer_snippet": null,
    "reason": "Why this doc is the ground truth",
    "alternative_docs": []
  }
]
```

| Field | Required | Description |
|---|---|---|
| `id` | yes | Unique question ID (e.g. `IBM-001`) |
| `vendor` | yes | `IBM` or `Microsoft` |
| `difficulty` | yes | `EINFACH`, `MITTEL`, or `SCHWER` |
| `question_de` | one of | German question text |
| `question_en` | one of | English question text (used if `question_de` is absent) |
| `question` | one of | Preferred over `question_de`/`question_en` if present |
| `expected_doc` | yes | Base filename of the expected source document |
| `expected_pages` | no | List of relevant page numbers |
| `expected_section` | no | Section heading in the document |
| `expected_answer_snippet` | no | Short answer snippet (not yet used) |
| `reason` | no | Human-readable explanation |
| `alternative_docs` | no | Additional accepted filenames |

---

## `bad_actors.json`

A list of document base names that are considered "bad actors" — overview documents that
frequently dominate Top-K retrieval results but do not contain the specialized information
needed for detailed licensing questions.

**Loaded by:** `vectorstore_IBM_Mapping.py` (module-level, at import time)  
**Override path via:** env var `LAS_BAD_ACTORS_JSON`

### Format

```json
[
  "IBM_Licensing_Models_Passport Advantage.pdf",
  "L-YRHY-YWPJ3V_de.pdf"
]
```

A plain JSON array of document file-name strings (base names only, no directory path).

### Effect on retrieval

When a retrieved chunk comes from a bad-actor document:

1. **Distance penalty** — a small value (default `0.05`) is added to its distance score,
   nudging it down the ranking.  
   Configure via env var `LAS_BAD_ACTORS_DISTANCE_PENALTY` (float, default `0.05`).

2. **Stricter per-doc cap** — at most `LAS_BAD_ACTORS_MAX_PER_DOC` chunks (default `1`)
   from a bad-actor document are included in the final Top-K result, which is tighter than
   the general `LAS_MAX_PER_DOC` cap.  
   Configure via env var `LAS_BAD_ACTORS_MAX_PER_DOC` (int, default `1`).

Both effects apply in rerank and non-rerank modes.  
If the JSON file is missing or invalid, the module falls back to built-in defaults and logs a warning.

---

## Relevant environment variables

| Variable | Default | Description |
|---|---|---|
| `LAS_QUESTIONS_FILE` | `questions/ibm_expert_questions.json` | Path to questions JSON |
| `LAS_BAD_ACTORS_JSON` | `questions/bad_actors.json` | Path to bad actors JSON |
| `LAS_INTERNAL_K` | `50` | Chroma candidate pool size before post-processing (default raised from 30 to ensure sufficient diversity candidates) |
| `LAS_MAX_PER_DOC` | `1` | Max chunks per document in final Top-K |
| `LAS_BAD_ACTORS_MAX_PER_DOC` | `1` | Max chunks per bad-actor document in final Top-K |
| `LAS_BAD_ACTORS_DISTANCE_PENALTY` | `0.05` | Distance (and rerank score) penalty for bad actors |
| `LAS_RERANK` | `0` | Enable reranking (`1` = on) |
| `LAS_RERANK_TOP_N` | `30` | Number of candidates to pass to reranker |
| `LAS_VENDOR` | `IBM` | Vendor filter for test script |
