"""
Neo4j Client

Manages connections to Neo4j database. 
"""

import os
from typing import Any, Optional
from contextlib import contextmanager
from neo4j import GraphDatabase, Driver, Session, Result
from dotenv import load_dotenv

load_dotenv()


class Neo4jClient:
    """
    Neo4j database client for the knowledge graph.
    
    Example:
        >>> client = Neo4jClient()
        >>> client. connect()
        >>> result = client.execute_query("MATCH (n) RETURN count(n) as count")
        >>> print(result[0]["count"])
        >>> client.close()
    
    Or using context manager:
        >>> with Neo4jClient() as client:
        ...     result = client.execute_query("MATCH (n) RETURN n LIMIT 5")
    """
    
    def __init__(
        self,
        uri: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        database: Optional[str] = None,
    ):
        """
        Initialize Neo4j client.
        
        Args:
            uri: Neo4j connection URI (default: from NEO4J_URI env var)
            user: Neo4j username (default: from NEO4J_USER env var)
            password: Neo4j password (default: from NEO4J_PASSWORD env var)
            database: Neo4j database name (default: from NEO4J_DATABASE env var)
        """
        self.uri = uri or os. getenv("NEO4J_URI", "bolt://localhost:7687")
        self.user = user or os.getenv("NEO4J_USER", "neo4j")
        self.password = password or os. getenv("NEO4J_PASSWORD", "password")
        self.database = database or os.getenv("NEO4J_DATABASE", "neo4j")
        self._driver: Optional[Driver] = None
    
    def connect(self) -> "Neo4jClient":
        """Establish connection to Neo4j."""
        if self._driver is None:
            self._driver = GraphDatabase. driver(
                self.uri,
                auth=(self.user, self. password),
            )
        return self
    
    def close(self) -> None:
        """Close the Neo4j connection."""
        if self._driver:
            self._driver.close()
            self._driver = None
    
    def __enter__(self) -> "Neo4jClient":
        """Context manager entry."""
        return self.connect()
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.close()
    
    @property
    def driver(self) -> Driver:
        """Get the Neo4j driver, connecting if necessary."""
        if self._driver is None:
            self. connect()
        return self._driver
    
    @contextmanager
    def session(self) -> Session:
        """Get a Neo4j session as a context manager."""
        session = self.driver. session(database=self.database)
        try:
            yield session
        finally:
            session.close()
    
    def execute_query(
        self,
        query: str,
        parameters: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        """
        Execute a Cypher query and return results.
        
        Args:
            query: Cypher query string
            parameters: Query parameters
        
        Returns:
            List of result records as dictionaries
        """
        with self. session() as session:
            result = session.run(query, parameters or {})
            return [record.data() for record in result]
    
    def execute_write(
        self,
        query: str,
        parameters: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        """
        Execute a write transaction. 
        
        Args:
            query: Cypher query string
            parameters: Query parameters
        
        Returns:
            List of result records as dictionaries
        """
        def _write_tx(tx, query: str, parameters: dict):
            result = tx.run(query, parameters)
            return [record.data() for record in result]
        
        with self. session() as session:
            return session.execute_write(_write_tx, query, parameters or {})
    
    def execute_read(
        self,
        query: str,
        parameters: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        """
        Execute a read transaction. 
        
        Args:
            query: Cypher query string
            parameters: Query parameters
        
        Returns:
            List of result records as dictionaries
        """
        def _read_tx(tx, query: str, parameters: dict):
            result = tx.run(query, parameters)
            return [record.data() for record in result]
        
        with self.session() as session:
            return session.execute_read(_read_tx, query, parameters or {})
    
    def verify_connectivity(self) -> bool:
        """Verify connection to Neo4j is working."""
        try:
            self.driver.verify_connectivity()
            return True
        except Exception:
            return False
    
    def clear_database(self) -> None:
        """Clear all nodes and relationships from the database."""
        self.execute_write("MATCH (n) DETACH DELETE n")
    
    def get_node_count(self) -> int:
        """Get total number of nodes in the database."""
        result = self.execute_read("MATCH (n) RETURN count(n) as count")
        return result[0]["count"] if result else 0
    
    def get_relationship_count(self) -> int:
        """Get total number of relationships in the database."""
        result = self.execute_read("MATCH ()-[r]->() RETURN count(r) as count")
        return result[0]["count"] if result else 0
    
    def create_indexes(self) -> None:
        """Create indexes for better query performance."""
        indexes = [
            "CREATE INDEX node_id IF NOT EXISTS FOR (n:NetworkNode) ON (n.id)",
            "CREATE INDEX node_type IF NOT EXISTS FOR (n:NetworkNode) ON (n.type)",
            "CREATE INDEX node_status IF NOT EXISTS FOR (n:NetworkNode) ON (n. status)",
            "CREATE INDEX policy_id IF NOT EXISTS FOR (p:Policy) ON (p. id)",
            "CREATE INDEX policy_type IF NOT EXISTS FOR (p:Policy) ON (p.policy_type)",
            "CREATE INDEX policy_status IF NOT EXISTS FOR (p:Policy) ON (p.status)",
            "CREATE INDEX compliance_id IF NOT EXISTS FOR (c:ComplianceRule) ON (c.id)",
        ]
        for index_query in indexes:
            try:
                self. execute_write(index_query)
            except Exception:
                pass  # Index might already exist
    
    def get_database_stats(self) -> dict[str, Any]:
        """Get database statistics."""
        return {
            "node_count": self. get_node_count(),
            "relationship_count": self. get_relationship_count(),
            "connected": self.verify_connectivity(),
            "database": self.database,
        }