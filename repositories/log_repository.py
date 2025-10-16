# agent-api/repositories/log_repository.py

from .base_repository import BaseRepository
from typing import List, Dict, Any, Optional
import json

class LogRepository(BaseRepository):
    """
    Repository for managing knowledge processing jobs and detailed logs.
    """
    def create_job(self, tickets_found: int, batch_size: int) -> str:
        """
        Creates a new entry in the ybs_knowledge_batch_jobs table.
        Returns the UUID of the newly created job.
        """
        query = """
            INSERT INTO public.ybs_knowledge_batch_jobs
                (status, tickets_found, parameters)
            VALUES
                (:status, :tickets_found, :parameters)
            RETURNING id;
        """
        params = {
            "status": "RUNNING",
            "tickets_found": tickets_found,
            "parameters": json.dumps({"batch_size": batch_size})
        }
        result = self.execute(query, params)
        job_id = result[0]['id']
        print(f"Created batch job with ID: {job_id}")
        return job_id

    def update_job_summary(self, job_id: str, status: str, succeeded: int, failed: int, error_summary: Optional[str] = None):
        """
        Updates a job with its final status and statistics upon completion.
        """
        query = """
            UPDATE public.ybs_knowledge_batch_jobs
            SET
                status = :status,
                end_time = CURRENT_TIMESTAMP,
                tickets_succeeded = :succeeded,
                tickets_failed = :failed,
                error_summary = :error_summary
            WHERE id = :job_id;
        """
        params = {
            "job_id": job_id,
            "status": status,
            "succeeded": succeeded,
            "failed": failed,
            "error_summary": error_summary
        }
        self.execute(query, params)
        print(f"Updated batch job {job_id} with status: {status}")

    def log_batch_details(self, job_id: str, log_entries: List[Dict[str, Any]]):
        """
        Performs a bulk insert of detailed processing logs for a batch of tickets.
        """
        if not log_entries:
            return

        query = """
            INSERT INTO public.ybs_knowledge_processing_log
                (job_id, ticket_id, knowledge_base_id, status, duration_ms, error_message)
            VALUES
                (:job_id, :ticket_id, :knowledge_base_id, :status, :duration_ms, :error_message);
        """

        # Add the job_id to each log entry before executing the batch insert
        for entry in log_entries:
            entry['job_id'] = job_id

        self.execute(query, log_entries)
        print(f"Logged details for {len(log_entries)} tickets under job {job_id}.")
