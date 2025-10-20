# agent-api/teams/support_team.py
from agno.team import Team
from agno.models.google import Gemini

# Importa as instâncias dos agentes que definimos
from agents.support_triage_coordinator import triage_agent
from agents.support_n1_agent import n1_agent
from agents.support_n2_agent import n2_agent
from agents.support_n3_agent import n3_agent

# Cria a instância da Equipe
support_team = Team(
    name="support_team",
    members=[
        triage_agent,
        n1_agent,
        n2_agent,
        n3_agent
    ],
    model=Gemini(id="gemini-2.0-flash"),
    instructions="Equipe de agentes que trabalha em conjunto para resolver chamados de suporte técnico através de um workflow hub-and-spoke coordenado pelo agente de triagem."
)
