# agent-api/repositories/chamados_repository.py

from .base_repository import BaseRepository
from typing import List, Dict, Any

class ChamadosRepository(BaseRepository):
    """
    Repositório para gerenciar todas as operações relacionadas à tabela sisateg_chamados.
    """
    def get_unprocessed_tickets(self, limit: int = 100) -> List[int]:
        """
        Busca os códigos de chamados encerrados que ainda não foram processados.
        """
        query = """
            SELECT cod_chamado FROM sisateg_chamados
            WHERE cod_situacao_chamado = 5 AND (knowledge_processado IS NULL OR knowledge_processado = FALSE)
            ORDER BY dat_inclusao ASC
            LIMIT :limit;
        """
        results = self.execute(query, {"limit": limit})
        return [row['cod_chamado'] for row in results]

    def generate_dossiers_for_tickets(self, ticket_ids: List[int]) -> List[Dict[str, Any]]:
        """
        Gera os dossiês para uma lista de chamados usando a função do banco.
        """
        query = "SELECT cod_chamado, dossie FROM fn_gera_dossie_chamado_para_lista(ARRAY[:ticket_ids])"
        results = self.execute(query, {"ticket_ids": ticket_ids})
        return [{"ticket_id": row['cod_chamado'], "dossier_text": row['dossie']} for row in results]

    def mark_tickets_as_processed(self, ticket_ids: List[int]) -> None:
        """
        Marca uma lista de chamados como processados na base de dados.
        """
        query = """
            UPDATE sisateg_chamados
            SET
                knowledge_processado = TRUE,
                knowledge_data_processamento = CURRENT_TIMESTAMP
            WHERE cod_chamado = ANY(:ticket_ids);
        """
        self.execute(query, {"ticket_ids": ticket_ids})