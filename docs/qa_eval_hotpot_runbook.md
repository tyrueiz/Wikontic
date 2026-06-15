# `qa_eval_hotpot` Runbook

## Prerequisites

Run commands from the repo root:

```bash
cd /absolute/path/to/Wikontic
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Use the local source tree:

```bash
export PYTHONPATH=/absolute/path/to/Wikontic/src
```

Example:

```bash
export PYTHONPATH=/home/mplgg/Wikontic_fork/Wikontic/src
```

Start MongoDB:

```bash
./setup_db.sh
```

## Structured + multi-step

### 1. Build the graph

```bash
CUDA_VISIBLE_DEVICES=1 \
OPENAI_API_KEY=fake \
WIKONTIC_BASE_URL=https://wikontic-vllm.tools.eurecom.fr/v1 \
PYTHONPATH=/absolute/path/to/Wikontic/src \
/absolute/path/to/Wikontic/.venv/bin/python inference_and_eval/hotpot_inference_with_db.py \
  --mongo_uri "mongodb://localhost:27018/?directConnection=true" \
  --ontology_db_name wikidata_ontology \
  --triplets_db_name hotpotqa \
  --model_name openai/gpt-oss-120b \
  --dataset_path datasets/hotpotqa.json \
  --num_samples 1000 \
  --structured_inference
```

### 2. Run QA evaluation

```bash
CUDA_VISIBLE_DEVICES=1 \
OPENAI_API_KEY=fake \
PYTHONPATH=/absolute/path/to/Wikontic/src \
/absolute/path/to/Wikontic/.venv/bin/python inference_and_eval/qa_eval_hotpot.py \
  --mongo_uri "mongodb://localhost:27018/?directConnection=true" \
  --ontology_db_name wikidata_ontology \
  --triplets_db_name hotpotqa \
  --model_name openai/gpt-oss-120b \
  --dataset_path datasets/hotpotqa.json \
  --structured_inference \
  --multi-step-qa
```

This is the safest pattern: pass all relevant parameters explicitly instead of relying on defaults.

### Reported final scores

For the full structured + multi-step run above, the reported output was:

```json
{
  "evaluated_samples": 1000,
  "requested_samples": 1000,
  "em": 0.515,
  "f1": 0.649,
  "prompt_tokens": 5684130,
  "completion_tokens": 1713206,
  "total_tokens": 7397336,
  "estimated_cost": 0.626848
}
```

## Fast sanity-check run

Before a long run, test with a small sample count.

### 1. Build the graph

```bash
PYTHONPATH=/absolute/path/to/Wikontic/src \
python3 inference_and_eval/hotpot_inference_with_db.py \
  --mongo_uri "mongodb://localhost:27018/?directConnection=true" \
  --ontology_db_name wikidata_ontology \
  --triplets_db_name hotpotqa_sanity \
  --model_name openai/gpt-oss-120b \
  --dataset_path datasets/hotpotqa200.json \
  --num_samples 2 \
  --structured_inference
```

### 2. Run QA evaluation

```bash
PYTHONPATH=/absolute/path/to/Wikontic/src \
python3 inference_and_eval/qa_eval_hotpot.py \
  --mongo_uri "mongodb://localhost:27018/?directConnection=true" \
  --ontology_db_name wikidata_ontology \
  --triplets_db_name hotpotqa_sanity \
  --model_name openai/gpt-oss-120b \
  --dataset_path datasets/hotpotqa200.json \
  --structured_inference \
  --multi-step-qa
```

## Where the results go

### 1. Prediction logs

The script writes answers to:

```text
qa_logs/
```

Example filename:

```text
qa_logs/hotpotqa_openai_gpt-oss-120b_structured_True_multi_step_True_use_qualifiers_True_use_filtered_triplets_False_hotpot_test_run_1.jsonl
```

Each line looks like:

```json
{"sample_id": "5a7180205542994082a3e856", "answer": "Creature Comforts"}
```

### 2. Final metrics

At the end of the run, the script prints something like:

```json
{
  "evaluated_samples": 50,
  "requested_samples": 50,
  "em": 0.28,
  "f1": 0.41,
  "prompt_tokens": 123456,
  "completion_tokens": 7890,
  "total_tokens": 131346,
  "estimated_cost": 0.007654
}
```

Meaning:

- `evaluated_samples`: predictions that were actually produced
- `requested_samples`: sample IDs found in Mongo
- `em`: exact match
- `f1`: token-level F1
- `prompt_tokens`: input tokens used
- `completion_tokens`: output tokens used
- `total_tokens`: total token usage
- `estimated_cost`: cost estimate from the model price table

