# agent-api/toolkits/knowledge_toolkit.py

try:
    from agno.tools.toolkit import Toolkit # CORREÇÃO: Caminho correto
    from agno.tools.tool import tool       # CORREÇÃO: Caminho correto
except Exception:
    # Fallback lightweight implementations when 'agno' is not installed
    from typing import Callable
    class Toolkit:
        def __init__(self, name: str, description: str):
            self.name = name
            self.description = description
    def tool(toolkit):
        def decorator(func):
            return func
        return decorator

from typing import List, Dict, Any, Optional
from repositories.chamados_repository import ChamadosRepository
from repositories.knowledge_repository import KnowledgeRepository
from repositories.log_repository import LogRepository

# --- Instanciação Central dos Repositórios ---
chamados_repo = ChamadosRepository()
knowledge_repo = KnowledgeRepository()
log_repo = LogRepository()

# --- Definição do Toolkit ---
knowledge_toolkit = Toolkit(
    name="knowledge_toolkit"
)

# ====================================================================
# FERRAMENTAS PARA WORKERS (BUILDERS - Time de Análise)
# ====================================================================

@tool
def get_unprocessed_tickets(limit: int = 100) -> List[int]:
    """
    (PARA WORKERS) Busca um lote de códigos de chamados encerrados que ainda não foram
    processados para a base de conhecimento.
    """
    print(f"EXECUTANDO FERRAMENTA (WORKER): get_unprocessed_tickets")
    return chamados_repo.get_unprocessed_tickets(limit=limit)

@tool
def generate_dossiers_for_tickets(ticket_ids: List[int]) -> List[Dict[str, Any]]:
    """
    (PARA WORKERS) Gera os dossiês para uma lista de códigos de chamado.
    """
    print(f"EXECUTANDO FERRAMENTA (WORKER): generate_dossiers_for_tickets")
    return chamados_repo.generate_dossiers_for_tickets(ticket_ids)

# ====================================================================
# FERRAMENTAS PARA AGENTES (CONSUMERS - Time de Atendimento)
# ====================================================================

@tool
def search_knowledge_base(query: str) -> List[Dict[str, Any]]:
    """
    (PARA AGENTES) Use esta ferramenta para pesquisar soluções para problemas
    descritos pelo usuário. Forneça uma query de busca clara e concisa.
    Retorna uma lista de até 5 soluções mais relevantes encontradas.
    """
    print(f"EXECUTANDO FERRAMENTA (AGENTE): search_knowledge_base com a query: '{query}'")
    return knowledge_repo.search_full_text(search_query=query, limit=5)

@tool
def get_knowledge_by_ticket_id(ticket_id: int) -> Optional[Dict[str, Any]]:
    """
    (PARA AGENTES) Use esta ferramenta se você precisar encontrar a solução
    exata para um número de chamado específico que já foi processado.
    """
    print(f"EXECUTANDO FERRAMENTA (AGENTE): get_knowledge_by_ticket_id para o chamado: {ticket_id}")
    return knowledge_repo.get_by_ticket_id(ticket_id=ticket_id)
