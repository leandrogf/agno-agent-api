# agent-api/batch_processor.py
from dotenv import load_dotenv
import time
import json
from uuid import UUID
import traceback
import os
from contextlib import contextmanager

# Importa o especialista em análise de lote que definimos
from agents.knowledge_builder import batch_analysis_agent

# Importa os repositórios, nossa única camada de acesso a dados
from repositories.chamados_repository import ChamadosRepository
from repositories.knowledge_repository import KnowledgeRepository
from repositories.log_repository import LogRepository

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

@contextmanager
def safe_db_operation():
    """Context manager para operações seguras de banco de dados"""
    try:
        yield
    except KeyboardInterrupt:
        print("\n⚠️ Operação interrompida pelo usuário. Realizando rollback...")
        raise
    except Exception as e:
        print(f"\n❌ Erro durante operação de banco de dados: {e}")
        traceback.print_exc()
        raise

def parse_agent_response(raw_result, job_id):
    """Parse e valida a resposta do agente, lidando com diferentes formatos"""
    if raw_result is None:
        raise ValueError("Resposta vazia do agente")

    # Salva a resposta bruta para debug
    import os
    import json
    from datetime import datetime

    temp_dir = os.path.join(os.path.dirname(__file__), "__TEMP__")
    os.makedirs(temp_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    debug_file = os.path.join(temp_dir, f"raw_response_{job_id}_{timestamp}.json")

    with open(debug_file, 'w', encoding='utf-8') as f:
        if hasattr(raw_result, 'content'):
            content = raw_result.content.strip()
            # Remove markdown delimitadores se presentes
            if content.startswith('```'):
                parts = content.split('```')
                if len(parts) >= 3:
                    content = parts[1]
                    if content.startswith('json'):
                        content = content[4:]
                    content = content.strip()
            f.write(content)
        else:
            json.dump(raw_result, f, ensure_ascii=False, separators=(',', ':'))

    print(f"\n💾 Resposta bruta salva em: {debug_file}")

    # Debug do resultado bruto
    print("\n🔍 Analisando resposta da IA:")
    print(f"   Tipo: {type(raw_result).__name__}")

    content = None
    # Determina o conteúdo baseado no tipo da resposta
    if hasattr(raw_result, 'content'):
        print("   → Conteúdo encontrado em raw_result.content")
        content = raw_result.content
    elif isinstance(raw_result, dict):
        print("   → Resultado já é um dicionário")
        content = raw_result
    else:
        print(f"\n❌ Erro: Formato de resposta inesperado: {type(raw_result)}")
        raise ValueError(f"Formato de resposta não suportado: {type(raw_result)}")

    # Se o conteúdo é uma string, tenta parsear como JSON
    if isinstance(content, str):
        print("   → Convertendo resposta string para JSON")
        try:
            # Remove markdown code blocks se presentes
            clean_content = content.strip()
            if clean_content.startswith('```'):
                print("\n   Detectado code block markdown, removendo...")
                # Pegamos o que está entre os codeblocks
                parts = clean_content.split('```')
                if len(parts) >= 3:  # tem o início e fim dos delimitadores
                    # Pega o conteúdo entre os delimitadores
                    clean_content = parts[1]
                    # Remove 'json' se presente no começo
                    if clean_content.startswith('json'):
                        print("   → Removendo prefixo 'json'")
                        clean_content = clean_content[4:]
                    clean_content = clean_content.strip()
                    # print(f"\n   → Conteúdo limpo: \n{clean_content}")
                else:
                    print("\n❌ Erro: Formato markdown inválido")
                    raise ValueError("Formato markdown inválido")

            # print("\n🔍 JSON preparado para parsing:")
            # print(clean_content)
            content = json.loads(clean_content)
            print("\n✅ JSON parseado com sucesso")

        except json.JSONDecodeError as e:
            print("\n❌ Erro ao decodificar JSON da resposta:")
            print(f"Conteúdo bruto:\n{content[:1000]}")
            print(f"Conteúdo limpo:\n{clean_content}")
            print(f"Erro: {str(e)}")
            raise ValueError(f"Falha ao parsear JSON: {str(e)}")

    # Validação do formato esperado
    if not isinstance(content, dict):
        raise ValueError(f"Resposta inválida: esperava dict, recebi {type(content)}")

    if 'records' not in content:
        print("\n❌ Erro: Resposta não contém registros válidos")
        print(f"Conteúdo: {str(content)[:500]}")
        raise ValueError("Estrutura inválida: 'records' não encontrado")

    # Valida cada registro retornado
    for record in content['records']:
        required_fields = ['ticket_id', 'title', 'problem_summary', 'tags']
        missing_fields = [f for f in required_fields if f not in record]
        if missing_fields:
            raise ValueError(f"Campos obrigatórios faltando no registro: {missing_fields}")

    return content

def process_batch(batch_analysis_agent, chamados_repo, knowledge_repo, log_repo,
                 ticket_ids_batch, job_id, count_processed):
    """Processa um lote de chamados com retry e validação"""
    batch_start_time = time.time()
    log_entries = []

    try:
        # Fase 1: Geração dos dossiês
        print("\n📑 Gerando dossiês para análise...")
        dossiers_data = chamados_repo.generate_dossiers_for_tickets(ticket_ids_batch)
        if not dossiers_data:
            raise ValueError("Nenhum dossiê foi gerado para os chamados selecionados")

        # Fase 2: Preparação dos dados para o LLM
        # Prepara o input incluindo ticket_id e texto do dossiê
        input_data = []
        for item in dossiers_data:
            input_data.append({
                "ticket_id": item['ticket_id'],
                "dossier_text": item['dossier_text']
            })
        llm_input = json.dumps(input_data)
        input_size = len(llm_input)
        print(f"🔍 Enviando para análise: {input_size:,} caracteres")
        if input_size < 10:
            raise ValueError("Texto do dossiê muito curto para análise")

        # Fase 3: Execução do agente com retries
        print("🤖 Executando análise com IA...")
        max_retries = 3
        last_error = None
        raw_result = None

        # Cria diretório temporário se não existir
        temp_dir = os.path.join(os.path.dirname(__file__), "__TEMP__")
        os.makedirs(temp_dir, exist_ok=True)

        for attempt in range(max_retries):
            try:
                print(f"\n🔄 Tentativa {attempt + 1}/{max_retries}")

                raw_result = batch_analysis_agent.run(
                    input=llm_input,
                    session_id=str(job_id),
                    metadata={
                        "batch_size": len(ticket_ids_batch),
                        "job_id": str(job_id),
                        "tickets": [str(id) for id in ticket_ids_batch],
                        "input_size": input_size,
                        "processing_version": 1
                    },
                    stream=False,
                    session_state={
                        "last_successful_batch": None,
                        "current_batch_index": count_processed
                    },
                    timeout=120  # 2 minute timeout
                )

                if raw_result is not None:
                    break

            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    delay = 2 ** attempt
                    print(f"❌ Tentativa {attempt + 1} falhou:")
                    print(f"   Erro: {str(e)}")
                    print(f"   Tipo: {type(e)}")
                    if hasattr(e, '__dict__'):
                        print(f"   Atributos: {e.__dict__}")
                    print(f"⏳ Aguardando {delay}s antes da próxima tentativa...")
                    time.sleep(delay)
                    continue
                else:
                    print(f"❌ Última tentativa falhou:")
                    print(f"   Erro: {str(e)}")
                    print(f"   Tipo: {type(e)}")
                    if hasattr(e, '__dict__'):
                        print(f"   Atributos: {e.__dict__}")
                    raise

        if raw_result is None:
            raise ValueError(f"Todas as {max_retries} tentativas falharam. Último erro: {str(last_error)}")

        # Fase 4: Parsing e validação da resposta
        analysis_result = parse_agent_response(raw_result, job_id)
        knowledge_records = analysis_result['records']

        if not knowledge_records:
            raise ValueError("Lista de registros vazia")

        if len(knowledge_records) < len(dossiers_data):
            print(f"\n⚠️ Aviso: Nem todos os chamados foram analisados.")
            print(f"   → Entrada: {len(dossiers_data)} chamados")
            print(f"   → Saída: {len(knowledge_records)} registros")
            print(f"   → {len(dossiers_data) - len(knowledge_records)} chamados serão processados na próxima execução")

        print(f"\n✅ Análise concluída!")
        print(f"   → {len(knowledge_records)} registros gerados")

        # Fase 5: Persistência dos resultados
        # Adiciona ticket_id a cada registro e converte para modelos Pydantic
        from agents.knowledge_builder import KnowledgeRecord
        knowledge_to_save = []
        # Cria um mapa de ticket_id para dossier para lookup rápido
        dossier_map = {str(d['ticket_id']): d for d in dossiers_data}

        for record in knowledge_records:
            # Usa o ticket_id que já deve estar no record (garantido pelo parser)
            ticket_id = str(record.get('ticket_id'))
            if not ticket_id or ticket_id not in dossier_map:
                print(f"\n⚠️ Aviso: Record sem ticket_id válido ou ticket_id não encontrado nos dossiês: {record}")
                continue

            model_dict = record.copy()  # Cria uma cópia do dicionário para não modificar o original
            # Não sobrescrevemos o ticket_id pois ele já deve estar correto
            model_dict.update({
                'llm_model': 'gemini-2.0-flash',    # Adiciona modelo usado
                'processing_version': 1             # Adiciona versão do processamento
            })
            knowledge_record = KnowledgeRecord(**model_dict)
            knowledge_to_save.append(knowledge_record.model_dump())
        # Salva os registros processados
        if knowledge_to_save:
            saved_ids = knowledge_repo.save_batch(knowledge_to_save)
            id_map = {item['ticket_id']: saved_id for item, saved_id in zip(knowledge_to_save, saved_ids)}

            # Marca apenas os tickets que foram processados com sucesso
            processed_ticket_ids = [item['ticket_id'] for item in knowledge_to_save]
            chamados_repo.mark_tickets_as_processed(processed_ticket_ids)

            # Registra os sucessos
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

            # Registra os não processados
            unprocessed_ticket_ids = set(d['ticket_id'] for d in dossiers_data) - set(processed_ticket_ids)
            for ticket_id in unprocessed_ticket_ids:
                log_entries.append({
                    "ticket_id": ticket_id,
                    "knowledge_base_id": None,
                    "status": "PENDING",
                    "duration_ms": 0,
                    "error_message": "Chamado não processado neste lote"
                })

        return len(knowledge_records), 0, log_entries

    except Exception as e:
        error_msg = f"Erro no processamento do lote: {str(e)}"
        print(f"  -> ❌ {error_msg}")
        duration = int((time.time() - batch_start_time) * 1000)

        log_entries = [{
            "ticket_id": ticket_id,
            "knowledge_base_id": None,
            "status": "BATCH_FAILURE",
            "duration_ms": duration,
            "error_message": error_msg
        } for ticket_id in ticket_ids_batch]

        return 0, len(ticket_ids_batch), log_entries

def main():
    """
    Função principal que orquestra o processamento em massa de chamados,
    utilizando uma arquitetura de repositórios para acesso a dados e logging robusto.
    """
    start_time_total = time.time()
    print("🚀 INICIANDO PROCESSAMENTO EM MASSA (ARQUITETURA DE REPOSITÓRIO) 🚀")

    # Instanciamos os repositórios
    chamados_repo = ChamadosRepository()
    knowledge_repo = KnowledgeRepository()
    log_repo = LogRepository()

    # Parâmetros de execução
    BATCH_SIZE = 5  # Processa 20 chamados por vez
    MAX_TICKETS = None  # Limite de chamados a processar (para testes)
    count_processed = 0

    print("\n🔧 Configuração:")
    print(f"   → Tamanho do lote: {BATCH_SIZE}")
    print(f"   → Limite de chamados: {MAX_TICKETS if MAX_TICKETS else 'Sem limite'}")

    total_succeeded = 0
    total_failed = 0
    job_id = None
    tickets_found = 0

    try:
        # Verificação inicial de tickets
        initial_tickets = chamados_repo.get_unprocessed_tickets(limit=MAX_TICKETS if MAX_TICKETS else None)
        if not initial_tickets:
            print("🏁 Nenhum chamado para processar. Encerrando.")
            return

        tickets_found = len(initial_tickets)
        with safe_db_operation():
            job_id = log_repo.create_job(tickets_found=tickets_found, batch_size=BATCH_SIZE)

        # Loop principal de processamento
        while True:
            # Verifica se atingiu o limite de chamados
            if MAX_TICKETS and count_processed >= MAX_TICKETS:
                print(f"\n🎯 Limite de {MAX_TICKETS} chamado(s) atingido.")
                break

            ticket_ids_batch = chamados_repo.get_unprocessed_tickets(limit=BATCH_SIZE)
            if not ticket_ids_batch:
                print("🏁 Todos os chamados foram processados.")
                break

            print(f"\n--- Processando lote de {len(ticket_ids_batch)} chamados (Job ID: {job_id}) ---")
            print(f"   → Processados até agora: {count_processed} de {MAX_TICKETS if MAX_TICKETS else 'ilimitado'}")

            # Processa o lote atual
            succeeded, failed, log_entries = process_batch(
                batch_analysis_agent, chamados_repo, knowledge_repo, log_repo,
                ticket_ids_batch, job_id, count_processed
            )

            total_succeeded += succeeded
            total_failed += failed
            count_processed += len(ticket_ids_batch) # Incrementa baseado no tamanho do lote

            # Registra os resultados do lote
            with safe_db_operation():
                if log_entries:
                    log_repo.log_batch_details(job_id, log_entries)

    except KeyboardInterrupt:
        print("\n\n⚠️ Processamento interrompido pelo usuário")
        error_summary = "Processamento interrompido pelo usuário"
        if job_id:
            with safe_db_operation():
                log_repo.update_job_summary(
                    job_id, "INTERRUPTED", total_succeeded, total_failed, error_summary
                )

    except Exception as e:
        error_summary = f"Erro fatal no worker: {e}"
        print(f"\n🚨 {error_summary} 🚨")
        traceback.print_exc()
        if job_id:
            with safe_db_operation():
                log_repo.update_job_summary(
                    job_id, "FAILED", total_succeeded, total_failed, error_summary
                )

    finally:
        # Finalização e sumário
        end_time_total = time.time()
        total_time = end_time_total - start_time_total

        print("\n" + "="*60)
        print("🏁 RESUMO DO PROCESSAMENTO EM MASSA 🏁")
        print("="*60)

        if job_id:
            final_status = "COMPLETED" if 'e' not in locals() else "FAILED"
            with safe_db_operation():
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

        print(f"\nResumo final:")
        print(f"  - Total de chamados encontrados: {tickets_found}")
        print(f"  - ✅ Sucessos: {total_succeeded}")
        print(f"  - ❌ Falhas: {total_failed}")
        print(f"  - ⏱️ Tempo total: {total_time:.2f} segundos")

if __name__ == "__main__":
    main()
