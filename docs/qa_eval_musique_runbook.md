# `qa_eval_musique` Runbook

This runbook documents the MuSiQue path for building a Wikontic knowledge graph and running QA evaluation. It follows the Wikontic paper's pipeline: extract triplets from text, optionally align them with Wikidata ontology constraints, store the graph in MongoDB, then answer multi-hop questions from the graph.

Paper reference: <https://arxiv.org/pdf/2512.00590>

## Prerequisites

### 1. Python environment

Run commands from the Wikontic repository root:

```bash
cd Wikontic
```

Install dependencies:

```bash
pip install -r requirements.txt
```

The evaluation script imports `jsonlines`. If it is missing in your environment, install it explicitly:

```bash
pip install jsonlines
```

Use the local source tree:

```bash
export PYTHONPATH=/absolute/path/to/Wikontic/src
```

Replace `/absolute/path/to/Wikontic` with the actual absolute path to your local clone.

### 2. MongoDB

Start MongoDB and initialize the ontology/triplet databases:

```bash
./setup_db.sh
```

The default MongoDB URI used by the MuSiQue scripts is:

```text
mongodb://localhost:27018/?directConnection=true
```

If your local MongoDB or Docker container listens on the default MongoDB port instead, pass:

```text
mongodb://localhost:27017/?directConnection=true
```

### 3. Model credentials

`inference_and_eval/musique_inference.py` reads the API key from the environment variable configured in the YAML file. The default MuSiQue config uses:

```bash
export KEY=your_api_key
```

If you are using OpenRouter or another OpenAI-compatible gateway, set the configured base URL as well:

```bash
export OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
```

`inference_and_eval/qa_eval_musique.py` reads:

```bash
export OPENAI_API_KEY=your_api_key
```

## MuSiQue Dataset

The default MuSiQue test file is:

```text
datasets/musique_200_test.json
```

`musique_inference.py` can read either:

- `.json`: one regular JSON dataset file
- `.jsonl`: JSON Lines, where each line is one standalone JSON object

For the bundled MuSiQue file, the loader reads the top-level `data` array.

In this project, `.jsonl` output is mainly used for QA prediction logs. Each line stores one evaluated sample:

```json
{"sample_id": "2hop__121145_561444", "answer": "Minnesota"}
```

## Build The MuSiQue Graph

Use the MuSiQue config file explicitly. The script's fallback config path does not point to the current `configs/` directory.

```bash
PYTHONPATH=/absolute/path/to/Wikontic/src python3 inference_and_eval/musique_inference.py \
  --config inference_and_eval/configs/musique_inference_with_db.yaml
```

Default config:

```yaml
mongo_uri: "mongodb://localhost:27018/?directConnection=true"
ontology_db_name: "wikidata_ontology"
triplets_db_name: "triplets_db"
model_name: "gpt-4o-mini"
dataset_path: "datasets/musique_200_test.json"
start_index: 82
num_samples: 50
structured_inference: false
```

Important MuSiQue slicing detail: the script starts from `start_index` and processes `num_samples` examples:

```python
sampled_ids = list(id2sample.keys())[cfg.start_index : cfg.start_index + cfg.num_samples]
```

With the default config:

- `start_index: 82`
- `num_samples: 50`

the script processes 50 samples, indices 82 through 131.

## Structured/Ontology Run

To follow the ontology-aware path described in the paper, set this in the YAML config:

```yaml
structured_inference: true
```

Then run:

```bash
PYTHONPATH=/absolute/path/to/Wikontic/src python3 inference_and_eval/musique_inference.py \
  --config inference_and_eval/configs/musique_inference_with_db.yaml
```

The graph database name is created from the base database name, model name, and inference mode:

```text
triplets_db_<model_name>_onto
```

For example, with `model_name: gpt-4o-mini`:

```text
triplets_db_gpt-4o-mini_onto
```

## Non-Ontology Run

For the faster dynamic path, keep:

```yaml
structured_inference: false
```

Then run:

```bash
PYTHONPATH=/absolute/path/to/Wikontic/src python3 inference_and_eval/musique_inference.py \
  --config inference_and_eval/configs/musique_inference_with_db.yaml
```

The graph database name ends with:

```text
_non_onto
```

For example, with `model_name: gpt-4o-mini`:

```text
triplets_db_gpt-4o-mini_non_onto
```

## Run QA Evaluation

Pass the exact triplet database created during graph construction.

### Non-ontology example

```bash
PYTHONPATH=/absolute/path/to/Wikontic/src python3 inference_and_eval/qa_eval_musique.py \
  --mongo_uri "mongodb://localhost:27018/?directConnection=true" \
  --ontology_db_name wikidata_ontology \
  --triplets_db_name triplets_db_gpt-4o-mini_non_onto \
  --model_name gpt-4o-mini \
  --dataset_path datasets/musique_200_test.json \
  --no_structured_inference \
  --run_number 1
```

### Structured + multi-step example

```bash
PYTHONPATH=/absolute/path/to/Wikontic/src python3 inference_and_eval/qa_eval_musique.py \
  --mongo_uri "mongodb://localhost:27018/?directConnection=true" \
  --ontology_db_name wikidata_ontology \
  --triplets_db_name triplets_db_gpt-4o-mini_onto \
  --model_name gpt-4o-mini \
  --dataset_path datasets/musique_200_test.json \
  --structured_inference \
  --multi-step-qa \
  --run_number 1
```

## Fast Sanity Check

Before a long run, change the MuSiQue config to:

```yaml
num_samples: 2
```

This processes two samples from the configured `start_index`.

Build the graph:

```bash
PYTHONPATH=/absolute/path/to/Wikontic/src python3 inference_and_eval/musique_inference.py \
  --config inference_and_eval/configs/musique_inference_with_db.yaml
```

Then run evaluation with the matching database name:

```bash
PYTHONPATH=/absolute/path/to/Wikontic/src python3 inference_and_eval/qa_eval_musique.py \
  --triplets_db_name triplets_db_gpt-4o-mini_non_onto \
  --model_name gpt-4o-mini \
  --dataset_path datasets/musique_200_test.json \
  --no_structured_inference \
  --run_number 1
```

## Where The Results Go

### 1. Prediction logs

The evaluation script writes answers to:

```text
qa_logs/
```

Example filename:

```text
qa_logs/triplets_db_gpt-4o-mini_non_onto_gpt-4o-mini_structured_False_multi_step_False_use_qualifiers_True_use_filtered_triplets_False_musique_test_run_1.jsonl
```

Each line is one JSON object:

```json
{"sample_id": "2hop__121145_561444", "answer": "Minnesota"}
```

This `.jsonl` file is the prediction log. It can be appended while the evaluation is running, which is why JSON Lines is used instead of one large JSON array.

### 2. Final metrics

At the end of the run, the script prints:

```json
{
  "evaluated_samples": 50,
  "requested_samples": 50,
  "em": 0.28,
  "f1": 0.41
}
```

Meaning:

- `evaluated_samples`: number of questions that produced an answer
- `requested_samples`: number of sample IDs found in MongoDB
- `em`: exact match after normalization
- `f1`: token-level F1 after normalization

## Files Involved

- `inference_and_eval/musique_inference.py`
- `inference_and_eval/qa_eval_musique.py`
- `inference_and_eval/configs/musique_inference_with_db.yaml`
- `datasets/musique_200_test.json`
- `src/wikontic/utils/openai_utils.py`
- `qa_logs/`
