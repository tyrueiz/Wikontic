# DOREMUS Streamlit Changes

This document summarizes the code changes that were made so Wikontic can run the Streamlit app with the DOREMUS ontology setup.

It is not a generic project changelog. It only covers the changes that matter for:

1. creating a DOREMUS ontology DB
2. creating a compatible triplets DB
3. pointing the Streamlit app at those DBs
4. making the app use the correct LLM model/backend assumptions

## Overview

Originally, the Streamlit app was wired around the existing Wikidata setup:

- ontology DB name hardcoded as `wikidata_ontology`
- triplets DB name hardcoded as `demo`
- Mongo URI taken from `MONGO_URI` with no safe default
- model dropdowns defaulting to OpenAI-hosted models like `gpt-4.1`

For the DOREMUS setup, we changed the code so that:

- DOREMUS mappings can be generated from `preprocessing/doremus.ttl`
- the ontology DB loader can work with a reduced DOREMUS mapping set
- a separate setup script can build isolated DOREMUS DBs
- the Streamlit pages can be pointed at those DBs through environment variables
- the Streamlit model selectors default to the vLLM-served `openai/gpt-oss-120b`

## 1. DOREMUS preprocessing

### File

- [preprocessing/doremus_preprocessing.py](/home/mplgg/Wikontic_fork/Wikontic/preprocessing/doremus_preprocessing.py)

### Why this change was needed

The existing ontology setup expected JSON mapping files derived from Wikidata-oriented preprocessing. DOREMUS ships as a Turtle ontology, so we needed a dedicated preprocessing step to turn `doremus.ttl` into the mapping files the loader can consume.

### What changed

Added a dedicated preprocessing script that:

- parses `preprocessing/doremus.ttl`
- extracts class labels
- extracts class hierarchy from `rdfs:subClassOf`
- extracts property labels
- extracts property constraints from:
  - `rdfs:domain`
  - `rdfs:range`

### Output files currently generated

- `entity_type2label.json`
- `entity_type2hierarchy.json`
- `prop2label.json`
- `prop2constraints.json`

### Important design choice

We intentionally reduced the output to the minimum useful set for DOREMUS instead of trying to fully imitate the old Wikidata preprocessing bundle.

## 2. Ontology DB loader support for reduced DOREMUS mappings

### File

- [src/wikontic/create_wikidata_ontology_db.py](/home/mplgg/Wikontic_fork/Wikontic/src/wikontic/create_wikidata_ontology_db.py)

### Why this change was needed

Originally, the ontology DB loader assumed a full Wikidata mapping bundle existed on disk, including:

- aliases
- property constraints
- inverse constraint indexes

That did not match the reduced DOREMUS mapping set.

### What changed

The loader was modified so it can now work when only the reduced DOREMUS files are present.

#### Required files now supported

- `entity_type2label.json`
- `entity_type2hierarchy.json`
- `prop2label.json`
- `prop2constraints.json`

#### New fallback behavior

If these are missing:

- `entity_type2aliases.json`
  - defaults to empty alias lists
- `prop2aliases.json`
  - defaults to empty alias lists

If these are missing:

- `subj_constraint2prop.json`
- `obj_constraint2prop.json`

they are now derived from `prop2constraints.json`.

### Why this matters for Streamlit

The Streamlit extraction pages instantiate the structured aligner and structured inference pipeline. Those depend on the ontology DB being successfully created first. Without this loader change, the DOREMUS DB creation step would fail before Streamlit could use it.

## 3. Separate DOREMUS setup script

### File

- [setup_doremus.sh](/home/mplgg/Wikontic_fork/Wikontic/setup_doremus.sh)

### Why this change was needed

The original setup script was tightly coupled to the Wikidata path:

- it built the default ontology DB
- it did not generate DOREMUS mappings
- it did not isolate the DOREMUS DB names

We needed a separate bootstrap path that would not overwrite or collide with the Wikidata setup.

### What changed

Added a new setup script that:

- ensures the Mongo container exists and is running on port `27018`
- runs `preprocessing/doremus_preprocessing.py`
- builds the ontology DB `doremus_ontology`
- builds the triplets DB `doremus_triplets_db`

### Why this matters for Streamlit

This gives the Streamlit app stable DB names to target:

- `doremus_ontology`
- `doremus_triplets_db`

without having to reuse `wikidata_ontology` or `demo`.

## 4. Streamlit pages now use configurable Mongo DB names

### Files

- [pages/1_KG_Extraction.py](/home/mplgg/Wikontic_fork/Wikontic/pages/1_KG_Extraction.py)
- [pages/3_Current_KG.py](/home/mplgg/Wikontic_fork/Wikontic/pages/3_Current_KG.py)
- [pages/4_Personal_KG.py](/home/mplgg/Wikontic_fork/Wikontic/pages/4_Personal_KG.py)
- [pages/5_Wikipedia_vs_Wikidata.py](/home/mplgg/Wikontic_fork/Wikontic/pages/5_Wikipedia_vs_Wikidata.py)

### Why this change was needed

The app originally assumed:

- `MONGO_URI` would already be set correctly
- `demo` should be the triplets DB
- `wikidata_ontology` should be the ontology DB

That broke in two ways for the DOREMUS setup:

1. the local Mongo container is exposed on `27018`, not `27017`
2. the DOREMUS flow should use dedicated DB names

### What changed

#### Safe Mongo default

The pages now default to:

```text
mongodb://localhost:27018/?directConnection=true
```

if `MONGO_URI` is not set.

#### Configurable ontology DB

