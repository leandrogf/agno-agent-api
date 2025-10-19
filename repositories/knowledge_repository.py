# agent-api/repositories/knowledge_repository.py

from .base_repository import BaseRepository
from typing import List, Dict, Any
from uuid import UUID
class KnowledgeRepository(BaseRepository):
    """
    Repository for managing all operations related to the ybs_knowledge_base table.
    """

    def get_all_knowledge_ids(self) -> List[UUID]:
        """
        Retorna todos os IDs da knowledge base ordenados por ticket_id.
        """
        query = """
            SELECT id
            FROM public.ybs_knowledge_base
            ORDER BY ticket_id;
        """
        results = self.execute(query)
        return [row['id'] for row in results]

    def close(self):
        """
        Fecha a conexão com o banco de dados.
        """
        if hasattr(self, '_session'):
            self._session.close()
    def save_batch(self, knowledge_batch: List[Dict[str, Any]]) -> List[str]:
        """
        Inserts or updates a batch of knowledge records into the database.
        Uses ON CONFLICT to handle records that might already exist.
        Returns the list of UUIDs for the inserted/updated records.
        """
        if not knowledge_batch:
            return []

        # The query uses the new English column names.
        query = """
            INSERT INTO public.ybs_knowledge_base (
                ticket_id, tfs_work_item_id, title, problem_summary, root_cause_analysis,
                solution_applied, solution_type, sql_template, tags, ticket_level,
                llm_model, processing_version, created_at, updated_at
            )
            VALUES (
                :ticket_id, :tfs_work_item_id, :title, :problem_summary, :root_cause_analysis,
                :solution_applied, :solution_type, :sql_template, :tags, :ticket_level,
                :llm_model, :processing_version, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
            ON CONFLICT (ticket_id) DO UPDATE SET
                title = EXCLUDED.title,
                problem_summary = EXCLUDED.problem_summary,
                root_cause_analysis = EXCLUDED.root_cause_analysis,
                solution_applied = EXCLUDED.solution_applied,
                solution_type = EXCLUDED.solution_type,
                tags = EXCLUDED.tags,
                llm_model = EXCLUDED.llm_model,
                processing_version = EXCLUDED.processing_version,
                updated_at = CURRENT_TIMESTAMP
            RETURNING id;
        """

        # The base 'execute' method handles passing the list of dictionaries
        # which SQLAlchemy interprets as a batch insert (executemany).
        results = self.execute(query, knowledge_batch)
        return [row['id'] for row in results]

    def get_formatted_knowledge_for_vectorization(self, knowledge_ids: List[UUID]) -> List[Dict[str, Any]]:
        """
        Busca o texto formatado para vetorização para uma lista de IDs de conhecimento
        usando a função do banco de dados.
        """
        if not knowledge_ids:
            return []

        # Converte UUIDs para strings se a biblioteca de DB preferir,
        # mas passar como lista de UUIDs para :knowledge_ids deve funcionar com psycopg3/sqlalchemy
        query = """
            SELECT
                knowledge_id,
                ticket_id,
                knowledge_text
            FROM
                public.fn_gera_texto_conhecimento_para_vetorizacao(ARRAY[:knowledge_ids])
        """

        # Passa a lista de UUIDs como parâmetro
        results = self.execute(query, {"knowledge_ids": knowledge_ids})

        # Retorna uma lista de dicionários prontos para o processo de embedding
        return [
            {
                "knowledge_id": row['knowledge_id'], # UUID
                "ticket_id": row['ticket_id'],     # int
                "text_to_embed": row['knowledge_text'] # str
            }
            for row in results
        ]
