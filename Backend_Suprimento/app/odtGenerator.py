import os
import tempfile
import re
from odf.opendocument import load
from odf.text import P, Span
from typing import Dict, Any
# -------------------------
# Função para gerar o documento ODT a partir do template e dos dados extraídos
# -------------------------

class ODTGenerator:

    def __init__(self, template_path: str = None):
            self.template_path = template_path or "/app/templates/sentenca_template.odt"

    def generate_from_template(self, resultado: Dict[str, Any], output_path: str = None) -> str:
        try:
            #Carrega o template
            doc=load(self.template_path)

            mapeamento = {
                "<<NÚMERO DO PROCESSO>>": resultado.get("numero_processo", ""),
                "<<REQUERENTE>>":         resultado.get("requerente", ""),
                "<<PARENTESCO>>":         resultado.get("parentesco", ""),
                "<<NOME DO FALECIDO>>":   resultado.get("nome_falecido", ""),
                "<<LOCAL DO ÓBITO>>":     resultado.get("local_obito", ""),
                "<<DATA>>":               resultado.get("data", ""),
                "<<ID DO PARECER>>":      resultado.get("id_parecer", ""),
                "<<ID DA DECLARAÇÃO DE ÓBITO>>": resultado.get("id_declaracao", ""),
                "<<ID DAS CERTIDÕES>>":   ", ".join(resultado.get("id_certidoes", [""])),
            }

            # Substitui placeholders em todo o documento
            self._replace_placeholders(doc, mapeamento)

            # Salva o documento
            if not output_path:
                output_path = f"/tmp/sentenca_{resultado.get('numero_processo', 'documento')}.odt"

            doc.save(output_path)
            return output_path
        except Exception as e:
            print(f"Erro ao gerar ODT from template{e}")
            raise




    def create_download_response(self, file_path: str, filename: str = None):
        """
        Prepara resposta para download do arquivo
        """
        if not filename:
            filename = os.path.basename(file_path)
        
        return {
            "file_path": file_path,
            "filename": filename,
            "download_url": f"/download/{filename}"
        }
    def replace_placeholders(self, doc, replacements: Dict[str, str]):
        def process_element(element):
            if hasattr(element, 'childNodes'):
                for child in element.childNodes:
                    if hasattr(child, 'data') and child.data:
                        # Substitui placeholders no texto
                        original_text = child.data
                        for placeholder, value in replacements.items():
                            if placeholder in original_text:
                                child.data = original_text.replace(placeholder, value)
                    else:
                        process_element(child)
        
        
        # Processa todo o conteúdo do documento
        process_element(doc.text)