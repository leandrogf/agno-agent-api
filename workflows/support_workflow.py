# agent-api/workflows/support_workflow.py
import json
from agno.workflow import Workflow
from teams.support_team import support_team
from agents.support_triage_coordinator import triage_agent
from agents.support_n1_agent import n1_agent
from agents.support_n2_agent import n2_agent
from agents.support_n3_agent import n3_agent

# --- 1. Definição do Roteador Inteligente (Smart Router) ---

def smart_router(message: str, history: list) -> str:
    """
    Este roteador é o cérebro do workflow.
    Ele inspeciona a SAÍDA (message) do nó anterior e decide para onde ir.
    A lógica de roteamento foi movida dos prompts dos agentes para este código Python.
    """

    # Tenta carregar a saída JSON do agente anterior
    try:
        # Adiciona log para depuração
        print(f"--- [Smart Router] Analisando mensagem: {message[:150]}...")
        data = json.loads(message)

        # --- Rota 1: Saída vinda do N1_SupportAgent ---
        # O N1 decide se a busca foi suficiente ou se precisa escalar.
        if "status" in data:
            if data["status"] == "answered":
                # Solução encontrada, devolve para o Triage entregar ao usuário
                print("--- [Smart Router] Decisão: N1 -> Triage (Solução encontrada) ---")
                return "TriageCoordinatorAgent"

            elif data["status"] == "not_found":
                # Solução não encontrada, escala para o N2
                print("--- [Smart Router] Decisão: N1 -> N2 (Não encontrado, escalar) ---")
                return "N2_DiagnosticAgent"

        # --- Rota 2: Saída vinda do TriageCoordinatorAgent (Início do fluxo) ---
        # Se o Triage acabou de coletar as informações, ele envia "gathered_info".
        # Este é o gatilho para iniciar a busca N1.
        elif "gathered_info" in data:
            print("--- [Smart Router] Decisão: Triage -> N1 (Info coletada) ---")
            return "N1_SupportAgent"

        # --- Rota 3: Saída vinda do TriageCoordinatorAgent (Conversa ou Fim) ---
        # Se o Triage apenas enviou uma mensagem (ex: "Olá", ou "A solução é...")
        # significa que o fluxo atual parou e está aguardando a próxima entrada do usuário.
        elif "user_message" in data:
            print("--- [Smart Router] Decisão: Triage -> END (Esperando usuário) ---")
            return "END"

        # --- Fallback (JSON inesperado) ---
        else:
            # Se o JSON for válido, mas não tiver as chaves esperadas.
            print(f"ALERTA: Smart Router não reconheceu a estrutura: {data}. Voltando para Triage.")
            return "TriageCoordinatorAgent"

    except Exception as e:
        # Se o JSON for inválido (ex: uma mensagem de erro ou texto puro)
        # Retorna para o Triage para que ele possa lidar com o erro
        # (ex: "Desculpe, não entendi, pode repetir?")
        print(f"ERRO: Smart Router falhou ao parsear JSON: {e}. Mensagem: {message[:100]}. Voltando para Triage.")
        return "TriageCoordinatorAgent"

# --- 2. Criação do Workflow ---
support_workflow = Workflow(
    name="support_workflow",
    description="Workflow de suporte 'hub-and-spoke' com lógica de roteamento em Python.",
    team=support_team
)

# --- 3. Definição do Ponto de Entrada ---
# O usuário SEMPRE fala com o TriageCoordinatorAgent primeiro.
support_workflow.set_entry_point(triage_agent)

# --- 4. Definição das Setas (Edges) ---

# O TriageAgent (entry point) usa o roteador para decidir se:
# a) Inicia o fluxo N1 (se "gathered_info" estiver presente)
# b) Termina o fluxo (se "user_message" estiver presente, aguardando usuário)
support_workflow.add_conditional_edges(
    source=triage_agent,
    condition=smart_router,
    edges={
        "N1_SupportAgent": n1_agent,
        "END": "END"
    }
)

# O N1_SupportAgent usa o roteador para decidir se:
# a) A solução foi encontrada (volta para Triage)
# b) A solução não foi encontrada (escala para N2)
support_workflow.add_conditional_edges(
    source=n1_agent,
    condition=smart_router,
    edges={
        "TriageCoordinatorAgent": triage_agent,
        "N2_DiagnosticAgent": n2_agent
    }
)

# Os passos N2 e N3 são fixos (não precisam de roteador condicional):
# O N2 (Diagnóstico) SEMPRE envia seu resultado para o N3 (Resolução).
support_workflow.add_edge(n2_agent, n3_agent)

# O N3 (Resolução) SEMPRE envia seu plano de volta para o Triage (para formatar ao usuário).
support_workflow.add_edge(n3_agent, triage_agent)
