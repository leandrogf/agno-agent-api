# agent-api/builders/vector_knowledge_builder.py
from dotenv import load_dotenv
import time
import asyncio
import os
import traceback
from uuid import UUID
from contextlib import contextmanager
from typing import List, Dict, Any, Tuple

# Importa as classes Agno para Knowledge Base e Embeddings
from agno.knowledge.knowledge import Knowledge
from agno.vectordb.lancedb import LanceDb, SearchType
from agno.knowledge.embedder.google import GeminiEmbedder # Usando Gemini Embedder

# Importa os repositórios
from repositories.knowledge_repository import KnowledgeRepository
from repositories.log_repository import LogRepository, JOB_TYPE_VECTORIZATION # Reutilizando o LogRepository

# Importa o gerenciador de arquivos temporários
from tempfiles import TempFileManager

# Carrega as variáveis de ambiente do arquivo .env
# IMPORTANTE: load_dotenv() buscará o .env na pasta de onde você RODA o script,
# ou você pode especificar o caminho ex: load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))
load_dotenv()

# --- Configurações ---
# --- AJUSTE PARA EXECUÇÃO LOCAL ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VECTOR_DB_PATH = os.path.join(BASE_DIR, "lancedb_data")
print(f"--- ATENÇÃO: Rodando localmente. Caminho do Vector DB: {VECTOR_DB_PATH} ---")
# --- FIM DO AJUSTE LOCAL ---
# Para rodar no Docker, comente as 3 linhas acima e descomente a linha abaixo:
# VECTOR_DB_PATH = "/app/lancedb_data" # Caminho DENTRO do container

VECTOR_TABLE_NAME = "sisateg_knowledge_base"
EMBEDDER_MODEL_ID = "models/embedding-001"
BATCH_SIZE = 50

@contextmanager
def safe_db_operation(repo_instance=None): # Tornar repo_instance opcional
    """Context manager para operações seguras, incluindo rollback se disponível."""
    try:
        yield
    except KeyboardInterrupt:
        print("\n⚠️ Operação interrompida pelo usuário.")
        if repo_instance and hasattr(repo_instance, 'rollback'):
             repo_instance.rollback()
        raise # Re-levanta a interrupção para parar o script
    except Exception as e:
        print(f"\n❌ Erro durante operação: {e}")
        traceback.print_exc()
        if repo_instance and hasattr(repo_instance, 'rollback'):
             repo_instance.rollback()
        # Não re-levanta a exceção aqui para permitir que o loop principal continue se possível
        # Re-levantaremos no loop principal se for fatal.

async def add_batch_to_vector_db(knowledge_base_agno: Knowledge, batch_data: List[Dict[str, Any]]) -> Tuple[int, List[Dict[str, Any]]]:
    """Adiciona um lote de dados formatados ao banco vetorial de forma assíncrona."""
    tasks = []
    for item in batch_data:
        # Remove o prefixo file:// se existir
        file_path = item['text_path'].replace('file://', '') if item['text_path'].startswith('file://') else item['text_path']
        tasks.append(
            knowledge_base_agno.add_content_async(
                name=str(item['knowledge_id']),
                text_content=open(file_path, 'r', encoding='utf-8').read(),
                metadata={
                    'postgres_id': str(item['knowledge_id']),
                    'ticket_id': item['ticket_id']
                }
            )
        )
    results = await asyncio.gather(*tasks, return_exceptions=True)

    success_count = 0
    errors = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            error_msg = f"Erro ao vetorizar knowledge_id {batch_data[i]['knowledge_id']}: {result}"
            print(f"   -> ❌ {error_msg}")
            errors.append({
                "knowledge_id": batch_data[i]['knowledge_id'],
                "ticket_id": batch_data[i]['ticket_id'],
                "error": error_msg
            })
        else:
            success_count += 1
    return success_count, errors

