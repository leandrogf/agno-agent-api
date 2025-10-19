# agent-api/repositories/log_repository.py

from .base_repository import BaseRepository
from typing import List, Dict, Any, Optional
import json

JOB_TYPE_VECTORIZATION = 'vectorization'
JOB_TYPE_KNOWLEDGE = 'knowledge'

class LogRepository(BaseRepository):
    """
    Repository for managing knowledge processing jobs and detailed logs.
    """
    def create_job(self, tickets_found: int, batch_size: int, job_type: str = JOB_TYPE_KNOWLEDGE) -> str:
        """
        Creates a new entry in the ybs_knowledge_batch_jobs table.
        Returns the UUID of the newly created job.

        Args:
            tickets_found (int): Number of tickets found to process
            batch_size (int): Size of each batch
            job_type (str): Type of job - 'knowledge' or 'vectorization'
        """
        # Validação de parâmetros
        if job_type not in (JOB_TYPE_KNOWLEDGE, JOB_TYPE_VECTORIZATION):
            raise ValueError(f"Invalid job_type. Must be one of: {JOB_TYPE_KNOWLEDGE}, {JOB_TYPE_VECTORIZATION}")

        query = """
            INSERT INTO public.ybs_knowledge_batch_jobs
                (status, tickets_found, parameters, job_type)
            VALUES
                (:status, :tickets_found, :parameters, :job_type)
            RETURNING id;
        """
        params = {
            "status": "RUNNING",
            "tickets_found": tickets_found,
            "parameters": json.dumps({"batch_size": batch_size}),
            "job_type": job_type
        }
        result = self.execute(query, params)
        job_id = result[0]['id']
        print(f"Created batch job with ID: {job_id}")
        return job_id

    def update_job_summary(self, job_id: str, status: str, succeeded: int, failed: int, error_summary: Optional[str] = None):
        """
        Updates a job with its final status and statistics upon completion.

        Args:
            job_id (str): UUID of the job
            status (str): Status to set (e.g. 'COMPLETED', 'FAILED', etc)
            succeeded (int): Number of successfully processed tickets
            failed (int): Number of failed tickets
            error_summary (str, optional): Summary of any errors encountered
        """
        # Validação básica dos parâmetros
        if not job_id:
            raise ValueError("job_id must be provided")
        if status not in ('COMPLETED', 'FAILED'):
            raise ValueError("status must be 'COMPLETED' or 'FAILED'")
        if succeeded < 0 or failed < 0:
            raise ValueError("succeeded and failed must be non-negative")

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

        Args:
            job_id (str): UUID of the job
            log_entries (List[Dict]): List of log entries to insert
        """
        if not log_entries:
            return

        # Validação básica
        if not job_id:
            raise ValueError("job_id must be provided")

        # Validação de estrutura dos log entries
        required_fields = {'ticket_id', 'status', 'duration_ms'}
        for entry in log_entries:
            missing_fields = required_fields - set(entry.keys())
            if missing_fields:
                raise ValueError(f"Log entry missing required fields: {missing_fields}")

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
