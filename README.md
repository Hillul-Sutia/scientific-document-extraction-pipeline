# Fermented Food Information Extraction

This project converts fermented-food research papers into seven structured JSON
tables. It extracts page-aware text and tables from PDFs, constructs bounded
evidence chunks, discovers explicitly mentioned fermented foods, retrieves a
small set of relevant chunks for each food and table, and uses a local Qwen2.5
model through Ollama for schema-constrained extraction.

The default generation model is `qwen2.5:3b`. A Hugging Face Qwen tokenizer is
used only to count tokens while constructing chunks; model inference is handled
by Ollama.

## Pipeline overview

```text
data/raw_pdfs/*.pdf
        |
        v
1. Ingestion (PyMuPDF4LLM)
        |-- data/markdown/*.md
        `-- data/pages/*.json
                    |
                    v
2. Preprocessing
        |-- clean page text
        |-- detect sections
        |-- separate text and Markdown tables
        `-- construct token-bounded, page-aware chunks
                    |
                    `-- data/chunks/*.json
                                |
                                v
3. Food discovery (Qwen2.5 through Ollama)
        |-- validate that every returned name occurs in the chunk
        |-- cache results by chunk ID and content hash
        `-- assign stable food IDs and food/document occurrences
                                |
                                v
4. Evidence retrieval
        |-- start with chunks that mention the food
        |-- add their immediate neighbors
        |-- rank using table-specific keywords and chunk type
        `-- keep at most EXTRACTION_MAX_CHUNKS
                                |
                                v
5. Structured extraction (Qwen2.5 through Ollama)
        |-- Tables 1, 2, 3, 4, 6, and 7: LLM + Pydantic schema
        |-- validate evidence chunk IDs
        |-- attach PDF/page/section provenance
        |-- merge or deduplicate records
        `-- Table 5: derive from Table 4 without an LLM call
                                |
                                `-- data/tables/*.json
```

## What each stage does

### 1. Ingestion

`src/ingestion/pipeline.py` scans `data/raw_pdfs` for `*.pdf` files. For every
PDF, `pymupdf4llm` extracts ordered page content and writes two artifacts:

- `data/markdown/<document>.md`: a human-readable copy with page markers.
- `data/pages/<document>.json`: the structured input used by preprocessing,
  containing `document_id`, `source_pdf`, and ordered pages.

Each PDF is isolated with error handling, so one unreadable document does not
stop ingestion of the remaining documents.

### 2. Preprocessing and chunk construction

For each page document, preprocessing performs these steps in order:

1. `MarkdownCleaner` normalizes newlines and spaces, joins words broken by line
   wrapping, removes isolated page artifacts, and removes numeric citation
   markers.
2. `SectionSplitter` recognizes Markdown and bold headings, carries the active
   heading across pages, preserves page numbers, and excludes reference and
   bibliography sections.
3. `TableParser` preserves document order while separating paragraphs from
   Markdown tables. A nearby table caption is attached to its table block.
4. `Chunker` creates separate text and table chunks:
   - text chunks target 550 tokens, have a maximum of 750 tokens, and reuse up
     to 80 tokens from the previous chunk;
   - tables remain intact when possible;
   - oversized tables are split by rows while repeating their header;
   - chunks do not cross section boundaries.
5. Each chunk receives a stable ID, content hash, token count, document/PDF and
   page metadata, previous/next chunk IDs, and `embedding_text` prepared for a
   future vector index.

Intermediate artifacts are written to:

```text
data/cleaned/          cleaned page documents
data/sections/         page-aware section fragments
data/parsed_sections/  ordered text and table blocks
data/chunks/           finalized extraction chunks
```

The tokenizer is loaded in this order: local Hugging Face cache, a one-time
download when allowed, then a deterministic local fallback tokenizer. The
fallback lets preprocessing continue offline, although its token counts are
approximate.

### 3. Food discovery

The extraction pipeline first sends every chunk to Qwen2.5 and asks for all
specific fermented-food names explicitly present in that chunk. Returned names
are normalized to lowercase and checked with an exact boundary-aware match
against the original chunk. Names not actually present in the evidence are
discarded, reducing hallucinated foods.

Discovery results are cached at:

```text
data/extraction_cache/food_discovery/<document>.json
```

The cache entry includes the chunk's content hash. Unchanged chunks reuse their
cached food names; changed or new chunks are processed again.

The pipeline then creates:

- `food_ids.json`: stable IDs such as `F0001`; existing IDs are reused.
- `food_occurrences.json`: one record for every food/document pair, including
  all chunks where that food was discovered.

The same food can therefore be extracted independently from multiple PDFs while
retaining one stable food ID.

### 4. Evidence retrieval

For each food/document occurrence and each target table, the shared retriever:

1. starts with all discovery chunks that mention the food;
2. adds the immediate previous and next chunks, allowing a food name in one
   chunk to be connected with details in an adjacent chunk;
3. scores candidates using table-specific keywords;
4. gives a small bonus to table chunks for raw materials, nutrition, microbiome,
   and predominant-microbe extraction;
5. sends only the highest-ranked `EXTRACTION_MAX_CHUNKS` chunks to the extractor.

This limits extraction context even when a food is mentioned many times. The
current retriever is lexical and neighbor-based. It does **not** currently use a
vector database or embeddings, although each chunk already contains an
`embedding_text` field for a future vector-search implementation.

Retrieval writes an INFO summary for every food/table pair and a score breakdown
for every candidate. The candidate log includes its seed/neighbor role, base
score, matched keywords, keyword score, table bonus, total score, rank, and
selection decision. These messages appear on the console and in
`logs/src_extraction_retriever.log`. Chunk contents are not copied into the log.

Example:

```text
Retrieval food=kimchi table=table4 seeds=1 candidates=3 selected=2 max_chunks=2
Retrieval score food=kimchi table=table4 chunk=c3 rank=2 role=neighbor \
base_score=10 matched_keywords=['nutrition', 'protein'] keyword_score=4 \
table_bonus=0 total_score=14 selected=True
```

### 5. Structured extraction and validation

Tables 1, 2, 3, 4, 6, and 7 use the same structured extractor with a different
Pydantic schema and table-specific instructions. For every food/document/table
combination, the selected chunks are sent together in one prompt.

The prompt requires the model to:

- use only supplied evidence;
- return a JSON array matching the requested schema;
- return `[]` when no supported record exists;
- include one or more allowed `evidence_chunk_ids` in every record;
- avoid transferring information from another food in the same evidence.

The response is parsed as JSON and validated with Pydantic. Empty records and
records without a valid supporting chunk ID are discarded. Valid records are
enriched with food ID, food name, source PDF, pages, section, and evidence.

After schema validation, `EvidenceVerifier` checks every extracted value against
only the chunks listed in that record's `evidence_chunk_ids`. Matching is
boundary-aware and accepts exact text, case/whitespace normalization, and
spacing-only unit variants such as `g / 100 g` versus `g/100g`. It does not use
fuzzy or semantic matching.

- Missing required source values reject the complete record. Required examples
  include raw material, nutrition parameter/value, taxonomy name, and microbe.
- Missing optional values are replaced with `null` instead of being saved as
  supported data.
- Normalized classifications such as food category, food type, nutrition
  category, and taxonomy level may not be literal source phrases. They are
  retained but explicitly labeled `derived_not_present` rather than verified as
  quotations.
- If a value exists in another retrieved chunk but not in the chunks cited by
  the record, it does not pass verification.

Accepted records contain `evidence_verification`, for example:

```json
{
  "status": "verified_with_derived_fields",
  "fields": {
    "category": "derived_not_present",
    "parameter": "exact",
    "value": "exact",
    "unit": "normalized"
  },
  "cited_chunk_ids": ["paper_c00042_ab12cd34"]
}
```

Verification removals and rejections are written to the console and
`logs/src_extraction_evidence_verifier.log`.

### Independent post-extraction verification

After extraction has completed, the saved tables can be audited again without
running Ollama, ingestion, preprocessing, or extraction:

```powershell
uv run python verify.py
```

The command reads `data/chunks` and `data/tables`, leaves the original tables
unchanged, and writes:

```text
data/verification/
|-- verified/
|   |-- table1.json
|   |-- table2.json
|   |-- table3.json
|   |-- table4.json
|   |-- table5.json
|   |-- table6.json
|   `-- table7.json
|-- rejected/
|   |-- table1.json
|   |-- table2.json
|   |-- table3.json
|   |-- table4.json
|   |-- table5.json
|   |-- table6.json
|   `-- table7.json
`-- verification_summary.json
```

Records whose required values are absent are written to `rejected`. Records
with missing or stale chunk IDs are labeled `unverifiable` with reason
`evidence_chunk_not_found`. Unsupported optional fields are set to `null` in the
verified copy, and the source record remains available inside the rejection
entry when a complete record is rejected.

Table 1 supports its merged `evidence` representation and also checks that the
food name occurs in the evidence. Table 5 is not searched directly against
chunks; each value must have lineage to an accepted Table 4 record for the same
food, source PDF, parameter, value, and unit.

Custom locations can be supplied when auditing archived results:

```powershell
uv run python verify.py `
  --chunks-dir path/to/chunks `
  --tables-dir path/to/tables `
  --output-dir path/to/verification
```

The standalone audit can be rerun whenever verification rules change, without
repeating expensive LLM calls. It requires the original chunk files whose IDs
are referenced by the extracted records.

If an Ollama request times out, the extractor retries with half as many evidence
chunks until only one remains. Other extraction failures are recorded in
`extraction_failures.json`, and the pipeline continues. Outputs are saved after
each food/document occurrence so completed work is not held only in memory.

## The seven output tables

The complete field definitions and examples are also documented in
[`tables.txt`](tables.txt).

| Table | Purpose | Core fields | Creation method |
|---|---|---|---|
| Table 1 | Fermented Food Master | `food_id`, `food_name`, `category`, `type`, `ethnic_group`, `source_pdf` | LLM extraction, merged across PDFs |
| Table 2 | Raw Materials | `food_id`, `raw_material`, `amount`, `preparation_method` | LLM extraction |
| Table 3 | Geographic Distribution | `food_id`, `state`, `district`, `ethnic_group`, `village` | LLM extraction |
| Table 4 | Nutrition, long format | `food_id`, `category`, `parameter`, `value`, `unit` | LLM extraction |
| Table 5 | Proximate Composition, wide format | `food_id`, `entity_type`, `entity_name`, `moisture`, `ash`, `protein`, `fat`, `fiber`, `carbohydrate` | Derived from Table 4; no LLM call |
| Table 6 | Microbiome | `food_id`, `taxonomy_level`, `taxonomy_name` | LLM extraction |
| Table 7 | Predominant Microbes | `food_id`, `microbe`, `count`, `source_pdf` | LLM extraction |

Table 4 stores one nutrient measurement per record. Table 5 pivots the Table 4
parameters moisture, ash, protein, fat, fibre/fiber, and carbohydrate into a
wide record, retaining the original value and unit as one string. It is grouped
by food and source PDF.

In addition to the core fields, extracted JSON records contain provenance such
as `food_name`, `source_pdf`, `evidence_chunk_ids`, and an `evidence` array with
the supporting PDF, page range, and section.

Final files are written to:

```text
data/tables/
|-- food_ids.json
|-- food_occurrences.json
|-- table1.json
|-- table2.json
|-- table3.json
|-- table4.json
|-- table5.json
|-- table6.json
|-- table7.json
`-- extraction_failures.json
```

## Requirements

- Python 3.11 or newer
- [uv](https://docs.astral.sh/uv/) for the local environment
- [Ollama](https://ollama.com/) running locally or reachable over HTTP
- Qwen2.5 3B available in Ollama
- Internet access on the first run if the Hugging Face tokenizer is not cached
  and tokenizer downloading is enabled

## Local setup with uv

From the project directory:

```powershell
uv sync --frozen
ollama pull qwen2.5:3b
```

Place research papers in:

```text
data/raw_pdfs/
```

Ensure Ollama is running, then execute all enabled stages:

```powershell
uv run python main.py
```

`main.py` loads an optional `.env` file first and then supplies local defaults
only for variables that were not already defined. Consequently, values set in
the shell or `.env` override the defaults.

Example PowerShell overrides:

```powershell
$env:OLLAMA_MODEL = "qwen2.5:3b"
$env:EXTRACTION_MAX_CHUNKS = "2"
$env:OLLAMA_TIMEOUT_SECONDS = "600"
uv run python main.py
```

These PowerShell variables last for the current terminal session. For persistent
project configuration, create an untracked `.env` file:

```dotenv
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen2.5:3b
EXTRACTION_MAX_CHUNKS=2
OLLAMA_TIMEOUT_SECONDS=600
```

The stage switches `RUN_INGESTION`, `RUN_PREPROCESSING`, and `RUN_EXTRACTION`
are currently defined inside `main.py`. Set a switch to `False` when running
only later stages against existing artifacts.

## Docker setup

The supplied Compose configuration runs the Python application in Docker and
connects it to Ollama running on the Windows host:

```powershell
docker compose build
docker compose run --rm app
```

Or run the configured command directly:

```powershell
docker compose up
```

Compose mounts the project at `/app` and maps the host directory
`.cache/huggingface` to `/opt/huggingface` in the container. This makes the
tokenizer cache persistent and shareable between local and container runs. The
container uses `http://host.docker.internal:11434` to reach host Ollama, so the
Ollama model itself does not need to be installed inside the application
container.

## Configuration reference

| Variable | Default | Purpose |
|---|---|---|
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama HTTP endpoint; Compose overrides it with the host address |
| `OLLAMA_MODEL` | `qwen2.5:3b` | Ollama generation model |
| `OLLAMA_TIMEOUT_SECONDS` | `300` | HTTP read timeout for a generation request |
| `OLLAMA_MAX_RETRIES` | `2` | Retries for non-timeout Ollama errors |
| `OLLAMA_NUM_CTX` | `4096` | Ollama context-window setting |
| `OLLAMA_KEEP_ALIVE` | `3m` from `main.py` | How long Ollama keeps the model loaded |
| `EXTRACTION_MAX_CHUNKS` | `3` | Maximum evidence chunks sent for one food/table extraction |
| `HF_HOME` | `.cache/huggingface` | Hugging Face tokenizer cache location |
| `TOKENIZER_MODEL` | `Qwen/Qwen2.5-7B-Instruct` | Tokenizer used for chunk token counting, not Ollama inference |
| `TOKENIZER_LOCAL_FILES_ONLY` | `true` | Try the local tokenizer cache first |
| `TOKENIZER_DOWNLOAD_IF_MISSING` | `true` from `main.py` | Download once if the tokenizer is absent, otherwise use fallback |

The Ollama model and Hugging Face tokenizer are independent. Ollama packages the
tokenizer required for inference with its model. The Hugging Face tokenizer in
this project is used only to measure preprocessing chunk lengths.

## LLM calls and runtime

For uncached input, food discovery makes one LLM request per chunk. Discovery is
cached, so rerunning unchanged documents avoids those calls. For every discovered
food/document occurrence, extraction can make one request for each of Tables 1,
2, 3, 4, 6, and 7. Table 5 adds no request.

Overlapping chunk text is intentional: it protects facts located at a chunk
boundary. Retrieval limits how many chunks reach an extraction prompt, so the
entire PDF is not sent for every table. Nevertheless, CPU-only Ollama inference
can still be slow, particularly for nutrition tables that require long JSON
responses.

The current non-master extraction output allowance is 768 tokens. A large Table
4 result may reach that limit and return incomplete JSON. Such an error is
recorded in `extraction_failures.json`; increasing only the HTTP timeout does not
increase the response token allowance.

## Tests

Run the unit and integration tests with:

```powershell
uv run python -m unittest discover -s src/test -p "test_*.py"
```

The tests cover tokenizer fallback/download behavior, page-aware section and
table parsing, token-bounded chunk construction, neighbor retrieval, stable food
IDs, multi-PDF extraction, provenance, Table 5 derivation, and timeout context
reduction.

## Active and legacy modules

The active extraction path is assembled in `src/extraction/pipeline.py` and uses
`StructuredTableExtractor` from `src/extraction/table_extractor.py`.

The older files under `src/extraction/extractors/` are not imported by the
current pipeline. Similarly, `src/classifier/chunk_classifier.py` is not part of
the current execution path. They should not be used to understand current
runtime behavior unless they are deliberately reconnected or removed.
