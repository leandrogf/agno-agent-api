# agent-api/batch_processor.py
from dotenv import load_dotenv
import time
import json
from uuid import UUID
# Importa o especialista em análise de lote que definimos
from agents.knowledge_builder_definitions import batch_analysis_agent

# Importa os repositórios, nossa única camada de acesso a dados
from repositories.chamados_repository import ChamadosRepository
from repositories.knowledge_repository import KnowledgeRepository
from repositories.log_repository import LogRepository

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

def main():
    """
    Função principal que orquestra o processamento em massa de chamados,
    utilizando uma arquitetura de repositórios para acesso a dados e logging robusto.
    """
    # --- 1. SETUP INICIAL ---
    start_time_total = time.time()
    print("🚀 INICIANDO PROCESSAMENTO EM MASSA (ARQUITETURA DE REPOSITÓRIO) 🚀")

    # Instanciamos os repositórios que o worker irá usar
    chamados_repo = ChamadosRepository()
    knowledge_repo = KnowledgeRepository()
    log_repo = LogRepository()

    # Parâmetros de execução
    BATCH_SIZE = 50

    total_succeeded = 0
    total_failed = 0
    job_id = None
    tickets_found = 0

    try:
        # --- 2. CRIAÇÃO DO JOB DE LOG ---
        initial_tickets = chamados_repo.get_unprocessed_tickets(limit=1)
        if not initial_tickets:
            print("🏁 Nenhum chamado para processar. Encerrando.")
            return

        tickets_found = len(initial_tickets)
        job_id = log_repo.create_job(tickets_found=tickets_found, batch_size=BATCH_SIZE)

        # --- 3. LOOP DE PROCESSAMENTO EM LOTES ---
        while True:
            ticket_ids_batch = chamados_repo.get_unprocessed_tickets(limit=BATCH_SIZE)
            if not ticket_ids_batch:
                print("🏁 Todos os chamados foram processados.")
                break

            print(f"\n--- Processando lote de {len(ticket_ids_batch)} chamados (Job ID: {job_id}) ---")

            batch_start_time = time.time()
            log_entries = []

            try:
                dossiers_data = chamados_repo.generate_dossiers_for_tickets(ticket_ids_batch)

                llm_input = json.dumps([item['dossier_text'] for item in dossiers_data])
                analysis_result = batch_analysis_agent.run(input=llm_input)
                knowledge_records = analysis_result.records

                if len(knowledge_records) != len(dossiers_data):
                    raise ValueError(f"Inconsistência de contagem da LLM. Entrada: {len(dossiers_data)}, Saída: {len(knowledge_records)}")

                knowledge_to_save = [record.model_dump() for record in knowledge_records]

                saved_ids = knowledge_repo.save_batch(knowledge_to_save)
                id_map = {item['ticket_id']: saved_id for item, saved_id in zip(knowledge_to_save, saved_ids)}
                chamados_repo.mark_tickets_as_processed([item['ticket_id'] for item in knowledge_to_save])

                for item in knowledge_to_save:
                    ticket_id = item['ticket_id']
                    duration = int((time.time() - batch_start_time) * 1000 / len(ticket_ids_batch))
                    log_entries.append({
                        "ticket_id": ticket_id,
                        "knowledge_base_id": id_map.get(ticket_id),
                        "status": "SUCCESS",
                        "duration_ms": duration,
                        "error_message": None
                    })
                total_succeeded += len(knowledge_to_save)
                print(f"  -> ✅ Lote processado com sucesso em {time.time() - batch_start_time:.2f} segundos.")

            except Exception as e:
                error_msg = f"Erro no processamento do lote: {str(e)}"
                print(f"  -> ❌ {error_msg}")
                duration = int((time.time() - batch_start_time) * 1000)
                for ticket_id in ticket_ids_batch:
                    log_entries.append({
                        "ticket_id": ticket_id,
                        "knowledge_base_id": None,
                        "status": "BATCH_FAILURE",
                        "duration_ms": duration,
                        "error_message": error_msg
                    })
                total_failed += len(ticket_ids_batch)

            finally:
                if log_entries:
                    log_repo.log_batch_details(job_id, log_entries)

    except Exception as e:
        error_summary = f"Erro fatal no worker: {e}"
        print(f"\n🚨 {error_summary} 🚨")
        if job_id:
            log_repo.update_job_summary(
                job_id, "FAILED", total_succeeded, total_failed, error_summary
            )

    finally:
        # --- 4. FINALIZAÇÃO E SUMÁRIO DO JOB ---
        end_time_total = time.time()
        print("\n===================================================")
        print("🏁 PROCESSAMENTO EM MASSA CONCLUÍDO 🏁")
        print("===================================================")
        if job_id:
            final_status = "COMPLETED" if 'e' not in locals() or not isinstance(e, Exception) else "FAILED"
            log_repo.update_job_summary(
                job_id, final_status, total_succeeded, total_failed
            )
            print(f"  - Job ID: {job_id}")

        print(f"  - Total de chamados encontrados: {tickets_found}")
        print(f"  - ✅ Sucessos: {total_succeeded}")
        print(f"  - ❌ Falhas: {total_failed}")
        print(f"  - ⏱️ Tempo total: {end_time_total - start_time_total:.2f} segundos")

if __name__ == "__main__":
    main()
