import os
import tempfile
import atexit
import pathlib

# Diretório base da aplicação
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMP_DIR = os.path.join(BASE_DIR, '__TEMP__', 'vectorization')

class TempFileManager:
    """
    Gerencia a criação e limpeza de arquivos temporários.
    """
    def __init__(self):
        """
        Inicializa o gerenciador, criando o diretório temporário se necessário.
        """
        pathlib.Path(TEMP_DIR).mkdir(parents=True, exist_ok=True)
        self.created_files = []
        atexit.register(self.cleanup)

    def create_temp_file(self, content: str) -> str:
        """
        Cria um arquivo temporário com o conteúdo fornecido.
        Retorna o caminho do arquivo.
        """
        # Cria arquivo temporário no diretório específico
        temp_fd, temp_path = tempfile.mkstemp(prefix="content_", suffix=".txt", dir=TEMP_DIR)

        # Escreve o conteúdo e fecha o descritor de arquivo
        try:
            with open(temp_fd, 'w', encoding='utf-8') as f:
                f.write(content)
        finally:
            os.close(temp_fd)  # Garante que o descritor de arquivo seja fechado

        # Registra para limpeza
        self.created_files.append(temp_path)

        print(f"INFO Arquivo temporário criado: {temp_path}")
        return temp_path

    def cleanup(self):
        """
        Remove todos os arquivos temporários criados.
        """
        for file_path in self.created_files:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                print(f"Erro ao remover arquivo temporário {file_path}: {e}")

        # Tenta remover o diretório se estiver vazio
        try:
            if os.path.exists(TEMP_DIR):
                os.rmdir(TEMP_DIR)
        except OSError:
            # O diretório pode não estar vazio, isso é ok
            pass
