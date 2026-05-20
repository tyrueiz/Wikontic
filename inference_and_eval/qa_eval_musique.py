import json
from tqdm import tqdm
import argparse
import warnings
import re
from unidecode import unidecode
from pymongo.mongo_client import MongoClient
import string
import os

from wikontic.utils.structured_aligner import Aligner as StructuredDBAligner
from wikontic.utils.dynamic_aligner import Aligner as DynamicDBAligner
from wikontic.utils.structured_inference_with_db import StructuredInferenceWithDB
from wikontic.utils.inference_with_db import InferenceWithDB
from wikontic.utils.openai_utils import LLMTripletExtractor

import logging
import jsonlines
from dotenv import load_dotenv, find_dotenv

logger = logging.getLogger("QAEvalMusique")
logger.setLevel(logging.ERROR)

warnings.filterwarnings("ignore")
_ = load_dotenv(find_dotenv())


def normalize(input_string):
    input_string = unidecode(input_string)
    input_string = input_string.lower()

    # Remove commas and periods between digits (e.g., 7,531 or 7.531 -> 7531)
    input_string = re.sub(r"(?<=\d)[,\.](?=\d)", "", input_string)

    # Replace all other punctuation with a space
    input_string = re.sub(f"[{re.escape(string.punctuation)}]", " ", input_string)

    # Replace multiple spaces with a single space
    input_string = re.sub(r"\s+", " ", input_string)

    # Trim leading/trailing whitespace
    return input_string.strip()


def exact_match_score(prediction, ground_truth):
    return float(normalize(prediction) == normalize(ground_truth))


def f1_score(prediction, ground_truth):
    pred_tokens = normalize(prediction).split()
    gold_tokens = normalize(ground_truth).split()

    if not pred_tokens and not gold_tokens:
        return 1.0
    if not pred_tokens or not gold_tokens:
        return 0.0

    common = {}
    for token in pred_tokens:
        common[token] = common.get(token, 0) + 1

    num_same = 0
    for token in gold_tokens:
        if common.get(token, 0) > 0:
            num_same += 1
            common[token] -= 1

    if num_same == 0:
        return 0.0

    precision = num_same / len(pred_tokens)
    recall = num_same / len(gold_tokens)
    return 2 * precision * recall / (precision + recall)


def get_mongo_client(mongo_uri):
    client = MongoClient(mongo_uri)
    return client


def get_dataset(dataset_path):
    with open(dataset_path, "r") as f:
        ds = json.load(f)
    if isinstance(ds, dict) and "data" in ds:
        return ds["data"]
    return ds


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mongo_uri",
        type=str,
        default="mongodb://localhost:27018/?directConnection=true",
    )
    parser.add_argument("--ontology_db_name", type=str, default="wikidata_ontology")
    parser.add_argument("--triplets_db_name", type=str, default="triplets_db")
    parser.add_argument("--model_name", type=str, default="openai/gpt-oss-20b")
    parser.add_argument(
        "--dataset_path", type=str, default="datasets/musique_200_test.json"
    )
    parser.add_argument(
        "--structured_inference",
        action="store_true",
        help="Enable structured inference",
    )
    parser.add_argument(
        "--no_structured_inference",
        action="store_false",
        dest="structured_inference",
        help="Disable structured inference",
    )
    parser.add_argument(
        "--multi-step-qa", action="store_true", help="Enable multi-step QA"
    )
    parser.add_argument("--use_qualifiers", action="store_true", help="Use qualifiers")
    parser.add_argument(
        "--no_use_qualifiers",
        action="store_false",
        dest="use_qualifiers",
        help="Do not use qualifiers",
    )
    parser.add_argument(
        "--use_filtered_triplets", action="store_true", help="Use filtered triplets"
    )
    parser.add_argument(
        "--no_use_filtered_triplets",
        action="store_false",
        dest="use_filtered_triplets",
        help="Do not use filtered triplets",
    )
    parser.add_argument("--run_number", type=int, default=1, help="Run number")
    parser.set_defaults(structured_inference=False)
    parser.set_defaults(use_qualifiers=True)
    parser.set_defaults(use_filtered_triplets=False)
    return parser.parse_args()


