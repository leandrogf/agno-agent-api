# agent-api/workflows/support_workflow.py
import json
from agno.workflow import Workflow
from teams.support_team import support_team
from agents.support_triage_coordinator import triage_agent
from agents.support_n1_agent import n1_agent
from agents.support_n2_agent import n2_agent
from agents.support_n3_agent import n3_agent

# --- 1. Definição do Roteador ---
def triage_router(message: str) -> str:
    # ... (lógica de parsear JSON e retornar o nome do nó) ...
    try:
        data = json.loads(message)
        next_node = data.get("next_node")
        valid_nodes = ["N1_SupportAgent", "N2_DiagnosticAgent", "N3_ResolutionAgent", "END"]
        if next_node in valid_nodes:
            print(f"--- [Triage Router] Decisão: {next_node} ---")
            return next_node
        else:
            print(f"ALERTA: Roteador de Triagem recebeu nó inválido: '{next_node}'. Voltando para Triage.")
            return "TriageCoordinatorAgent"
    except Exception as e:
        print(f"ERRO: Erro no Roteador de Triagem ao processar '{message[:50]}...': {e}. Voltando para Triage.")
        return "TriageCoordinatorAgent"

# --- 2. Criação do Workflow ---
support_workflow = Workflow( # <-- Definido no nível do módulo
    name="support_workflow",
    description="Workflow de suporte 'hub-and-spoke' com triagem central.",
    team=support_team
)

# --- 3. Definição do Ponto de Entrada ---
support_workflow.set_entry_point(triage_agent)

# --- 4. Definição das Setas (Edges) ---
support_workflow.add_conditional_edges(
    source=triage_agent,
    condition=triage_router,
    edges={
        "N1_SupportAgent": n1_agent,
        "N2_DiagnosticAgent": n2_agent,
        "N3_ResolutionAgent": n3_agent,
        "END": "END"
    }
)
support_workflow.add_edge(n1_agent, triage_agent)
support_workflow.add_edge(n2_agent, triage_agent)
support_workflow.add_edge(n3_agent, triage_agent)