def process_vector_batch(
    knowledge_repo: KnowledgeRepository,
    knowledge_base_agno: Knowledge,
    batch_ids: List[UUID],
    job_id: UUID
) -> Tuple[int, int, List[Dict[str, Any]]]:
    """
    Processa um lote de IDs da knowledge base para vetorização.
    Espelha a estrutura de `process_batch` do outro builder.
    Retorna (succeeded_count, failed_count, log_entries).
    """
    batch_start_time = time.time()
    log_entries = []
    batch_succeeded = 0
    batch_failed = 0
    formatted_batch_data: List[Dict[str, Any]] = [] # Para ter a lista disponível no finally

    try:
        # Fase 1: Buscar texto formatado usando a função do banco
        print(f"   → Buscando texto formatado para {len(batch_ids)} registros...")
        # Usamos safe_db_operation aqui também para a leitura
        with safe_db_operation(knowledge_repo):
            formatted_batch_data = knowledge_repo.get_formatted_knowledge_for_vectorization(batch_ids)

        if not formatted_batch_data:
            print("   ⚠️ Nenhum dado formatado retornado para este lote. Marcando como SKIPPED.")
            batch_failed = len(batch_ids) # Considera falha se não achou dados para os IDs
            log_entries = [{
                "knowledge_base_id": kid,
                "ticket_id": None, # Não sabemos o ticket_id aqui
                "status": "SKIPPED",
                "duration_ms": int((time.time() - batch_start_time) * 1000),
                "error_message": "Dados formatados não encontrados para o ID."
            } for kid in batch_ids]
            # Retorna imediatamente pois não há o que vetorizar
            return batch_succeeded, batch_failed, log_entries

        # Mapeia ID para ticket_id para logging posterior
        id_to_ticket_map = {item['knowledge_id']: item['ticket_id'] for item in formatted_batch_data}

        # Cria URLs temporárias para os textos
        temp_manager = TempFileManager()
        for item in formatted_batch_data:
            item['text_path'] = temp_manager.create_temp_file(item['text_to_embed'])

        # Fase 2: Adicionar ao banco vetorial (Vetorização + Inserção)
        print(f"   → Vetorizando e adicionando {len(formatted_batch_data)} registros ao LanceDB...")
        # A operação com LanceDB é I/O bound e pode falhar, mas não precisa de rollback transacional
        # Por isso, não envolvemos em safe_db_operation, mas tratamos erros retornados
        loop = asyncio.get_event_loop()
        batch_succeeded, errors_in_batch = loop.run_until_complete(add_batch_to_vector_db(knowledge_base_agno, formatted_batch_data))
        batch_failed = len(errors_in_batch)

        batch_duration_ms = int((time.time() - batch_start_time) * 1000)
        avg_time_per_item = batch_duration_ms / len(formatted_batch_data) if formatted_batch_data else 0

        print(f"   → Lote concluído em {batch_duration_ms} ms ({avg_time_per_item:.0f} ms/item)")
        print(f"     ✅ Sucesso: {batch_succeeded}")
        print(f"     ❌ Falhas: {batch_failed}")

        # Fase 3: Preparar logs detalhados
        # Mapa de erros para lookup rápido
        error_map = {e['knowledge_id']: e['error'] for e in errors_in_batch}

        for k_id in batch_ids: # Itera sobre os IDs originais do lote
            ticket_id = id_to_ticket_map.get(k_id) # Pega o ticket_id correspondente, se existir
            status = "UNKNOWN"
            error_message = None
            duration = 0

            if k_id in error_map:
                status = "FAILURE"
                error_message = error_map[k_id][:1000] # Limita tamanho
                duration = batch_duration_ms # Usa duração do lote para falhas individuais
            elif any(str(item['knowledge_id']) == str(k_id) for item in formatted_batch_data):
                # Se estava nos dados formatados E não está nos erros, foi sucesso
                 status = "SUCCESS"
                 duration = int(avg_time_per_item) # Média por item
            else:
                 # Se não estava nos dados formatados retornados pela query
                 status = "SKIPPED"
                 error_message = "Registro não encontrado nos dados formatados (inconsistência?)."

            log_entries.append({
                "knowledge_base_id": k_id, # Log com UUID
                "ticket_id": ticket_id,
                "status": status,
                "duration_ms": duration,
                "error_message": error_message
            })

        # Ajusta a contagem de falhas para incluir SKIPPEDs iniciais se houver
        # (Se formatted_batch_data estava vazio, batch_failed já era len(batch_ids))
        if formatted_batch_data:
            actual_failed_count = len([log for log in log_entries if log['status'] not in ["SUCCESS"]])
        else:
            actual_failed_count = batch_failed

        return batch_succeeded, actual_failed_count, log_entries

    except Exception as batch_error:
        # Erro crítico que impediu o processamento do lote (ex: falha na query SQL)
        error_msg = f"Erro crítico no lote: {str(batch_error)}"
        print(f"   -> ❌ {error_msg}")
        traceback.print_exc()
        batch_failed = len(batch_ids) # Todo o lote falhou
        duration = int((time.time() - batch_start_time) * 1000)
        # Loga falha para todos no lote
        log_entries = [{
            "knowledge_base_id": kid,
            "ticket_id": id_to_ticket_map.get(kid), # Tenta pegar o ticket_id se a query rodou
            "status": "BATCH_FAILURE",
            "duration_ms": duration,
            "error_message": error_msg[:1000]
        } for kid in batch_ids]

        return 0, batch_failed, log_entries


