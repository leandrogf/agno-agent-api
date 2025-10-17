# agent-api/agents/knowledge_builder_definitions.py

from agno.agent import Agent
from pydantic import BaseModel, Field
from typing import List
from agno.models.google import Gemini

# ====================================================================
# 1. MODELOS DE DADOS (PYDANTIC)
# ====================================================================

class KnowledgeRecord(BaseModel):
    """
    Modelo Pydantic que representa um registro na ybs_knowledge_base, contendo o conhecimento
    estruturado e anônimo extraído de um chamado.
    """
    ticket_id: int = Field(
        description="Código do chamado (cod_chamado) que originou este registro."
    )
    tfs_work_item_id: int | None = Field(
        default=None,
        description="ID do item de trabalho no TFS (pode ser nulo)."
    )
    title: str = Field(
        description="Título curto, descritivo e generalizado para o problema (1 frase)."
    )
    problem_summary: str = Field(
        description="Descrição anônima e clara do problema reportado pelo usuário (1-2 frases)."
    )
    root_cause_analysis: str | None = Field(
        default=None,
        description="Explicação técnica da causa real do problema identificada."
    )
    solution_applied: str | None = Field(
        default=None,
        description="Descrição clara e técnica da solução implementada."
    )
    solution_type: str | None = Field(
        default=None,
        description="Categoria da solução (ex: Script SQL, User Guidance, Configuration)."
    )
    sql_template: List[str] = Field(
        default_factory=list,
        description="Lista de scripts SQL template usados na solução, com variáveis. Mesmo quando há apenas um SQL, deve ser uma lista com um elemento."
    )
    tags: List[str] = Field(
        default_factory=list,
        min_length=1,
        description="Lista de palavras-chave relevantes para busca."
    )
    ticket_level: int | None = Field(
        default=None,
        ge=1,
        le=3,
        description="Nível de complexidade do chamado (1: Simples, 2: Médio, 3: Complexo)."
    )
    llm_model: str = Field(
        default="gemini-2.0-flash",
        description="Modelo de LLM usado para gerar este registro."
    )
    processing_version: int = Field(
        default=1,
        ge=1,
        description="Versão do algoritmo/prompt de processamento usado."
    )

class KnowledgeBatch(BaseModel):
    """
    Modelo Pydantic para um lote de registros de conhecimento.
    """
    records: List[KnowledgeRecord]

# ====================================================================
# 2. ENGENHARIA DE PROMPT
# ====================================================================

MISSION = """Sua missão é extrair conhecimento técnico estruturado de chamados de suporte.
Para cada chamado você deve:
1. Identificar o problema central
2. Extrair detalhes técnicos relevantes
3. Estruturar em formato JSON específico
4. Anonimizar todas as informações
5. Manter apenas dados técnicos reutilizáveis"""

