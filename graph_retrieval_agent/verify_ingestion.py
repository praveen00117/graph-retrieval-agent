from __future__ import annotations

from .graph_db import graph_db


def main() -> None:
    print("L0-L4 node counts")
    print("=" * 60)
    counts = graph_db.run(
        """
        MATCH (n)
        WHERE n.layer IS NOT NULL
        RETURN n.layer AS layer, labels(n)[0] AS node_type, count(*) AS count
        ORDER BY layer, node_type
        """
    )
    for row in counts:
        print(f"{row['layer']:<3} {row['node_type']:<24} {row['count']}")

    print("\nCustomer Onboarding graph relationships")
    print("=" * 60)
    rows = graph_db.run(
        """
        MATCH (a)-[r]->(b)
        WHERE 'Customer Onboarding' IN coalesce(r.process_contexts, [])
        RETURN
            a.id AS source_id,
            type(r) AS relationship_type,
            b.id AS target_id
        ORDER BY source_id, relationship_type, target_id
        """
    )
    for row in rows:
        print(
            f"{row['source_id']} -[{row['relationship_type']}]-> {row['target_id']}"
        )

    print("\nSummary")
    print("=" * 60)
    summary = graph_db.run(
        """
        MATCH (n)
        WITH count(n) AS nodes
        MATCH ()-[r]->()
        RETURN nodes, count(r) AS relationships
        """
    )
    print(summary[0] if summary else {"nodes": 0, "relationships": 0})


if __name__ == "__main__":
    main()
