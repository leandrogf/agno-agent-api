from agno.playground import Playground
from typing import List, Union, Dict

# --- 1. Importações dos Agentes de Exemplo (Mantidas) ---
# (Assumindo que os arquivos ainda existem e funcionam)
try:
    from agents.agno_assist import get_agno_assist
    from agents.finance_agent import get_finance_agent
    # Removi web_agent pois não estava no seu tree.txt, mas adicione se necessário
    # from agents.web_agent import get_web_agent
    example_agents_available = True
except ImportError:
    print("Playground: AVISO - Não foi possível importar os agentes de exemplo (agno_assist, finance_agent).")
    example_agents_available = False

# --- 2. Importação do NOSSO Registro de Agentes/Equipe ---
from core.agent_registry import AGENT_REGISTRY
from agno.agent import Agent
from agno.team import Team

######################################################
## Routes for the Playground Interface (Agno UI)
######################################################

# --- 3. Carregar TODOS os Serviços ---

# Lista para guardar todas as instâncias (Exemplos + Nossos)
all_services_for_playground: List[Union[Agent, Team]] = []
loaded_service_names: List[str] = [] # Para evitar duplicatas

# Carrega os Agentes de Exemplo (se disponíveis)
if example_agents_available:
    try:
        # Instancia os agentes de exemplo com debug_mode=True
        agno_assist = get_agno_assist(debug_mode=True)
        finance_agent = get_finance_agent(debug_mode=True)
        # web_agent = get_web_agent(debug_mode=True) # Adicione se existir

        all_services_for_playground.extend([agno_assist, finance_agent]) # Adicione web_agent se existir
        loaded_service_names.extend([agno_assist.name, finance_agent.name]) # Adicione web_agent.name se existir
        print(f"Playground: Agentes de exemplo carregados: {[a.name for a in [agno_assist, finance_agent]]}") # Ajuste a lista
    except Exception as e:
        print(f"Playground: ERRO ao carregar agentes de exemplo: {e}")

# Carrega NOSSOS Agentes e Equipe do Registry
our_service_names: List[str] = AGENT_REGISTRY.get_available_services()
for service_name in our_service_names:
    if service_name not in loaded_service_names: # Evita adicionar duplicatas se houver sobreposição
        service_instance = AGENT_REGISTRY.get_service(service_name)
        if service_instance:
            # Assumimos que debug_mode já foi definido na criação da instância
            all_services_for_playground.append(service_instance)
            loaded_service_names.append(service_name)
            print(f"Playground: Adicionando nosso serviço '{service_name}'")
        else:
            print(f"Playground: AVISO - Nosso serviço '{service_name}' não encontrado no registry.")

if not all_services_for_playground:
    print("Playground: ERRO - Nenhum agente ou equipe encontrado para servir no playground!")
    # Criar um playground vazio pode causar erros na UI, melhor parar ou ter um fallback
    raise RuntimeError("Nenhum serviço (Agente/Equipe) pôde ser carregado para o Playground.")

# --- 4. Criar a Instância do Playground ---
# Passa a lista COMBINADA de instâncias para o Playground
playground = Playground(agents=all_services_for_playground)

# --- 5. Obter o Roteador FastAPI ---
# O Playground gera automaticamente os endpoints necessários (/playground/*)
playground_router = playground.get_async_router()

print(f"--- Playground Router Configurado com {len(all_services_for_playground)} serviços: {loaded_service_names} ---")
