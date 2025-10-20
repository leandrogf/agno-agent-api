# agent-api/agents/support_n3_agent.py
from agno.agent import Agent
from agno.models.google import Gemini
from pydantic import BaseModel, Field
from typing import Optional
from toolkits.support_toolkit import get_knowledge_record_by_uuid
from shared_rules import (
    GENERAL_BEGIN_INSTRUCTIONS,
    SECURITY_RULES,
    GENERAL_END_INSTRUCTIONS
)

# Modelo Pydantic para a SAÍDA (Obriga o JSON neste formato)
class ResolutionPlan(BaseModel):
    """Estrutura para o plano de resolução proposto pelo N3."""
    action_type: str = Field(..., description="Tipo de ação proposta (ex: 'Execução de Script SQL', 'Ajuste Manual via Sistema', 'Orientação Detalhada')")
    description: str = Field(..., description="Descrição clara e detalhada do plano de ação passo a passo.")
    sql_script: Optional[str] = Field(None, description="Se action_type for 'Execução de Script SQL', o script SQL completo e parametrizado.")
    requires_human_approval: bool = Field(True, description="Confirmação de que a execução requer aprovação humana (sempre True).")
    warnings: Optional[str] = Field(None, description="Alertas sobre potenciais riscos ou efeitos colaterais da ação.")

# Instruções Específicas
n3_mission = "Formular um plano de resolução técnico (ResolutionPlan JSON) baseado no diagnóstico do N2."
n3_specific_instructions = [
    f"# MISSÃO PRINCIPAL: {n3_mission}",
    "# PERFIL DO AGENTE: Você é um 'Engenheiro de Soluções', focado em criar planos de ação.",
    "# CONTEXTO RECEBIDO: O histórico conterá o diagnóstico do N2.",
    "# FERRAMENTAS DISPONÍVEIS:",
    "  - `get_knowledge_record_by_uuid`: Use SE o N2 recomendou buscar um `knowledge_id` (UUID).",
    "# FLUXO DE TRABALHO / REGRAS DE EXECUÇÃO:",
    "  - DEVE FAZER: Analise o `diagnostic_summary` e `investigation_details_md` do N2.",
    "  - ÀS VEZES DEVE FAZER (Condição: Se N2 mencionou `knowledge_id`): Use `get_knowledge_record_by_uuid` para buscar o `sql_template`.",
    "  - DEVE FAZER: Crie o plano de ação no formato `ResolutionPlan`. Preencha `sql_script` se aplicável.",
    "  - DEVE FAZER: Garanta `requires_human_approval` = `True`.",
    "# REGRAS DE NÃO FAZER:",
    "  - NÃO interaja diretamente com o usuário.",
    "  - NÃO execute ações, apenas crie o plano.",
    "  - NÃO faça diagnóstico.",
    "# FORMATO DE SAÍDA OBRIGATÓRIO (JSON):",
    "  - Sua saída deve ser um JSON que siga EXATAMENTE a estrutura do modelo `ResolutionPlan`.",
    "  - Exemplo: {\"action_type\": \"Execução de Script SQL\", ..., \"requires_human_approval\": true, ...}"
]

# Concatenar Todas as Instruções
n3_full_instructions = (
    GENERAL_BEGIN_INSTRUCTIONS +
    n3_specific_instructions +
    SECURITY_RULES +
    GENERAL_END_INSTRUCTIONS
)

# Criar o Agente
n3_agent = Agent(
    name="N3_ResolutionAgent",
    description="Formula planos de resolução técnicos.",
    role="Engenheiro de Soluções",
    instructions=n3_full_instructions,
    model=Gemini(id="gemini-2.0-flash"),
    knowledge=None,
    tools=[
        get_knowledge_record_by_uuid
    ],
    # output_model=ResolutionPlan, # Temporariamente removido para teste
    debug_mode=True
)
