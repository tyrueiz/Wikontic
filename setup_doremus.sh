#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

CONTAINER_NAME="${CONTAINER_NAME:-text2kg_mongo}"
MONGO_IMAGE="${MONGO_IMAGE:-mongodb/mongodb-atlas-local:latest}"
MONGO_PORT="${MONGO_PORT:-27018}"
MONGO_URI="${MONGO_URI:-mongodb://localhost:${MONGO_PORT}/?directConnection=true}"
ONTOLOGY_DB_NAME="${ONTOLOGY_DB_NAME:-doremus_ontology}"
TRIPLETS_DB_NAME="${TRIPLETS_DB_NAME:-doremus_triplets_db}"
DOREMUS_TTL_PATH="${DOREMUS_TTL_PATH:-preprocessing/doremus.ttl}"
DOREMUS_MAPPINGS_DIR="${DOREMUS_MAPPINGS_DIR:-src/wikontic/utils/ontology_mappings_doremus}"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required but was not found in PATH." >&2
  exit 1
fi

if ! docker ps -a --format '{{.Names}}' | grep -Fxq "${CONTAINER_NAME}"; then
  docker pull "${MONGO_IMAGE}"
  docker run --name "${CONTAINER_NAME}" -d -p "${MONGO_PORT}:27017" "${MONGO_IMAGE}"
elif ! docker ps --format '{{.Names}}' | grep -Fxq "${CONTAINER_NAME}"; then
  docker start "${CONTAINER_NAME}"
fi

cd "${SCRIPT_DIR}"

python3 preprocessing/doremus_preprocessing.py \
  --ttl_path "${DOREMUS_TTL_PATH}" \
  --output_dir "${DOREMUS_MAPPINGS_DIR}"

cd src/wikontic

python3 create_wikidata_ontology_db.py \
  --mongo_uri "${MONGO_URI}" \
  --database "${ONTOLOGY_DB_NAME}" \
  --mappings_dir "utils/ontology_mappings_doremus/"

python3 create_ontological_triplets_db.py \
  --mongo_uri "${MONGO_URI}" \
  --db_name "${TRIPLETS_DB_NAME}"

cd ../..

cat <<EOF
DOREMUS setup complete.

Mongo URI: ${MONGO_URI}
Ontology DB: ${ONTOLOGY_DB_NAME}
Triplets DB: ${TRIPLETS_DB_NAME}

Use these DB names in inference/eval commands, for example:
  --ontology_db_name ${ONTOLOGY_DB_NAME} --triplets_db_name ${TRIPLETS_DB_NAME}
EOF
