import argparse
import json
from collections import defaultdict, deque
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

try:
    from rdflib import BNode, Graph, Literal, Namespace, RDF, RDFS, OWL, SKOS, URIRef
except ImportError as exc:  # pragma: no cover - runtime dependency guard
    raise SystemExit(
        "This script requires rdflib. Install it with: pip install rdflib"
    ) from exc


DOREMUS = Namespace("http://data.doremus.org/ontology#")
XSD_NS = "http://www.w3.org/2001/XMLSchema#"


def choose_label(graph: Graph, node) -> Optional[str]:
    labels = [str(label) for label in graph.objects(node, RDFS.label)]
    if not labels:
        return None

    english_labels = [
        str(label) for label in graph.objects(node, RDFS.label) if getattr(label, "language", None) == "en"
    ]
    if english_labels:
        return english_labels[0]
    return labels[0]


def compact_term(graph: Graph, term) -> Optional[str]:
    if term is None or isinstance(term, BNode):
        return None
    if isinstance(term, Literal):
        if term.datatype:
            return compact_term(graph, term.datatype)
        return "Literal"
    if not isinstance(term, URIRef):
        return str(term)

    uri = str(term)
    if uri.startswith(str(DOREMUS)):
        return uri.split("#", 1)[1]
    if uri.startswith(XSD_NS):
        return f"xsd:{uri.rsplit('#', 1)[1]}"

    try:
        prefix, _, local = graph.namespace_manager.compute_qname(term)
        return f"{prefix}:{local}"
    except Exception:
        if "#" in uri:
            return uri.rsplit("#", 1)[1]
        return uri.rsplit("/", 1)[-1]


def collect_classes(graph: Graph) -> Set[URIRef]:
    class_nodes: Set[URIRef] = {
        node for node in graph.subjects(RDF.type, OWL.Class) if isinstance(node, URIRef)
    }
    class_nodes.update(
        node for node in graph.subjects(RDF.type, RDFS.Class) if isinstance(node, URIRef)
    )

    for predicate in (RDFS.domain, RDFS.range, RDFS.subClassOf):
        for subject, obj in graph.subject_objects(predicate):
            if predicate == RDFS.subClassOf and isinstance(subject, URIRef):
                class_nodes.add(subject)
            if isinstance(obj, URIRef):
                class_nodes.add(obj)

    return class_nodes


def collect_properties(graph: Graph) -> List[Tuple[URIRef, str]]:
    properties: List[Tuple[URIRef, str]] = []
    seen: Set[URIRef] = set()
    for prop_type, data_type in (
        (OWL.ObjectProperty, "Entity"),
        (OWL.DatatypeProperty, "Literal"),
    ):
        for node in graph.subjects(RDF.type, prop_type):
            if isinstance(node, URIRef) and node not in seen:
                seen.add(node)
                properties.append((node, data_type))
    return properties


def build_hierarchy(
    graph: Graph, class_id_map: Dict[URIRef, str]
) -> Dict[str, List[str]]:
    direct_parents: Dict[str, Set[str]] = defaultdict(set)
    for child, parent in graph.subject_objects(RDFS.subClassOf):
        if child in class_id_map and isinstance(parent, URIRef) and parent in class_id_map:
            direct_parents[class_id_map[child]].add(class_id_map[parent])

    hierarchy: Dict[str, List[str]] = {}
    for class_id in class_id_map.values():
        visited: Set[str] = set()
        queue = deque([class_id])
        while queue:
            current = queue.popleft()
            if current in visited:
                continue
            visited.add(current)
            queue.extend(direct_parents.get(current, []))
        hierarchy[class_id] = sorted(visited)
    return hierarchy


def main():
    parser = argparse.ArgumentParser(
        description="Generate ontology mapping JSON files from doremus.ttl"
    )
    parser.add_argument(
        "--ttl_path",
        default="preprocessing/doremus.ttl",
        help="Path to the DOREMUS Turtle ontology file",
    )
    parser.add_argument(
        "--output_dir",
        default="src/wikontic/utils/ontology_mappings_doremus",
        help="Directory where ontology mapping JSON files will be written",
    )
    args = parser.parse_args()

    ttl_path = Path(args.ttl_path)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    graph = Graph()
    graph.parse(ttl_path, format="turtle")

    class_nodes = collect_classes(graph)
    property_nodes = collect_properties(graph)

    class_id_map: Dict[URIRef, str] = {}
    entity_type2label: Dict[str, str] = {}
    for node in sorted(class_nodes, key=str):
        class_id = compact_term(graph, node)
        if class_id is None:
            continue
        class_id_map[node] = class_id
        label = choose_label(graph, node) or class_id.replace("_", " ")
        entity_type2label[class_id] = label

    entity_type2hierarchy = build_hierarchy(graph, class_id_map)

    prop2label: Dict[str, str] = {}
    prop2constraints: Dict[str, Dict[str, List[str]]] = {}

    for node, _ in sorted(property_nodes, key=lambda item: str(item[0])):
        prop_id = compact_term(graph, node)
        if prop_id is None:
            continue

        label = choose_label(graph, node) or prop_id.replace("_", " ")
        prop2label[prop_id] = label

        subject_constraints = sorted(
            {
                constraint_id
                for obj in graph.objects(node, RDFS.domain)
                if (constraint_id := compact_term(graph, obj)) is not None
            }
        )
        value_constraints = sorted(
            {
                constraint_id
                for obj in graph.objects(node, RDFS.range)
                if (constraint_id := compact_term(graph, obj)) is not None
            }
        )

        prop2constraints[prop_id] = {
            "Subject type constraint": subject_constraints or ["ANY"],
            "Value-type constraint": value_constraints or ["ANY"],
        }

    outputs = {
        "entity_type2label.json": entity_type2label,
        "entity_type2hierarchy.json": entity_type2hierarchy,
        "prop2label.json": prop2label,
        "prop2constraints.json": prop2constraints,
    }

    for filename, payload in outputs.items():
        with open(output_dir / filename, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)

    print(f"Wrote DOREMUS ontology mappings to {output_dir}")


if __name__ == "__main__":
    main()
