# DOREMUS Runbook

This runbook documents the commands needed to run Wikontic with the DOREMUS ontology setup that exists in this repo.

It also explains how far the same process generalizes to another KG.

## What is already supported

The current code now supports a reduced ontology-mapping setup for DOREMUS.

For DOREMUS, the working path is:

1. Generate mapping JSON files from `preprocessing/doremus.ttl`
2. Build a Mongo ontology DB from those mappings
3. Build a Mongo triplets DB
4. Run the Streamlit app for interactive extraction and visualization, or


The minimum mapping files currently supported by the reduced loader path are:

- `entity_type2label.json`
- `entity_type2hierarchy.json`
- `prop2label.json`
- `prop2constraints.json`


## Prerequisites

Run everything from the repo root:

Install dependencies:

```bash
pip install -r requirements.txt
```

If your local Python has the `pyOpenSSL` / `cryptography` mismatch, fix that first:

```bash
python3 -m pip install --user --upgrade "pyOpenSSL>=23.2.0" "cryptography>=42"
```

Use the local source tree:

```bash
export PYTHONPATH=/absolute/path/to/Wikontic/src
```

## 1. Build the DOREMUS DBs

The simplest path is:

```bash
./setup_doremus.sh
```

This script:

- starts the Mongo container on `localhost:27018`
- generates DOREMUS mappings from `preprocessing/doremus.ttl`
- creates the ontology DB `doremus_ontology`
- creates the triplets DB `doremus_triplets_db`

### Equivalent manual commands

If you want the explicit steps instead of the wrapper script:

```bash
docker pull mongodb/mongodb-atlas-local:latest
docker run --name text2kg_mongo -d -p 27018:27017 mongodb/mongodb-atlas-local:latest
```

If the container already exists but is stopped:

```bash
docker start text2kg_mongo
```

Generate DOREMUS mappings:

```bash
python3 preprocessing/doremus_preprocessing.py \
  --ttl_path preprocessing/doremus.ttl \
  --output_dir src/wikontic/utils/ontology_mappings_doremus
```

Build the ontology DB:

```bash
cd src/wikontic
python3 create_wikidata_ontology_db.py \
  --mongo_uri "mongodb://localhost:27018/?directConnection=true" \
  --database doremus_ontology \
  --mappings_dir "utils/ontology_mappings_doremus/"
```

Build the triplets DB:

```bash
python3 create_ontological_triplets_db.py \
  --mongo_uri "mongodb://localhost:27018/?directConnection=true" \
  --db_name doremus_triplets_db
cd ../..
```

## 2. Run the Streamlit app with DOREMUS

Set the environment so the UI reads and writes the DOREMUS DBs:

```bash
export MONGO_URI="mongodb://localhost:27018/?directConnection=true"
export ONTOLOGY_DB_NAME="doremus_ontology"
export TRIPLETS_DB_NAME="doremus_triplets_db"
export OPENAI_API_KEY="fake"
export DEFAULT_APP_MODEL="openai/gpt-oss-120b"
```

Then run:

```bash
streamlit run Wikontic.py
```

### What works in the app

The supported DOREMUS flow is:

1. Open `KG Extraction`
2. Keep the model as `openai/gpt-oss-120b`
3. Paste a music-domain text
4. Click `Extract and Visualize`
5. Open `Current KG`

That gives you a graph extracted with:

- ontology DB: `doremus_ontology`
- triplets DB: `doremus_triplets_db`

### Important limitation

`Personal KG` is different. It uses OpenAI web search through the Responses API, so it needs a real `OPENAI_API_KEY`. It is not the recommended path for testing DOREMUS unless you specifically want that page.

## 3. Example test text

Use something music-domain and relation-heavy:

```text
Claude Debussy composed La Mer in 1905. La Mer is an orchestral work in three movements. It was premiered in Paris. Debussy was born in Saint-Germain-en-Laye in 1862 and died in Paris in 1918.
```

## 5. Can this work for another KG?

Yes, but only if the other KG can be converted into the mapping format the code now understands.

### What “another KG” must provide

At minimum, you need a preprocessing step that emits:

- `entity_type2label.json`
- `entity_type2hierarchy.json`
- `prop2label.json`
- `prop2constraints.json`

Where:

- `entity_type2label.json`
  maps type IDs to display labels
- `entity_type2hierarchy.json`
  gives the transitive superclass closure including self
- `prop2label.json`
  maps property IDs to display labels
- `prop2constraints.json`
  gives:
  - `"Subject type constraint"`
  - `"Value-type constraint"`

The current loader can derive inverse subject/object constraint indexes from `prop2constraints.json`.

### When code changes are not needed

You do not need more code changes if:

1. your KG can be turned into those four files, and
2. the IDs are internally consistent across those files

In that case, the process is:

1. write a preprocessing script for that KG
2. generate a new mappings directory
3. point `create_wikidata_ontology_db.py` at that mappings directory
4. use a separate ontology DB and triplets DB name

### When code changes are still needed

You will still need code changes if the KG:

- does not have a meaningful class hierarchy
- does not have property domain/range information
- uses very different semantics that make the current structured aligner assumptions invalid
- needs ontology-specific alias or constraint logic beyond what the reduced loader can infer

So the honest answer is:

- DOREMUS: yes, we can document it cleanly now
- arbitrary KG: possible, but only if you can preprocess it into this expected structure

## 6. Recommended environment block

For the DOREMUS Streamlit flow, this is the cleanest shell setup:

```bash
export PYTHONPATH=/home/mplgg/Wikontic_fork/Wikontic/src
export MONGO_URI="mongodb://localhost:27018/?directConnection=true"
export ONTOLOGY_DB_NAME="doremus_ontology"
export TRIPLETS_DB_NAME="doremus_triplets_db"
export OPENAI_API_KEY="fake"
export DEFAULT_APP_MODEL="openai/gpt-oss-120b"
```

Then run:

```bash
streamlit run Wikontic.py
```
