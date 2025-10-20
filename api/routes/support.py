# agent-api/api/routes/support.py

import json
from fastapi import APIRouter, HTTPException, status, Body
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import AsyncGenerator, List, Optional, Union, Dict, Any

# Importações do Agno
from agno.agent import Agent
from agno.team import Team
from agno.schema import AgentRun # Para tipagem da resposta não-stream

# Importa nosso registro central de agentes e equipes
from core.agent_registry import AGENT_REGISTRY

# Cria o roteador específico para o suporte
support_router = APIRouter(prefix="/support", tags=["Support Services"])

# --- Modelos Pydantic para Request/Response ---

class ChatRequest(BaseModel):
    """Modelo para o corpo da requisição de chat."""
    message: str = Field(..., description="A mensagem ou pergunta do usuário.")
    stream: bool = Field(True, description="Indica se a resposta deve ser em stream (SSE).")
    session_id: Optional[str] = Field(None, description="ID opcional para rastrear a sessão de chat.")
    user_id: Optional[str] = Field(None, description="ID opcional para identificar o usuário.")
    # Adicione outros campos de configuração se necessário (ex: metadata)
    config: Optional[Dict[str, Any]] = Field(None, description="Configurações adicionais para a execução.")

# --- Endpoints da API ---

@support_router.get("/services", response_model=List[str])
async def list_support_services():
    """
    Retorna uma lista com os nomes de todos os serviços de suporte disponíveis
    (equipes e agentes individuais).
    """
    return AGENT_REGISTRY.get_available_services()


async def chat_response_streamer(
    service: Union[Agent, Team],
    message: str,
    config: Optional[Dict[str, Any]] = None
) -> AsyncGenerator[str, None]:
    """
    Função geradora assíncrona para processar e retornar a resposta em stream (SSE).
    Itera sobre os eventos retornados por `service.astream` ou `service.arun(stream=True)`.
    """
    final_output = None
    stream_config = config or {} # Garante que config não seja None

    try:
        # Usamos arun com stream=True, que retorna um AsyncIterator[AgentRun]
        # (Presumindo que Team também suporte isso, como Agent faz)
        async for agent_run in service.arun(message, stream=True, config=stream_config):
            # Processa diferentes tipos de eventos se necessário (opcional)
            # Ex: log de início/fim de agente, chamada de ferramenta, etc.
            # print(f"STREAM EVENT: {agent_run.event_type} - {agent_run.agent_name}")

            # O evento final 'AgentRunCompleted' geralmente contém a saída completa
            if agent_run.is_last:
                final_output = agent_run.run_output

                # Se a saída for um objeto Pydantic (como ResolutionPlan), serializa
                if isinstance(final_output, BaseModel):
                    output_data = final_output.model_dump_json()
                # Se for um dicionário (ex: saída JSON do N1 ou N2)
                elif isinstance(final_output, dict):
                     output_data = json.dumps(final_output, ensure_ascii=False)
                # Se for texto simples (menos provável com nossa estrutura JSON)
                else:
                    output_data = str(final_output)

                # Formato Server-Sent Events (SSE)
                yield f"data: {output_data}\n\n"

    except Exception as e:
        print(f"Erro durante o stream: {e}")
        # Retorna um evento de erro no stream
        error_data = json.dumps({"error": "Ocorreu um erro durante o processamento.", "details": str(e)})
        yield f"data: {error_data}\n\n"
        # Você pode querer logar o erro completo aqui
        import traceback
        traceback.print_exc()

@support_router.post("/chat/{service_id}")
async def chat_with_service(service_id: str, body: ChatRequest):
    """
    Envia uma mensagem para um serviço de suporte (equipe ou agente) e
    retorna a resposta, em stream ou como um objeto único.
    """
    # Obtém a instância do serviço (Agente ou Equipe) pelo nome
    service = AGENT_REGISTRY.get_service(service_id)

    if service is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Serviço '{service_id}' não encontrado."
        )

    # Prepara a configuração, incluindo session_id e user_id se fornecidos
    # O Agno/Langchain usa a chave 'configurable' para isso
    config = body.config or {}
    configurable_config = config.get("configurable", {})
    if body.session_id:
        configurable_config["session_id"] = body.session_id
    if body.user_id:
        # Adicione lógica para mapear user_id se necessário, ou passe direto
        configurable_config["user_id"] = body.user_id
    config["configurable"] = configurable_config

    if body.stream:
        # Retorna a resposta em stream usando Server-Sent Events (SSE)
        return StreamingResponse(
            chat_response_streamer(service, body.message, config),
            media_type="text/event-stream"
        )
    else:
        # Executa de forma síncrona (espera o resultado final)
        try:
            # Usamos arun com stream=False, que retorna o AgentRun final
            agent_run: AgentRun = await service.arun(body.message, stream=False, config=config)
            final_output = agent_run.run_output

            # Se a saída for um objeto Pydantic (como ResolutionPlan), retorna como dict
            if isinstance(final_output, BaseModel):
                return final_output.model_dump()
            # Se for dicionário ou string (já JSON), retorna diretamente
            elif isinstance(final_output, (dict, str)):
                 return final_output
            else:
                 return {"response": str(final_output)} # Fallback

        except Exception as e:
            print(f"Erro durante a execução não-stream: {e}")
            import traceback
            traceback.print_exc()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Ocorreu um erro durante o processamento: {str(e)}"
            )
