# agent-api/repositories/knowledge_repository.py

from .base_repository import BaseRepository
from typing import List, Dict, Any

class KnowledgeRepository(BaseRepository):
    """
    Repository for managing all operations related to the ybs_knowledge_base table.
    """
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
