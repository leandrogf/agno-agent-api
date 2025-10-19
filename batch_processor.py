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
    BATCH_SIZE = 1  # Processamento individual para melhor controle
    MAX_RETRIES = 3  # Número máximo de tentativas por chamado
    count_processed = 0

    print("\n🔧 Configuração:")
    print(f"   → Tamanho do lote: {BATCH_SIZE}")
    print(f"   → Máximo de tentativas: {MAX_RETRIES}")

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
        job_id = log_repo.create_job(tickets_found=tickets_found, batch_size=BATCH_SIZE, job_type='knowledge')
        c = 0
        # --- 3. LOOP DE PROCESSAMENTO EM LOTES ---
        while True or count_processed == 1:

            ticket_ids_batch = chamados_repo.get_unprocessed_tickets(limit=BATCH_SIZE)
            if not ticket_ids_batch:
                print("🏁 Todos os chamados foram processados.")
                break

            print(f"\n--- Processando lote de {len(ticket_ids_batch)} chamados (Job ID: {job_id}) ---")

            batch_start_time = time.time()
            log_entries = []

            try:
                # Fase 1: Geração dos dossiês
                print("\n📑 Gerando dossiês para análise...")
                dossiers_data = chamados_repo.generate_dossiers_for_tickets(ticket_ids_batch)
                if not dossiers_data:
                    raise ValueError("Nenhum dossiê foi gerado para os chamados selecionados")

                # Fase 2: Preparação dos dados para o LLM
                llm_input = json.dumps([item['dossier_text'] for item in dossiers_data])
                input_size = len(llm_input)
                print(f"🔍 Enviando para análise: {input_size:,} caracteres")
                if input_size < 10:
                    raise ValueError("Texto do dossiê muito curto para análise")

                # Fase 3: Execução do agente e validação da resposta
                print("🤖 Executando análise com IA...")

                # Configuração de metadados para rastreamento
                execution_metadata = {
                    "batch_size": BATCH_SIZE,
                    "job_id": str(job_id),
                    "tickets": [str(id) for id in ticket_ids_batch],
                    "input_size": input_size,
                    "processing_version": 1
                }

                # Tentar executar o agente com retries
                max_retries = 3
                raw_result = None
                last_error = None

                for attempt in range(max_retries):
                    try:
                        print(f"\n🔄 Tentativa {attempt + 1}/{max_retries}")
                        raw_result = batch_analysis_agent.run(
                            input=llm_input,
                            session_id=str(job_id),
                            metadata=execution_metadata,
                            stream=False,
                            session_state={  # Cache de estado da sessão
                            "last_successful_batch": None,
                                "current_batch_index": count_processed
                            },
                            timeout=120  # 2 minute timeout
                        )

                        if raw_result is not None and hasattr(raw_result, 'content'):
                            break  # Success, exit retry loop

                    except Exception as retry_error:
                        if attempt < 2:  # Don't sleep on last attempt
                            time.sleep(2 ** attempt)  # Exponential backoff: 1s, 2s, 4s
                            print(f"Tentativa {attempt + 1} falhou, tentando novamente...")
                            continue
                        raise  # Re-raise on final attempt

                    # Debug do resultado bruto da IA
                    print("\n🔍 Analisando resposta da IA:")
                    print(f"   Tipo: {type(raw_result).__name__}")
                    if hasattr(raw_result, 'content'):
                        print("   → Conteúdo encontrado em raw_result.content")
                        print(f"   → Tipo do conteúdo: {type(raw_result.content).__name__}")
                        print(f"   → Valor: {str(raw_result.content)[:1000]}")
                        analysis_result = raw_result.content
                    elif isinstance(raw_result, dict):
                        print("   → Resultado já é um dicionário")
                        print(f"   → Valor: {str(raw_result)[:1000]}")
                        analysis_result = raw_result
                    else:
                        print("\n❌ Erro: Formato de resposta inesperado")
                        print(f"   Tipo: {type(raw_result).__name__}")
                        print(f"   Valor: {str(raw_result)[:1000]}")

                        # Tentar extrair mais informações se possível
                        print("\n🔬 Tentando extrair mais informações:")
                        for attr in dir(raw_result):
                            if not attr.startswith('_'):
                                try:
                                    value = getattr(raw_result, attr)
                                    print(f"   → {attr}: {str(value)[:200]}")
                                except:
                                    continue

                        raise ValueError("Formato de resposta inválido")

                    # Improved response handling
                    if raw_result is None:
                        raise ValueError("Resposta vazia do agente")

                    # Handle string response (common with Gemini)
                    if isinstance(raw_result.content, str):
                        try:
                            # Clean up the response if it's a markdown code block
                            content = raw_result.content.strip()
                            if content.startswith('```json'):
                                content = content[7:].strip()
                            if content.endswith('```'):
                                content = content[:-3].strip()
                            analysis_result = json.loads(content)
                        except json.JSONDecodeError as e:
                            print(f"\n❌ Erro ao decodificar JSON: {e}")
                            print(f"Resposta bruta:\n{raw_result.content}")
                            raise ValueError(f"Falha ao parsear JSON da resposta: {e}")
                    else:
                        analysis_result = raw_result.content

                    if not isinstance(analysis_result, dict):
                        raise ValueError(f"Resposta inválida, esperava dict mas recebi {type(analysis_result)}")

                    if 'records' not in analysis_result:
                        print("\n❌ Erro: Resposta não contém registros válidos")
                        print(f"   Conteúdo: {str(analysis_result)[:500]}")
                        raise ValueError("Estrutura de resposta inválida: 'records' não encontrado")

                    knowledge_records = analysis_result['records']
                    if not knowledge_records:
                        raise ValueError("Lista de registros vazia")

                    print(f"\n✅ Análise concluída com sucesso!")
                    print(f"   → {len(knowledge_records)} registros gerados")
                    if knowledge_records:
                        print("   → Campos encontrados:", list(knowledge_records[0].keys()))
                    except Exception as e:
                        print(f"❌ Erro durante a análise do lote: {str(e)}")
                        raise

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
                count_processed += 1
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
        total_time = end_time_total - start_time_total

        print("\n" + "="*60)
        print("🏁 RESUMO DO PROCESSAMENTO EM MASSA 🏁")
        print("="*60)

        if job_id:
            final_status = "COMPLETED" if 'e' not in locals() or not isinstance(e, Exception) else "FAILED"
            log_repo.update_job_summary(
                job_id, final_status, total_succeeded, total_failed
            )

            print(f"\n📊 Estatísticas:")
            print(f"   → ID do Job: {job_id}")
            print(f"   → Status: {'✅ Concluído' if final_status == 'COMPLETED' else '❌ Falhou'}")
            print(f"   → Chamados processados com sucesso: {total_succeeded}")
            print(f"   → Chamados com falha: {total_failed}")
            print(f"   → Taxa de sucesso: {(total_succeeded/(total_succeeded+total_failed)*100 if total_succeeded+total_failed > 0 else 0):.1f}%")
            print(f"   → Tempo total de execução: {total_time:.1f} segundos")

            if total_succeeded > 0:
                print(f"   → Média de tempo por chamado: {(total_time/total_succeeded):.1f} segundos")

        print(f"  - Total de chamados encontrados: {tickets_found}")
        print(f"  - ✅ Sucessos: {total_succeeded}")
        print(f"  - ❌ Falhas: {total_failed}")
        print(f"  - ⏱️ Tempo total: {end_time_total - start_time_total:.2f} segundos")

if __name__ == "__main__":
    main()
