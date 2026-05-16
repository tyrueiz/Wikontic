
# `qa_eval_hotpot` Runbook

  

## Prerequisites

  

### 1. Python environment

  

Run commands from the Wikontic repo root:

  

```bash

cd  Wikontic

```

  

Install dependencies before running anything:

  

```bash

pip  install  -r  requirements.txt

```

  

Use the local source tree with:

  

```bash

PYTHONPATH=/absolute/path/to/Wikontic/src

```

  

Replace `/absolute/path/to/Wikontic` with the actual absolute path to your local Wikontic repository.

  

Example:

  

```bash

PYTHONPATH=/home/mplgg/Wikontic_fork/Wikontic/src

```

  

### 2. MongoDB

  

Start MongoDB with:

  

```bash

./setup_db.sh

```


  

## Structured + multi-step

  

### 1. Build the graph

  

```bash

PYTHONPATH=/absolute/path/to/Wikontic/src  python3  inference_and_eval/hotpot_inference_with_db.py  

--mongo_uri  "mongodb://localhost:27018/?directConnection=true"  

--ontology_db_name  wikidata_ontology  

--triplets_db_name triplets_db  

--model_name  openai/gpt-oss-120b  

--dataset_path  datasets/hotpotqa200.json  

--num_samples  50

--structured_inference

```

  

### 2. Run QA evaluation

  

```bash

PYTHONPATH=/absolute/path/to/Wikontic/src  python3  inference_and_eval/qa_eval_hotpot.py  

--structured_inference  

--multi-step-qa  

```




## Fast sanity-check run

  

Before a long run, test with a small sample count:

  
### 1. Build the graph

  

```bash

PYTHONPATH=/absolute/path/to/Wikontic/src  python3  inference_and_eval/hotpot_inference_with_db.py  

--mongo_uri  "mongodb://localhost:27018/?directConnection=true"  

--ontology_db_name  wikidata_ontology  

--triplets_db_name triplets_db  

--model_name  openai/gpt-oss-120b  

--dataset_path  datasets/hotpotqa200.json  

--num_samples  2

--structured_inference

```

  

### 2. Run QA evaluation

  

```bash

PYTHONPATH=/absolute/path/to/Wikontic/src  python3  inference_and_eval/qa_eval_hotpot.py  \

--no_structured_inference  

--no_multi-step-qa  

```

  

## Where the results go

  

### 1. Prediction logs

  

The script writes answers to:

  

```text

qa_logs/

```

  

Example filename:

  

```text

qa_logs/triplets_db_hotpot_basic_openai_gpt-oss-120b_structured_False_multi_step_False_use_qualifiers_True_use_filtered_triplets_False_hotpot_test_run_1.jsonl

```

  

Each line looks like:

  

```json

{"sample_id": "5a7180205542994082a3e856", "answer": "Creature Comforts"}

```

  

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

  

-  `evaluated_samples`: number of questions that produced an answer

-  `requested_samples`: number of sample IDs found in MongoDB

-  `em`: exact match after normalization

-  `f1`: token-level F1 after normalization

  

## Files involved

  

-  `inference_and_eval/hotpot_inference_with_db.py`

-  `inference_and_eval/qa_eval_hotpot.py`

-  `datasets/hotpotqa200.json`

-  `src/wikontic/utils/openai_utils.py`

-  `qa_logs/`
