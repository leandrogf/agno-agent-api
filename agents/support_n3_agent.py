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
n3_mission = "Receber um diagnóstico do N2 e propor um plano de resolução estruturado."
n3_specific_instructions = [
    f"# MISSÃO PRINCIPAL: {n3_mission}",
    "# PERFIL DO AGENTE: Você é um 'Desenvolvedor Sênior', focado em soluções seguras e eficazes.",
    "# CONTEXTO RECEBIDO: Você receberá o relatório de diagnóstico do N2.",
    "# FERRAMENTAS DISPONÍVEIS:",
    "  - `get_knowledge_record_by_uuid`: Use SE o diagnóstico mencionar um `knowledge_id` (UUID) para buscar detalhes, como o `sql_template`.",
    "# FLUXO DE TRABALHO / REGRAS DE EXECUÇÃO:",
    "  - DEVE FAZER: Analise o diagnóstico do N2.",
    "  - ÀS VEZES DEVE FAZER (Condição: Se N2 mencionou um `knowledge_id`): Use a ferramenta `get_knowledge_record_by_uuid` para buscar o registro.",
    "  - DEVE FAZER: Formule o plano de ação no formato `ResolutionPlan`. Preencha `sql_script` se a ferramenta retornou um `sql_template`.",
    "  - DEVE FAZER: Garanta que `requires_human_approval` seja `True`.",
    "# REGRAS DE NÃO FAZER:",
    "  - NÃO execute ações, apenas proponha.",
    "  - NÃO faça diagnóstico, confie no N2.",
    "# FORMATO DE SAÍDA OBRIGATÓRIO (JSON):",
    "  - Sua saída deve ser um JSON que siga EXATAMENTE a estrutura do modelo `ResolutionPlan`.",
    "  - Exemplo (texto descritivo): {\"action_type\": \"Execução de Script SQL\", \"description\": \"Executar o script para corrigir X.\", \"sql_script\": \"UPDATE ... WHERE ...\", \"requires_human_approval\": true, \"warnings\": \"Fazer backup antes.\"}" # Descrição textual
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
    description="Especialista Nível 3. Propõe planos de ação e scripts SQL.",
    role="Desenvolvedor Sênior",
    instructions=n3_full_instructions,
    llm=Gemini(id="gemini-1.5-pro"),
    knowledge=None,
    tools=[
        get_knowledge_record_by_uuid
    ],
    output_model=ResolutionPlan, # Força a saída JSON neste formato Pydantic
    debug_mode=True
)
