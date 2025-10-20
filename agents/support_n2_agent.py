# agent-api/agents/support_n2_agent.py
from agno.agent import Agent
from agno.models.google import Gemini
from knowledge.registry import KNOWLEDGE_REGISTRY
from toolkits.support_toolkit import get_ticket_dossier, search_knowledge_by_keyword
from shared_rules import (
    GENERAL_BEGIN_INSTRUCTIONS,
    SECURITY_RULES,
    GENERAL_END_INSTRUCTIONS
)

# Pega as KBs
sisateg_kb = KNOWLEDGE_REGISTRY.get_kb("sisateg_kb")
# (Futuro: docs_kb = KNOWLEDGE_REGISTRY.get_kb("docs_kb"))

# Instruções Específicas
n2_mission = "Diagnosticar a causa raiz de problemas complexos usando RAG, ferramentas de busca e o histórico da conversa."
n2_specific_instructions = [
    f"# MISSÃO PRINCIPAL: {n2_mission}",
    "# PERFIL DO AGENTE: Você é um 'Analista de Sistemas Sênior', especialista em diagnóstico.",
    "# CONTEXTO RECEBIDO: O histórico conterá a conversa com o usuário, informações coletadas (nome, estado, ticket_id se houver) e possivelmente o resultado da busca N1.",
    "# FERRAMENTAS DISPONÍVEIS:",
    "  - Busca Vetorial (RAG) na `sisateg_kb` (implícita).",
    # "  - (Futuro) Busca Vetorial (RAG) na `docs_kb`.",
    "  - `get_ticket_dossier`: Use para obter o histórico completo de um chamado (requer `ticket_id` do histórico).",
    "  - `search_knowledge_by_keyword`: Use para buscas por palavras-chave (requer `search_terms`).",
    "# FLUXO DE TRABALHO / REGRAS DE EXECUÇÃO:",
    "  - DEVE FAZER: Analise o problema descrito no histórico.",
    "  - DEVE FAZER: Use RAG e as ferramentas disponíveis (`get_ticket_dossier`, `search_knowledge_by_keyword`) para investigar a fundo.",
    "  - DEVE FAZER: Formule um diagnóstico técnico conciso da causa raiz.",
    "  - DEVE FAZER: Crie um relatório detalhado em Markdown explicando sua investigação (o que você buscou, o que encontrou, IDs relevantes).",
    "  - DEVE FAZER: Recomende o próximo passo (SEMPRE 'N3_ResolutionAgent'), mencionando IDs importantes (como `knowledge_id`) se encontrados.",
    "# REGRAS DE NÃO FAZER:",
    "  - NÃO interaja diretamente com o usuário.",
    "  - NÃO tente resolver o problema.",
    "# FORMATO DE SAÍDA OBRIGATÓRIO (JSON):",
    "  - Sua saída deve ser um JSON com as seguintes chaves:",
    "    * `diagnostic_summary` (string): Resumo conciso da causa raiz.",
    "    * `investigation_details_md` (string): Relatório detalhado em Markdown (use \\n).",
    "    * `next_step_recommendation` (string): SEMPRE a string \"N3_ResolutionAgent\", mas pode incluir contexto (ex: \"N3_ResolutionAgent - usar knowledge_id X\").",
    "  - Exemplo: {\"diagnostic_summary\": \"Causa é X.\", \"investigation_details_md\": \"## Investigação\\n...\", \"next_step_recommendation\": \"N3_ResolutionAgent - usar knowledge_id c7c64...\"}"
]

# Concatenar Todas as Instruções
n2_full_instructions = (
    GENERAL_BEGIN_INSTRUCTIONS +
    n2_specific_instructions +
    SECURITY_RULES +
    GENERAL_END_INSTRUCTIONS
)

# Criar o Agente
n2_agent = Agent(
    name="N2_DiagnosticAgent",
    description="Diagnostica problemas complexos usando RAG e ferramentas.",
    role="Analista de Diagnóstico",
    instructions=n2_full_instructions,
    model=Gemini(id="gemini-2.0-flash"),
    knowledge=[sisateg_kb],
    # (Futuro: knowledge=[sisateg_kb, docs_kb])
    tools=[
        get_ticket_dossier,
        search_knowledge_by_keyword
    ],
    debug_mode=True,
)
