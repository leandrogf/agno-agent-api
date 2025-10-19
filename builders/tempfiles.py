import os
import tempfile

class TempFileManager:
    """
    Gerencia arquivos temporários, cuidando da limpeza adequada.
    """
    def __init__(self):
        self.temp_files = []
        # Usa uma pasta temporária dedicada para nossos arquivos
        self.temp_dir = os.path.join(tempfile.gettempdir(), "agno_temp")
        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir)

    def create_temp_file(self, content, prefix="content_", suffix=".txt"):
        """
        Cria um arquivo temporário com o conteúdo especificado.
        """
        # Cria um nome de arquivo temporário único
        temp_path = os.path.join(self.temp_dir, f"{prefix}{os.urandom(4).hex()}{suffix}")

        # Escreve o conteúdo usando with para garantir o fechamento adequado
        with open(temp_path, 'w', encoding='utf-8') as f:
            f.write(content)

        # Adiciona à lista para limpeza posterior
        self.temp_files.append(temp_path)

        # Retorna o nome do arquivo como URL file://
        return f"file://{temp_path}"

    def cleanup(self):
        """
        Remove todos os arquivos temporários criados.
        """
        for file_path in self.temp_files:
            try:
                if os.path.exists(file_path):
                    os.unlink(file_path)
            except Exception as e:
                print(f"Erro ao remover arquivo temporário {file_path}: {e}")
        self.temp_files = []  # Limpa a lista

    def __del__(self):
        """
        Garante que os arquivos sejam limpos mesmo se o programa for interrompido.
        """
        self.cleanup()
