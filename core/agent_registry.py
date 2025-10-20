# agent-api/core/agent_registry.py

from typing import Dict, List, Any, Union
from agno.agent import Agent
from agno.team import Team

# --- 1. Importar as INSTÂNCIAS que já definimos ---
# Importa os agentes individuais
from agents.support_triage_coordinator import triage_agent
from agents.support_n1_agent import n1_agent
from agents.support_n2_agent import n2_agent
from agents.support_n3_agent import n3_agent

# Importa a equipe completa (que contém os agentes e o workflow)
from teams.support_team import support_team

class AgentRegistry:
    """
    Registry central para gerenciar instâncias de Agentes e Equipes (Teams) do Agno.
    Permite buscar e listar todos os 'serviços' (agentes ou equipes) disponíveis na API.
    Segue o padrão do ToolRegistry.
    """

    _registry: Dict[str, Union[Agent, Team]] = {} # Cache para armazenar as instâncias

    def __init__(self):
        """
        Inicializa o Registry e carrega as instâncias definidas.
        """
        print("--- AgentRegistry Inicializado ---")
        self._load_services()

    def _load_services(self):
        """
        Carrega as instâncias de Agentes e Equipes no registro.
        Adicione novas instâncias aqui conforme necessário.
        """
        # Adiciona a Equipe principal (que executa o workflow completo)
        self._registry[support_team.name] = support_team # Ex: "support_team" -> <Team object>

        # Adiciona os Agentes individuais (úteis para teste direto ou playground)
        self._registry[triage_agent.name] = triage_agent # Ex: "TriageCoordinatorAgent" -> <Agent object>
        self._registry[n1_agent.name] = n1_agent
        self._registry[n2_agent.name] = n2_agent
        self._registry[n3_agent.name] = n3_agent

        print(f"AgentRegistry: {len(self._registry)} serviços carregados: {list(self._registry.keys())}")

    def get_service(self, name: str) -> Union[Agent, Team, None]:
        """
        Obtém uma instância de Agente ou Equipe pelo nome registrado.

        Args:
            name (str): O nome do serviço (ex: "support_team", "N1_SupportAgent").

        Returns:
            Union[Agent, Team, None]: A instância correspondente ou None se não encontrada.
        """
        return self._registry.get(name)

    def get_available_services(self) -> List[str]:
        """
        Retorna uma lista com os nomes de todos os serviços (Agentes e Equipes) registrados.

        Returns:
            List[str]: Lista de nomes dos serviços.
        """
        return list(self._registry.keys())

# --- Instância Singleton (como no ToolRegistry) ---
# Outros módulos (como as rotas da API) importarão esta instância.
AGENT_REGISTRY = AgentRegistry()