The extraction pages now read:

```text
ONTOLOGY_DB_NAME
```

with default:

```text
wikidata_ontology
```

#### Configurable triplets DB

The relevant pages now read:

```text
TRIPLETS_DB_NAME
```

with defaults based on the page’s previous behavior.

### Why this matters for Streamlit

This is the key change that lets the app use DOREMUS just by exporting:

```bash
export ONTOLOGY_DB_NAME="doremus_ontology"
export TRIPLETS_DB_NAME="doremus_triplets_db"
```

instead of editing page code every time.

## 5. Streamlit extraction pages now default to the right LLM model

### Files

- [pages/1_KG_Extraction.py](/home/mplgg/Wikontic_fork/Wikontic/pages/1_KG_Extraction.py)
- [pages/4_Personal_KG.py](/home/mplgg/Wikontic_fork/Wikontic/pages/4_Personal_KG.py)

### Why this change was needed

The original Streamlit model dropdowns offered:

- `gpt-4.1`
- `gpt-4o-mini`
- `gpt-4.1-mini`

But your local backend is configured around the OpenAI-compatible vLLM server using:

- `openai/gpt-oss-120b`

That caused 404 errors when the app tried to call `gpt-4.1` on the vLLM endpoint.

### What changed

The extraction pages now:

- default to `openai/gpt-oss-120b`
- allow model choices to come from environment configuration

Environment variables now used:

- `DEFAULT_APP_MODEL`
- `APP_MODEL_OPTIONS`

Current default model list:

- `openai/gpt-oss-120b`
- `openai/gpt-oss-20b`
- `gpt-4o-mini`

### Why this matters for Streamlit

This removed the “model does not exist” failures and aligned the UI with the backend you are actually running.

## 6. Streamlit extraction pages now accept `OPENAI_API_KEY`

### Files

- [pages/1_KG_Extraction.py](/home/mplgg/Wikontic_fork/Wikontic/pages/1_KG_Extraction.py)
- [pages/4_Personal_KG.py](/home/mplgg/Wikontic_fork/Wikontic/pages/4_Personal_KG.py)

### Why this change was needed

The app previously looked for:

```text
KEY
```

which did not match the rest of the repo and did not match the environment conventions already used elsewhere.

### What changed

The pages now use:

- `KEY` if present
- otherwise `OPENAI_API_KEY`

### Why this matters for Streamlit

This avoids one more environment mismatch when launching the app for the DOREMUS flow.

## 7. Personal KG page now warns about its OpenAI web search dependency

### File

- [pages/4_Personal_KG.py](/home/mplgg/Wikontic_fork/Wikontic/pages/4_Personal_KG.py)

### Why this change was needed

The `Personal KG` page is different from the main extraction page:

- it uses the OpenAI Responses API
- it uses the `web_search` tool
- it therefore needs a real hosted OpenAI model and a real OpenAI API key

That is not compatible with the simple `OPENAI_API_KEY=fake` vLLM-only setup.

### What changed

- removed the hardcoded `gpt-4.1` usage
- made the search model configurable with `WEB_SEARCH_MODEL`
- added a user-facing warning if the page is launched with no real API key

### Why this matters for Streamlit

It prevents confusing failures on the `Personal KG` page when the rest of the DOREMUS Streamlit setup is working correctly.

## 8. How the DOREMUS Streamlit path works now

With the code changes above, the supported flow is:

1. Build the DOREMUS DBs:

```bash
./setup_doremus.sh
```

2. Export the environment:

```bash
export PYTHONPATH=/home/mplgg/Wikontic_fork/Wikontic/src
export MONGO_URI="mongodb://localhost:27018/?directConnection=true"
export ONTOLOGY_DB_NAME="doremus_ontology"
export TRIPLETS_DB_NAME="doremus_triplets_db"
export OPENAI_API_KEY="fake"
export DEFAULT_APP_MODEL="openai/gpt-oss-120b"
```

3. Start Streamlit:

```bash
streamlit run Wikontic.py
```

4. Use:

- `KG Extraction` to extract a graph from input text
- `Current KG` to visualize the graph written in the current session

## 9. Remaining limitations

These changes make the DOREMUS Streamlit path usable, but they do not make the app fully ontology-agnostic.

Current limits:

- the UI still talks in generic/Wikidata-flavored terms in places
- `Personal KG` still depends on hosted OpenAI web search
- the DOREMUS ontology support assumes the reduced mapping structure we implemented
- other KGs still need their own preprocessing step unless they can produce the same mapping files

## 10. Related files

If you want to follow the complete DOREMUS setup path, the main files are:

- [preprocessing/doremus_preprocessing.py](/home/mplgg/Wikontic_fork/Wikontic/preprocessing/doremus_preprocessing.py)
- [src/wikontic/create_wikidata_ontology_db.py](/home/mplgg/Wikontic_fork/Wikontic/src/wikontic/create_wikidata_ontology_db.py)
- [setup_d.sh](/home/mplgg/Wikontic_fork/Wikontic/setup_d.sh)
- [pages/1_KG_Extraction.py](/home/mplgg/Wikontic_fork/Wikontic/pages/1_KG_Extraction.py)
- [pages/3_Current_KG.py](/home/mplgg/Wikontic_fork/Wikontic/pages/3_Current_KG.py)
- [pages/4_Personal_KG.py](/home/mplgg/Wikontic_fork/Wikontic/pages/4_Personal_KG.py)
- [docs/doremus_runbook.md](/home/mplgg/Wikontic_fork/Wikontic/docs/doremus_runbook.md)
