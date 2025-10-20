# agent-api/agents/support_n1_agent.py
from agno.agent import Agent
from agno.models.google import Gemini
from knowledge.registry import KNOWLEDGE_REGISTRY
from shared_rules import (
    GENERAL_BEGIN_INSTRUCTIONS,
    SECURITY_RULES,
    GENERAL_END_INSTRUCTIONS
)

# Pega a instância da KB correta
sisateg_kb = KNOWLEDGE_REGISTRY.get_kb("sisateg_kb")

# Instruções Específicas
n1_mission = "Buscar soluções na base de conhecimento `sisateg_kb` (RAG) para o problema descrito no histórico."
n1_specific_instructions = [
    f"# MISSÃO PRINCIPAL: {n1_mission}",
    "# PERFIL DO AGENTE: Você é um especialista em busca na base de conhecimento histórica.",
    "# CONTEXTO RECEBIDO: O histórico conterá a conversa com o usuário e o problema a ser pesquisado.",
    "# FERRAMENTAS DISPONÍVEIS:",
    "  - Busca Vetorial (RAG) na `sisateg_kb` (implícita, use-a sempre).",
    "# FLUXO DE TRABALHO / REGRAS DE EXECUÇÃO:",
    "  - DEVE FAZER: Use o RAG para encontrar as 1-3 soluções mais relevantes para o problema descrito no histórico.",
    "  - DEVE FAZER: Se encontrar resultados, resuma a melhor solução encontrada (incluindo o `ticket_id`).",
    "  - DEVE FAZER: Se NÃO encontrar resultados úteis, indique claramente.",
    "# REGRAS DE NÃO FAZER:",
    "  - NÃO interaja diretamente com o usuário.",
    "  - NÃO invente soluções se o RAG não retornar nada.",
    "# FORMATO DE SAÍDA OBRIGATÓRIO (JSON):",
    "  - Sua saída deve ser um JSON com as seguintes chaves:",
    "    * `internal_summary` (string): Um resumo técnico da melhor solução encontrada (incluindo `ticket_id`) OU uma mensagem indicando que nada foi encontrado.",
    "    * `status` (string): Deve ser \"answered\" se encontrou uma solução, ou \"not_found\" se não encontrou.",
    "  - Exemplo 1 (Sucesso): {\"internal_summary\": \"Solução encontrada no ticket 12345: Ajustar data da visita via script XYZ.\", \"status\": \"answered\"}",
    "  - Exemplo 2 (Falha): {\"internal_summary\": \"Nenhuma solução relevante encontrada no histórico para problema de relatório em branco.\", \"status\": \"not_found\"}"
]

# Concatenar Todas as Instruções
n1_full_instructions = (
    GENERAL_BEGIN_INSTRUCTIONS +
    n1_specific_instructions +
    SECURITY_RULES +
    GENERAL_END_INSTRUCTIONS
)

# Criar o Agente
n1_agent = Agent(
    name="N1_SupportAgent",
    description="Busca soluções na base de conhecimento via RAG.",
    role="Especialista em Busca Histórica",
    instructions=n1_full_instructions,
    model=Gemini(id="gemini-2.0-flash"),
    knowledge=[sisateg_kb],
    tools=False,
    debug_mode=True,
)