INSTRUCTIONS_FOR_BATCH_PROCESSING = [
    "# OBJETIVO",
    f"Sua missão é: {MISSION}",

    "# FORMATO DE SAÍDA (EXEMPLO)",
    """{
  "records": [{
    "ticket_id": 123456,
    "title": "Erro de acesso ao relatório financeiro",
    "problem_summary": "O usuário não consegue visualizar o relatório financeiro mensal no módulo de gestão",
    "root_cause_analysis": "Permissão VIEW_FINANCIAL_REPORTS não estava atribuída ao papel do usuário",
    "solution_applied": "Adicionada a permissão VIEW_FINANCIAL_REPORTS ao papel do usuário via painel administrativo",
    "solution_type": "Permission Update",
    "sql_template": [],
    "tags": ["permissão", "relatório", "acesso", "papel-usuário"],
    "ticket_level": 1
  }]
}""",

    "# REGRAS DE EXTRAÇÃO",
    "1. TICKET_ID (OBRIGATÓRIO):",
    "   - Extraia o cod_chamado do dossiê e use como ticket_id",
    "   - O ticket_id estará sempre presente no texto como 'cod_chamado: [número]'",
    "   - CRÍTICO: Este número DEVE ser extraído exatamente como aparece",

    "2. TÍTULO (OBRIGATÓRIO):",
    "   - Título curto e genérico do problema (1 frase)",
    "   - Foque no tipo de problema, não nos detalhes específicos",
    "   - Ex: 'Erro de permissão ao acessar relatório'",

    "2. PROBLEMA (OBRIGATÓRIO):",
    "   - Descreva o problema em 1-2 frases",
    "   - Use linguagem clara e direta",
    "   - Mantenha o anonimato (use 'o usuário')",

    "3. CAUSA RAIZ (OPCIONAL):",
    "   - Identifique a causa técnica do problema",
    "   - Foque em explicações técnicas úteis",
    "   - Use null se não for clara",

    "4. SOLUÇÃO (OPCIONAL):",
    "   - Descreva a solução técnica implementada",
    "   - Inclua passos ou comandos relevantes",
    "   - Use null se não resolvido",

    "5. TIPO DE SOLUÇÃO (OPCIONAL):",
    "   - Categorize: Script SQL, User Guidance, Configuration,",
    "   - Database Fix, Permission Update, etc",
    "   - Use null se não aplicável",

    "6. SQL TEMPLATE (OPCIONAL):",
    "   - DEVE SER UMA LISTA VAZIA [] ou lista de SQLs",
    "   - NUNCA use null para este campo",
    "   - Substitua valores específicos por :variavel",

    "7. TAGS (LISTA):",
    "   - 3-7 palavras-chave técnicas relevantes",
    "   - Use substantivos técnicos no singular",
    "   - Inclua: componentes, tecnologias, conceitos",

    "8. NÍVEL DO CHAMADO (OPCIONAL):",
    "   - 1: Simples (configuração básica/permissão)",
    "   - 2: Médio (debug/análise necessária)",
    "   - 3: Complexo (mudança de código/banco)",

    "# REGRAS CRÍTICAS",
    "1. IDENTIFICAÇÃO:",
    "   - O ticket_id DEVE ser o cod_chamado encontrado no texto",
    "   - SEMPRE extraia e mantenha o ticket_id no registro de saída",
    "   - CRÍTICO: O ticket_id deve ser exatamente o mesmo número do cod_chamado",
    "   - Cada registro DEVE ter o ticket_id correspondente ao seu chamado",
    "   - NUNCA invente ou altere o ticket_id",

    "2. ANONIMIZAÇÃO:",
    "   - NUNCA inclua nomes de pessoas, emails ou outros identificadores",
    "   - NUNCA exponha credenciais ou senhas",
    "   - Use termos genéricos: 'o usuário', 'o sistema', etc",

    "2. QUALIDADE TÉCNICA:",
    "   - NUNCA invente informações técnicas",
    "   - SEMPRE valide a coerência técnica da solução",
    "   - SEMPRE mantenha explicações técnicas precisas",

    "3. ESTRUTURA:",
    "   - SEMPRE mantenha o formato JSON especificado",
    "   - SEMPRE use linguagem técnica profissional",
    "   - SEMPRE prefira dados estruturados a texto livre",
]

# ====================================================================
# 3. INSTANCIAÇÃO DO AGENTE
# ====================================================================
batch_analysis_agent = Agent(
    name="batch_knowledge_builder_specialist",
    role="Analista de Suporte Técnico Sênior",
    description="Especialista em processar lotes de dossiês de chamados e extrair conhecimento estruturado em formato JSON.",
    instructions=[
        "CRÍTICO - FORMATO DE RESPOSTA:",
        "- RETORNE APENAS O JSON PURO",
        "- NUNCA USE MARKDOWN ```json ou ```",
        "- A resposta deve começar DIRETAMENTE com { ",
        "- A resposta deve terminar DIRETAMENTE com }",
        "- NENHUM outro caractere antes ou depois",
        "- ERRADO: ```json { ... } ```",
        "- ERRADO: ```{ ... }```",
        "- CERTO: { ... }",
        *INSTRUCTIONS_FOR_BATCH_PROCESSING
    ],
    model=Gemini(id="gemini-2.0-flash"),
    tools=False,
    debug_mode=False,          # Habilita logs detalhados
    markdown=False,           # Desabilita formatação markdown para garantir JSON puro

)
