# Graph Retrieval Agent — Code Through Task 4

This package intentionally stops at **Task 4: Implement Ingestion Agent & Neo4j Graph Creation**.
It does **not** include incident understanding, graph retrieval, FastAPI retrieval endpoints, or Streamlit retrieval UI.

## Jira task coverage

### Task 1 — Define L0-L4 Graph Schema & Relationships
Implemented in `graph_retrieval_task4/graph_schema.py`.

L0-L4 model:
- L0: `StrategicGoal`
- L1: `Obligation`
- L2: `BusinessProcess`, `ProcessStep`
- L3: `Service`, `API`
- L4: `Environment`, `TestDataRequirement`, `AutomationTest`

Allowed relationships:
- `StrategicGoal -[:DRIVES]-> Obligation`
- `Obligation -[:FULFILLED_BY]-> BusinessProcess`
- `BusinessProcess -[:HAS_STEP]-> ProcessStep`
- `ProcessStep -[:NEXT_STEP]-> ProcessStep`
- `ProcessStep -[:SUPPORTED_BY]-> Service`
- `Service -[:EXPOSES]-> API`
- `Service -[:DEPENDS_ON]-> Service`
- `Service -[:DEPLOYED_TO]-> Environment`
- `API -[:REQUIRES_TEST_DATA]-> TestDataRequirement`
- `API -[:VALIDATED_BY]-> AutomationTest`

### Task 2 — Create Dummy Customer Onboarding Dataset
Implemented as semi-structured source data in:
`graph_retrieval_task4/data/customer_onboarding_source.md`

This is intentionally not a graph-ready Excel structure.

### Task 3 — Design Ingestion Agent
Implemented in `graph_retrieval_task4/ingestion_agent.py`.

Flow:

`Semi-structured source -> LLM extraction -> entity/relationship normalization -> schema validation -> normalized L0-L4 graph`

The `preview` / `preview_file` methods perform extraction and validation without writing to Neo4j.

### Task 4 — Implement Ingestion Agent & Neo4j Graph Creation
Implemented in:
- `ingestion_agent.py` — extraction, normalization, validation, constraints and graph upsert
- `graph_db.py` — Neo4j HTTPS Query API connector
- `demo_ingestion.py` — preview / write runner
- `verify_ingestion.py` — validates the created graph

## Setup

Create and activate a virtual environment, then install dependencies:

```bash
python -m pip install -r graph_retrieval_task4/requirements.txt
```

Copy `.env.example` to `.env` in the project root and set your own credentials.

Required environment variables:

```env
NEO4J_QUERY_URL=...
NEO4J_USERNAME=...
NEO4J_PASSWORD=...
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-5.6-luna
```

## 1. Preview ingestion

```bash
python -m graph_retrieval_task4.demo_ingestion
```

This prints the normalized entities and relationships but does not modify Neo4j.

## 2. Write graph to Neo4j

```bash
python -m graph_retrieval_task4.demo_ingestion --write
```

Expected result for the bundled source is approximately:

```text
status: success
source_name: customer_onboarding_source.md
nodes_upserted: 29
relationships_upserted: 41
validation_warnings: []
```

LLM extraction can vary, so review the preview before writing.

## 3. Verify graph creation

```bash
python -m graph_retrieval_task4.verify_ingestion
```

This shows L0-L4 counts and the Customer Onboarding relationships stored in Neo4j.

## Optional: clean POC graph before a fresh run

Only use this against your disposable POC database:

```bash
python -c "from graph_retrieval_task4.graph_db import graph_db; graph_db.run('MATCH (n) DETACH DELETE n'); print('Graph data deleted')"
```

## Deliberately excluded because they are Task 5+

- `agent.py` incident understanding
- `retrieval.py` incident-based subgraph retrieval
- retrieval FastAPI endpoints
- retrieval Streamlit UI
- Incoming Credit Payment / additional business-process scenarios
- Impact Analysis / Blast Radius / Manifest generation