def main():
    """
    Loop principal que coordena o fluxo de trabalho.
    """
    # Garante que os arquivos temporários serão limpos
    temp_manager = TempFileManager()
    start_time_total = time.time()
    print(f"🚀 INICIANDO VETORIZAÇÃO DA BASE DE CONHECIMENTO ({JOB_TYPE_VECTORIZATION}) 🚀")

    # Configurando o event loop principal
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Instanciamos os repositórios
    knowledge_repo = KnowledgeRepository()
    log_repo = LogRepository()

    # Parâmetros (mantidos do original)
    MAX_RECORDS = 100 # Limite para testes (None para todos)
    count_processed = 0 # Contará os IDs processados (tentados)

    print("\n🔧 Configuração:")
    print(f"   → Tamanho do lote: {BATCH_SIZE}")
    print(f"   → Limite de registros: {MAX_RECORDS if MAX_RECORDS else 'Sem limite'}")

    total_succeeded = 0
    total_failed = 0
    job_id = None
    total_found = 0
    knowledge_base_agno = None # Para garantir que está definida no finally

    try:
        # --- Inicialização ---
        print("\n🔧 Configurando Embedder e Vector DB...")
        if not os.getenv("GOOGLE_API_KEY"):
            raise ValueError("Erro: Variável de ambiente GOOGLE_API_KEY não definida.")
        embedder = GeminiEmbedder(id=EMBEDDER_MODEL_ID)

        vector_db = LanceDb(
            uri=VECTOR_DB_PATH,
            table_name=VECTOR_TABLE_NAME,
            embedder=embedder
        )
        knowledge_base_agno = Knowledge(vector_db=vector_db)
        print("   → Embedder e Vector DB configurados.")

        # --- Busca Inicial e Criação do Job ---
        print(f"\n🔍 Buscando todos os registros na ybs_knowledge_base...")
        # **Lembrete:** Implementar get_all_knowledge_ids em knowledge_repository.py
        with safe_db_operation(knowledge_repo):
             all_knowledge_ids = knowledge_repo.get_all_knowledge_ids()
        total_found = len(all_knowledge_ids)

        if not all_knowledge_ids:
            print("🏁 Nenhum registro encontrado para vetorizar. Encerrando.")
            return

        print(f"   → {total_found} registros encontrados.")
        if MAX_RECORDS:
            all_knowledge_ids = all_knowledge_ids[:MAX_RECORDS]
            total_found = len(all_knowledge_ids) # Atualiza total_found se houver limite
            print(f"   → Limitando processamento a {total_found} registros.")


        # Cria o Job de Log
        with safe_db_operation(log_repo):
             job_id = log_repo.create_job(job_type=JOB_TYPE_VECTORIZATION, tickets_found=total_found, batch_size=BATCH_SIZE)
        print(f"   → Job de Log criado (ID: {job_id})")

        # --- Loop Principal de Processamento ---
        for i in range(0, total_found, BATCH_SIZE):
            batch_ids = all_knowledge_ids[i:i + BATCH_SIZE]
            current_batch_number = i // BATCH_SIZE + 1
            total_batches = (total_found + BATCH_SIZE - 1) // BATCH_SIZE

            print(f"\n--- Processando Lote {current_batch_number} / {total_batches} (Registros {i+1}-{min(i+BATCH_SIZE, total_found)}) ---")

            # Processa o lote atual usando a nova função
            succeeded, failed, log_entries = process_vector_batch(
                knowledge_repo, knowledge_base_agno, batch_ids, job_id
            )

            total_succeeded += succeeded
            total_failed += failed
            count_processed += len(batch_ids) # Incrementa pelos IDs tentados no lote

            # Registra os resultados do lote
            with safe_db_operation(log_repo):
                if log_entries:
                    # **Lembrete:** Adaptar log_batch_details para aceitar knowledge_base_id (UUID)
                    log_repo.log_batch_details(job_id, log_entries)

            # Verifica se atingiu o limite (redundante com a lógica no início, mas seguro)
            if MAX_RECORDS and count_processed >= MAX_RECORDS:
                print(f"\n🎯 Limite de {MAX_RECORDS} registro(s) processados atingido.")
                break

        print("\n🏁 Processamento de lotes concluído.")

    except KeyboardInterrupt:
        print("\n\n⚠️ Vetorização interrompida pelo usuário")
        if job_id:
            with safe_db_operation(log_repo):
                 log_repo.update_job_summary(job_id, "INTERRUPTED", total_succeeded, total_failed, "Processo interrompido.")

    except Exception as e:
        error_summary = f"Erro fatal durante a vetorização: {e}"
        print(f"\n🚨 {error_summary} 🚨")
        traceback.print_exc()
        if job_id:
            with safe_db_operation(log_repo):
                log_repo.update_job_summary(job_id, "FAILED", total_succeeded, total_failed, error_summary[:1000])

    finally:
        # --- Finalização e Sumário ---
        end_time_total = time.time()
        total_time = end_time_total - start_time_total

        print("\n" + "="*60)
        print("🏁 RESUMO DA VETORIZAÇÃO 🏁")
        print("="*60)

        final_status = "UNKNOWN"
        # Determina status final baseado nos resultados e se houve interrupção/erro
        if 'KeyboardInterrupt' in locals():
            final_status = "INTERRUPTED"
        elif 'e' in locals() and isinstance(e, Exception) and job_id: # Erro fatal capturado
            final_status = "FAILED"
        elif total_failed > 0 and total_succeeded > 0:
            final_status = "PARTIAL"
        elif total_failed > 0 and total_succeeded == 0:
             final_status = "FAILED"
        elif total_failed == 0 and total_succeeded == total_found:
             final_status = "COMPLETED"
        elif total_failed == 0 and total_succeeded < total_found and total_found > 0 : # Processou menos que o total (ex: limite MAX_RECORDS)
             final_status = "PARTIAL" # Ou "LIMITED"? Vamos usar PARTIAL.
        elif total_found == 0:
             final_status = "COMPLETED" # Completou, mas não tinha nada a fazer

        if job_id:
            try:
                # Atualiza o job log apenas se foi criado
                with safe_db_operation(log_repo):
                    log_repo.update_job_summary(job_id, final_status, total_succeeded, total_failed)
                print(f"   → Job de Log atualizado (ID: {job_id}, Status: {final_status})")
            except Exception as log_update_err:
                print(f"   ⚠️ Falha ao atualizar o status final do Job de Log: {log_update_err}")
        else:
             print("   → Job de Log não foi criado (nenhum registro encontrado ou erro inicial).")


        print(f"\n📊 Estatísticas Finais:")
        print(f"   → Total de registros encontrados: {total_found}")
        print(f"   → Total de registros tentados: {count_processed}")
        print(f"   → ✅ Vetorizados com sucesso: {total_succeeded}")
        print(f"   → ❌ Falhas na vetorização: {total_failed}")
        if count_processed > 0:
             success_rate = (total_succeeded / count_processed * 100)
             print(f"   → Taxa de sucesso (sobre tentados): {success_rate:.1f}%")
        print(f"   → ⏱️ Tempo total de execução: {total_time:.1f} segundos")
        if total_succeeded > 0:
            avg_time_per_success = total_time / total_succeeded
            print(f"   → Média de tempo por registro (sucesso): {avg_time_per_success:.2f} segundos")

        # Fechar conexões e limpar arquivos temporários
        if knowledge_repo: knowledge_repo.close()
        if log_repo: log_repo.close()
        temp_manager.cleanup()
        loop.close() # Fecha o event loop principal
        print("\nConexões com banco de dados fechadas e arquivos temporários limpos.")
        print("="*60)

if __name__ == "__main__":
    main()
