import requests
from requests.auth import HTTPBasicAuth

from .config import settings


class GraphDB:
    def __init__(self):
        self.url = settings.neo4j_query_url
        self.auth = HTTPBasicAuth(
            settings.neo4j_username,
            settings.neo4j_password,
        )

    def close(self):
        return None

    def run(self, query: str, parameters: dict | None = None):
        response = requests.post(
            self.url,
            auth=self.auth,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json={
                "statement": query,
                "parameters": parameters or {},
            },
            timeout=30,
        )

        if not response.ok:
            raise RuntimeError(
                f"Neo4j Query API failed "
                f"({response.status_code}): {response.text}"
            )

        payload = response.json()

        data = payload.get("data", {})
        fields = data.get("fields", [])
        values = data.get("values", [])

        return [
            dict(zip(fields, row))
            for row in values
        ]


graph_db = GraphDB()