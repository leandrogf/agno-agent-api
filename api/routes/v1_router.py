# agent-api/api/routes/v1_router.py

from fastapi import APIRouter

# --- 1. Importações dos Roteadores Originais (Mantidas) ---
# from api.routes.agents import agents_router  # Para os endpoints /agents/...
from api.routes.health import health_router  # Para o endpoint /health
# from api.routes.playground import playground_router # Para a UI do Agno

# --- 2. ADICIONAR Importação do Nosso Roteador de Suporte ---
from api.routes.support import support_router # Para os endpoints /support/...

# --- 3. Criação do Roteador Principal v1 ---
v1_router = APIRouter(prefix="/v1")

# --- 4. Inclusão de TODOS os Roteadores ---
# Inclui os roteadores originais
v1_router.include_router(health_router)
# v1_router.include_router(agents_router)
# v1_router.include_router(playground_router)

# ADICIONA o nosso roteador de suporte
v1_router.include_router(support_router)

print("--- v1 Router Configurado com: health, agents, playground, support ---")
