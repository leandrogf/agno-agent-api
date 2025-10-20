# agent-api/teams/support_team.py
from agno.team import Team

# Importa as instâncias dos agentes que definimos
from agents.support_triage_coordinator import triage_agent
from agents.support_n1_agent import n1_agent
from agents.support_n2_agent import n2_agent
from agents.support_n3_agent import n3_agent

# Cria a instância da Equipe
support_team = Team(
    name="support_team",
    description="Equipe de agentes que interage em tempo real para resolver chamados.",

    # Lista de TODOS os agentes que fazem parte desta equipe
    agents=[
        triage_agent,
        n1_agent,
        n2_agent,
        n3_agent
    ]
    # O Workflow será vinculado no próximo arquivo
)
