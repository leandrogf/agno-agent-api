# agent-api/repositories/base_repository.py

import os
from sqlalchemy import create_engine, text, exc
from typing import List, Dict, Any, Optional

class BaseRepository:
    """
    Classe base para todos os repositórios. Gerencia a conexão com o banco de dados
    e fornece um método de execução genérico.
    """
    _engine = None

    def __init__(self):
        if BaseRepository._engine is None:
            db_url = os.getenv("DATABASE_URL")
            if not db_url:
                raise ConnectionError("A variável de ambiente DATABASE_URL não foi configurada.")

            sqlalchemy_url = db_url.replace("postgresql+psycopg2", "postgresql")
            BaseRepository._engine = create_engine(sqlalchemy_url)
        self.engine = BaseRepository._engine

    def execute(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Executa uma query SQL e retorna os resultados como uma lista de dicionários.
        Args:
            query: A string da query SQL a ser executada.
            params: Um dicionário de parâmetros para a query.
        Returns:
            Uma lista de dicionários, onde cada dicionário representa uma linha do resultado.
        """
        try:
            with self.engine.connect() as connection:
                # Inicia uma transação para garantir consistência
                with connection.begin() as transaction:
                    result = connection.execute(text(query), params or {})
                    # Se a query for um SELECT, ela terá a descrição das colunas
                    if result.returns_rows:
                        # Converte o resultado em uma lista de dicionários
                        return [dict(row._mapping) for row in result]
                    # Se for INSERT/UPDATE/DELETE, não retorna linhas, então retorna lista vazia
                    return []
        except exc.SQLAlchemyError as e:
            print(f"ERRO DE BANCO DE DADOS ao executar query: {e}")
            # Em caso de erro, propaga a exceção para que a camada superior possa tratá-la
            raise
