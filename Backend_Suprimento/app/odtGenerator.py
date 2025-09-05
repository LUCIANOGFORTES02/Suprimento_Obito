import os
import tempfile
import re
from odf.opendocument import load
from odf.text import P, Span
from typing import Dict, Any
from odf import teletype
from odf.text import P, H, ListItem
from odf.table import TableCell
# -------------------------
# Função para gerar o documento ODT a partir do template e dos dados extraídos
# -------------------------

class ODTGenerator:

    def __init__(self):
        self.template_path = "app/templates/sentenca_template.odt"
    
    def generate_from_template(self, resultado: Dict[str, Any], output_path: str = None) -> str:
        try:
            print(f"🔍 Dados recebidos para substituição: {resultado}")
            numero_processo = resultado.get("numero_processo")
            if not numero_processo:
                raise ValueError("numero_processo é obrigatório para gerar nome do arquivo")
            # Defina output_path logo no início
            if output_path is None:
                output_path = f"/tmp/sentenca_{numero_processo}.odt"
                print(f"📁 Output path definido como: {output_path}")    
            # Verifique se o template existe
            if not os.path.exists(self.template_path):
                raise FileNotFoundError(f"Template não encontrado: {self.template_path}")
            print(f"🔍 Dados recebidos para substituição: {resultado}")
            
            print(f"📁 Carregando template de: {self.template_path}")
        
            # Carrega o template
            doc = load(self.template_path)
            print("✅ Template carregado com sucesso")
            
            # Extrai texto para debug
            full_text = teletype.extractText(doc.text) or ""
            print(f"📄 Prévia do texto ({len(full_text)} chars): {full_text[:200]}...")


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
            print(f"🎯 Mapeamento a aplicar: {mapeamento}")

            # Verifica quais placeholders existem no documento
            print("🔍 Procurando placeholders no template:")
            for placeholder, value in mapeamento.items():
                if placeholder in full_text:
                    print(f"   ✅ {placeholder} - ENCONTRADO")
                else:
                    print(f"   ⚠️  {placeholder} - NÃO ENCONTRADO")

           # Substitui placeholders
            print("🔄 Iniciando substituição de placeholders...")
            self.replace_placeholders_hybrid(doc, mapeamento)
            print("✅ Substituição concluída")
            print(f"Documento preenchido: {doc.text}")

            

           # Verifica o resultado
            new_text = teletype.extractText(doc.text) or ""
            print(f"📄 Texto após substituição ({len(new_text)} chars): {new_text[:200]}...")

            
            print(f"💾 Salvando documento em: {output_path}")
            doc.save(output_path)
                    # Verifica se o arquivo foi criado
            if output_path and os.path.exists(output_path):
                print(f"✅ Documento salvo com sucesso: {output_path}")
                return output_path
            else:
                raise Exception(f"Falha ao salvar documento em: {output_path}")
        except Exception as e:
            print(f"❌ ERRO DETALHADO em generate_from_template: {str(e)}")
            print(f"❌ Tipo do erro: {type(e).__name__}")
            import traceback
            print(f"❌ Stack trace: {traceback.format_exc()}")
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
    
    def replace_placeholders_hybrid(self, doc, replacements: Dict[str, str]):
        """
        Método híbrido: usa abordagem inteligente para manter formatação
        """
        print("🔧 Usando método híbrido de substituição...")
        
        # Primeiro, tenta substituir nos elementos de texto simples
        for element in doc.getElementsByType(P):
            self._replace_in_element_smart(element, replacements)
        
        for element in doc.getElementsByType(H):
            self._replace_in_element_smart(element, replacements)
        
        # Depois, procura em spans e outros elementos formatados
        for element in doc.getElementsByType(Span):
            self._replace_in_element_smart(element, replacements)

    def _replace_in_element_smart(self, element, replacements):
        """
        Substituição inteligente que preserva a estrutura do elemento
        """
        if hasattr(element, 'data') and element.data:
            # Elemento com texto direto
            original = element.data
            new_text = original
            
            for placeholder, value in replacements.items():
                if placeholder in new_text:
                    new_text = new_text.replace(placeholder, value)
            
            if new_text != original:
                element.data = new_text
        
        # Processa filhos recursivamente (para elementos complexos)
        if hasattr(element, 'childNodes'):
            for child in element.childNodes:
                self._replace_in_element_smart(child, replacements)