if __name__ == "__main__":

    args = get_args()
    mongo_client = get_mongo_client(args.mongo_uri)
    db = mongo_client.get_database(args.ontology_db_name)

    triplets_db = mongo_client.get_database(args.triplets_db_name)
    ontology_db = mongo_client.get_database(args.ontology_db_name)

    api_key = os.getenv("OPENAI_API_KEY")
    proxy_url = os.getenv("PROXY_URL")

    model_name = args.model_name
    dataset_path = args.dataset_path
    use_qualifiers = args.use_qualifiers
    use_filtered_triplets = args.use_filtered_triplets

    os.makedirs("qa_logs", exist_ok=True)

    logger.info(f"Use qualifier: {args.use_qualifiers}")
    logger.info(f"Use filtered triplets: {args.use_filtered_triplets}")
    ds = get_dataset(dataset_path)

    id2sample = {}
    for elem in ds:
        id2sample[elem["id"]] = elem
        if "answerable" in elem:
            answerable = "Answerable" if elem["answerable"] else "Unanswerable"
            id2sample[f"{elem['id']}_{answerable}"] = elem

    if args.structured_inference:
        logger.info("Structured inference enabled")
        aligner = StructuredDBAligner(ontology_db=ontology_db, triplets_db=triplets_db)
    else:
        logger.info("Structured inference disabled, using dynamic inference")
        aligner = DynamicDBAligner(triplets_db=triplets_db)

    extractor = LLMTripletExtractor(model=model_name, api_key=api_key, proxy=proxy_url)

    if args.structured_inference:
        inference_with_db = StructuredInferenceWithDB(
            extractor=extractor, aligner=aligner, triplets_db=triplets_db
        )
    else:
        inference_with_db = InferenceWithDB(
            extractor=extractor, aligner=aligner, triplets_db=triplets_db
        )

    unique_sample_ids = triplets_db.get_collection("triplets").distinct("sample_id")

    if args.multi_step_qa:
        logger.info(f"Enabled multi-step QA")
    else:
        logger.info(f"Disabled multi-step QA")

    sample_id2ans = {}
    if args.multi_step_qa:

        for sample_id in tqdm(unique_sample_ids):
            question = None
            try:
                question = id2sample[sample_id]["question"]
                ans = inference_with_db.answer_with_qa_collapsing(
                    question,
                    sample_id,
                    use_qualifiers=use_qualifiers,
                    use_filtered_triplets=use_filtered_triplets,
                )

                if isinstance(ans, int):
                    ans = str(ans)

                sample_id2ans[sample_id] = ans
                with jsonlines.open(
                    f"qa_logs/{args.triplets_db_name}_{args.model_name.replace('/', '_')}_structured_{args.structured_inference}_multi_step_{args.multi_step_qa}_use_qualifiers_{args.use_qualifiers}_use_filtered_triplets_{args.use_filtered_triplets}_musique_test_run_{str(args.run_number)}.jsonl",
                    "a",
                ) as f:
                    f.write({"sample_id": sample_id, "answer": ans})

                logger.info("-" * 100)
                logger.info(
                    sample_id,
                    " | ",
                    question,
                    " | ",
                    ans,
                    " | ",
                    normalize(ans),
                    " | ",
                    id2sample[sample_id]["answer"],
                    " | ",
                    normalize(id2sample[sample_id]["answer"]),
                )
            except Exception as e:
                logger.error(f"Error for sample_id={sample_id}, question={question}: {e}")
                continue

    else:
        for sample_id in tqdm(unique_sample_ids):
            question = None
            try:
                question = id2sample[sample_id]["question"]
                identified_entities = (
                    inference_with_db.identify_relevant_entities_from_question_with_llm(
                        question=question, sample_id=sample_id
                    )
                )

                if not identified_entities:
                    logger.error(
                        f"[DEBUG] No entities identified for sample_id={sample_id}, question={question}"
                    )
                supporting_triplets, ans = inference_with_db.answer_question_with_llm(
                    question=question,
                    linked_entities=identified_entities,
                    sample_id=sample_id,
                    use_qualifiers=use_qualifiers,
                    use_filtered_triplets=use_filtered_triplets,
                )

                if isinstance(ans, int):
                    ans = str(ans)

                sample_id2ans[sample_id] = ans

                with jsonlines.open(
                    f"qa_logs/{args.triplets_db_name}_{args.model_name.replace('/', '_')}_structured_{args.structured_inference}_multi_step_{args.multi_step_qa}_use_qualifiers_{args.use_qualifiers}_use_filtered_triplets_{args.use_filtered_triplets}_musique_test_run_{str(args.run_number)}.jsonl",
                    "a",
                ) as f:
                    f.write({"sample_id": sample_id, "answer": ans})

                logger.info(
                    sample_id,
                    " | ",
                    question,
                    " | ",
                    ans,
                    " | ",
                    normalize(ans),
                    " | ",
                    id2sample[sample_id]["answer"],
                    " | ",
                    normalize(id2sample[sample_id]["answer"]),
                )
                logger.info("-" * 100)
            except Exception as e:
                logger.error(
                    f"Error for sample_id={sample_id}, question={question}: {e}"
                )
                continue

    evaluated_sample_ids = [sample_id for sample_id in unique_sample_ids if sample_id in sample_id2ans]
    if evaluated_sample_ids:
        em = sum(
            exact_match_score(sample_id2ans[sample_id], id2sample[sample_id]["answer"])
            for sample_id in evaluated_sample_ids
        ) / len(evaluated_sample_ids)
        f1 = sum(
            f1_score(sample_id2ans[sample_id], id2sample[sample_id]["answer"])
            for sample_id in evaluated_sample_ids
        ) / len(evaluated_sample_ids)
        print(
            json.dumps(
                {
                    "evaluated_samples": len(evaluated_sample_ids),
                    "requested_samples": len(unique_sample_ids),
                    "em": round(em, 4),
                    "f1": round(f1, 4),
                },
                indent=2,
            )
        )
    else:
        print(
            json.dumps(
                {
                    "evaluated_samples": 0,
                    "requested_samples": len(unique_sample_ids),
                    "em": 0.0,
                    "f1": 0.0,
                },
                indent=2,
            )
        )