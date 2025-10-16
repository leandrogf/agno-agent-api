# agent-api/repositories/base_repository.py

import os
from sqlalchemy import create_engine, text, exc
from typing import List, Dict, Any, Optional

class BaseRepository:
    """
    Classe base para todos os repositórios. Gerencia a conexão com o banco de dados
    e fornece um método de execução genérico.

    Esta versão constrói a string de conexão dinamicamente para garantir que
    se conecte ao banco de dados do Directus (directus_db), e não ao do Agno (agno_db).
    """
    _engine = None

    def __init__(self):
        if BaseRepository._engine is None:
            # --- LÓGICA DE CONEXÃO CORRIGIDA ---
            # Busca as credenciais e o nome do banco do Directus do ambiente
            db_user = os.getenv("POSTGRES_USER")
            db_password = os.getenv("POSTGRES_PASSWORD")
            db_name = os.getenv("POSTGRES_DB")  # A variável que aponta para 'directus_db'

            # O nome do host é o nome do serviço Docker, e a porta é a interna do contêiner
            db_host = "postgres-senar"
            db_port = "5432"

            # Validação para garantir que todas as variáveis necessárias estão presentes
            if not all([db_user, db_password, db_name]):
                raise ConnectionError(
                    "As variáveis de ambiente para o banco de dados (POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB) não estão configuradas."
                )

            # Constrói a URL de conexão do SQLAlchemy para o banco de dados correto
            sqlalchemy_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

            print(f"BaseRepository: Initializing connection to -> postgresql://{db_user}:****@{db_host}:{db_port}/{db_name}")

            BaseRepository._engine = create_engine(sqlalchemy_url)

        self.engine = BaseRepository._engine

    def execute(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Executa uma query SQL e retorna os resultados como uma lista de dicionários.
        """
        try:
            with self.engine.connect() as connection:
                with connection.begin() as transaction:
                    result = connection.execute(text(query), params or {})
                    if result.returns_rows:
                        return [dict(row._mapping) for row in result]
                    return []
        except exc.SQLAlchemyError as e:
            print(f"DATABASE ERROR executing query: {e}")
            raise
