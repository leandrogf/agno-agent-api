# agent-api/toolkits/support_toolkit.py

import json
from uuid import UUID
from typing import List, Dict, Any, Optional

# --- 1. Importações Padrão do Agno ---
# (Seguindo o padrão do knowledge_toolkit.py)
try:
    from agno.tools.toolkit import Toolkit
    from agno.tools import tool
except Exception:
    # Fallback
    print("WARNING: 'agno' não instalado. Usando fallbacks.")
    from typing import Callable
    class Toolkit:
        def __init__(self, name: str, description: str):
            self.name = name
            self.description = description
    def tool(toolkit):
        def decorator(func):
            return func
        return decorator

# --- 2. Importação e Instanciação dos Repositórios ---
# (Instanciamos aqui, como no seu padrão)
from repositories.chamados_repository import ChamadosRepository
from repositories.knowledge_repository import KnowledgeRepository

chamados_repo = ChamadosRepository()
knowledge_repo = KnowledgeRepository()

# --- 3. Definição do Toolkit de Suporte ---
support_toolkit = Toolkit(
    name="support_toolkit",
    description="Conjunto de ferramentas para os agentes de suporte (N1, N2, N3) usarem para diagnosticar e resolver chamados."
)

# ===================================================================
# FERRAMENTAS PARA AGENTES (CONSUMERS - Time de Suporte)
# ===================================================================

# --- Ferramenta 1 (Para Agente N3) ---
@tool(toolkit=support_toolkit)
def get_knowledge_record_by_uuid(knowledge_id: UUID) -> str:
    """
    (PARA AGENTE N3) Use esta ferramenta quando precisar buscar os detalhes
    completos de uma SOLUÇÃO de conhecimento (incluindo o 'sql_template')
    usando o ID (UUID) único do registro (knowledge_id).
    O RAG (busca vetorial) do N1/N2 deve ter fornecido este UUID.

    Args:
        knowledge_id (UUID): O ID (UUID) único do registro de conhecimento.
    """
    print(f"--- [TOOL]: get_knowledge_record_by_uuid (ID: {knowledge_id}) ---")

    # Usa o método que criamos no KnowledgeRepository
    record = knowledge_repo.find_by_id(knowledge_id)

    if record:
        return json.dumps(record, default=str)
    else:
        return json.dumps({"error": f"Nenhum registro de conhecimento encontrado com o ID {knowledge_id}"})


# --- Ferramenta 2 (Para Agente N2) ---
@tool(toolkit=support_toolkit)
def get_ticket_dossier(ticket_id: int) -> str:
    """
    (PARA AGENTE N2) Use esta ferramenta quando precisar de todo o CONTEXTO
    e HISTÓRICO (o dossiê completo) de um chamado específico.
    Você deve fornecer o ID numérico do chamado (ticket_id).

    Args:
        ticket_id (int): O ID numérico original do chamado (ex: 76557).
    """
    print(f"--- [TOOL]: get_ticket_dossier (ID: {ticket_id}) ---")

    # Usa o método que já existia no ChamadosRepository
    dossier_list = chamados_repo.generate_dossiers_for_tickets([ticket_id])

    if dossier_list:
        return json.dumps(dossier_list[0], default=str)
    else:
        return json.dumps({"error": f"Nenhum dossiê encontrado para o chamado ID {ticket_id}"})


# --- Ferramenta 3 (Para Agente N2) ---
@tool(toolkit=support_toolkit)
def search_knowledge_by_keyword(search_terms: str) -> str:
    """
    (PARA AGENTE N2) Use esta ferramenta para fazer uma busca complementar por
    PALAVRAS-CHAVE na base de conhecimento. É útil se a busca vetorial (RAG)
    não retornar bons resultados.

    Args:
        search_terms (str): Uma string com 2 ou 3 palavras-chave. Ex: 'relatorio sincronizacao'
    """
    print(f"--- [TOOL]: search_knowledge_by_keyword (Query: '{search_terms}') ---")

    # Usa o método que criamos no KnowledgeRepository
    results = knowledge_repo.search_by_keyword(search_terms, limit=5)

    if results:
        return json.dumps(results, default=str)
    else:
        return json.dumps({"results": [], "message": f"Nenhum resultado encontrado para '{search_terms}'"})
