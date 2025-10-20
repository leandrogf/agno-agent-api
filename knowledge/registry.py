# agent-api/knowledge/registry.py

import os
from agno.knowledge.knowledge import Knowledge
from agno.vectordb.lancedb import LanceDb
from agno.knowledge.embedder.google import GeminiEmbedder
from typing import Dict, Any

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VECTOR_DB_PATH = os.path.join(BASE_DIR, "lancedb_data")

class KnowledgeRegistry:
    """
    Registry central para gerenciar instâncias de Bases de Conhecimento (KB) do Agno.
    Utiliza inicialização preguiçosa (lazy loading) para criar as instâncias
    apenas quando são solicitadas pela primeira vez.
    Segue o padrão do ToolRegistry.
    """

    _kbsDefinitions: Dict[str, Any] = {
        "sisateg_kb": {
            "VectorDbPath": VECTOR_DB_PATH,
            "VectorTableName": "sisateg_knowledge_base",
            "EmbedderModelId": "models/embedding-001"
        },
        "docs_kb": {
            "VectorDbPath": VECTOR_DB_PATH,
            "VectorTableName": "system_documentation", # Nome da futura tabela
            "EmbedderModelId": "models/embedding-001"
        }
    }

    _kbs: Dict[str, Knowledge] = {} # Cache para armazenar as instâncias de KB

    def __init__(self):
        """Inicializa o Registry (vazio inicialmente)."""
        print("--- KnowledgeRegistry Inicializado ---")

        for kb_name in self._kbsDefinitions.keys():
            print(f"KB registrada: {kb_name}")
            if kb_name not in self._kbs:
                self._kbs[kb_name] = self._create_kb(self._kbsDefinitions[kb_name])

    def _create_kb(self, definitions) -> Knowledge:
        """
        Lógica interna para criar a instância da KB 'sisateg_kb'.
        Lê as configurações do ambiente e do vector_knowledge_builder.
        """

        embedder = GeminiEmbedder(id=definitions["EmbedderModelId"])
        vector_db = LanceDb(
            uri=definitions["VectorDbPath"],
            table_name=definitions["VectorTableName"],
            embedder=embedder
        )
        kb = Knowledge(vector_db=vector_db)
        return kb

    def get_kb(self, name: str) -> Knowledge:
        """
        Obtém uma instância de base de conhecimento pelo nome, criando-a se
        ainda não existir (inicialização preguiçosa).

        Args:
            name (str): O nome da KB registrada (ex: "sisateg_kb", "docs_kb").

        Returns:
            Knowledge: A instância da base de conhecimento.

        Raises:
            ValueError: Se o nome da KB não for reconhecido.
        """
        if name not in self._kbs:
            return None
        return self._kbs[name]

    def all_kbs(self) -> Dict[str, Knowledge]:
        """
        Retorna um dicionário com todas as KBs já instanciadas.
        Nota: KBs não solicitadas via get_kb() não estarão aqui.

        Returns:
            Dict[str, Knowledge]: Dicionário com nome_kb -> instancia_kb.
        """
        return self._kbs.copy() # Retorna uma cópia para evitar modificação externa

# --- Instância Singleton (como no seu registry.py) ---
# Outros módulos importarão esta instância para acessar as KBs.
KNOWLEDGE_REGISTRY = KnowledgeRegistry()
