from datetime import datetime, timezone
from typing import Dict, List, Optional

import networkx as nx
from sqlalchemy import create_engine, Column, String, Text, Integer, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker

from app.backend.config.settings import settings


Base = declarative_base()


class GraphNode(Base):
    __tablename__ = "graph_nodes"

    node_id = Column(String, primary_key=True)
    display_name = Column(String, nullable=False)
    mention_count = Column(Integer, nullable=False, default=1)
    source_file_ids = Column(Text, nullable=False, default="")
    created_at = Column(DateTime, nullable=False)


class GraphEdge(Base):
    __tablename__ = "graph_edges"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_id = Column(String, ForeignKey("graph_nodes.node_id"), nullable=False)
    target_id = Column(String, ForeignKey("graph_nodes.node_id"), nullable=False)
    relationship = Column(String, nullable=False)
    file_id = Column(String, nullable=True)
    evidence = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False)


class GraphStoreService:
    def __init__(self):
        self.engine = create_engine(settings.postgres_url)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)

    def _normalize(self, name: str) -> str:
        return name.strip().lower()

    def upsert_node(self, name: str, file_id: Optional[str] = None) -> str:
        node_id = self._normalize(name)

        session = self.SessionLocal()
        try:
            node = session.query(GraphNode).filter_by(node_id=node_id).first()

            if node:
                node.mention_count += 1

                existing_file_ids = [f for f in node.source_file_ids.split(",") if f]
                if file_id and file_id not in existing_file_ids:
                    existing_file_ids.append(file_id)
                    node.source_file_ids = ",".join(existing_file_ids)
            else:
                node = GraphNode(
                    node_id=node_id,
                    display_name=name.strip(),
                    mention_count=1,
                    source_file_ids=file_id or "",
                    created_at=datetime.now(timezone.utc)
                )
                session.add(node)

            session.commit()
            return node_id
        finally:
            session.close()

    def upsert_edge(
        self,
        source_name: str,
        target_name: str,
        relationship: str,
        file_id: Optional[str] = None,
        evidence: Optional[str] = None
    ) -> None:
        source_id = self.upsert_node(source_name, file_id)
        target_id = self.upsert_node(target_name, file_id)

        session = self.SessionLocal()
        try:
            existing = (
                session.query(GraphEdge)
                .filter_by(source_id=source_id, target_id=target_id, relationship=relationship)
                .first()
            )

            if existing:
                return

            edge = GraphEdge(
                source_id=source_id,
                target_id=target_id,
                relationship=relationship,
                file_id=file_id,
                evidence=evidence,
                created_at=datetime.now(timezone.utc)
            )
            session.add(edge)
            session.commit()
        finally:
            session.close()

    def load_graph(self) -> nx.MultiDiGraph:
        session = self.SessionLocal()
        try:
            graph = nx.MultiDiGraph()

            for node in session.query(GraphNode).all():
                graph.add_node(node.node_id, display_name=node.display_name)

            for edge in session.query(GraphEdge).all():
                graph.add_edge(
                    edge.source_id,
                    edge.target_id,
                    relationship=edge.relationship,
                    evidence=edge.evidence
                )

            return graph
        finally:
            session.close()

    def find_related(self, entity_names: List[str], hops: int = 2) -> List[Dict[str, str]]:
        graph = self.load_graph()

        if graph.number_of_nodes() == 0:
            return []

        matched_nodes = set()
        for name in entity_names:
            normalized = self._normalize(name)
            for node_id in graph.nodes:
                if normalized in node_id or node_id in normalized:
                    matched_nodes.add(node_id)

        facts = []
        seen_edges = set()

        for node_id in matched_nodes:
            subgraph = nx.ego_graph(graph, node_id, radius=hops, undirected=True)

            for source, target, data in subgraph.edges(data=True):
                relationship = data.get("relationship", "related_to")
                edge_key = (source, target, relationship)

                if edge_key in seen_edges:
                    continue

                seen_edges.add(edge_key)
                facts.append({
                    "source": source,
                    "target": target,
                    "relationship": relationship,
                    "evidence": data.get("evidence") or ""
                })

        return facts
