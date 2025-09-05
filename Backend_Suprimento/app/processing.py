import io
import os
import re
import json
import typing
import pdfplumber
from datetime import datetime
from collections import OrderedDict

import pytesseract
from pytesseract import image_to_string
from pdf2image import convert_from_path

from odf.opendocument import OpenDocumentText
from odf.text import P


# -------------------------
# Helpers
# -------------------------
def normalize_spaces(s: str) -> str: #Normalizar espaços em brancos em um string.
    return re.sub(r"\s+", " ", s or "").strip()

def page_needs_ocr(txt: str) -> bool:
    # se não extraiu NADA ou é muito curto, manda para OCR
    return len(normalize_spaces(txt).split()) < 70

def ocr_pages_images (pdf_path:str, page_indices:typing.List[int]) -> dict:
  results = {}

  #Converter as páginas necessárias para imagem
  pages = convert_from_path(pdf_path, dpi=300, first_page=min(page_indices)+1, last_page=max(page_indices)+1)

  start = min (page_indices)
  for offset, img in enumerate(pages):
    index= start + offset
    if index in page_indices:
      text = image_to_string(img, lang='por') or ""
      results[index] = text
  return results


# -------------------------
# Extração texto (pdfplumber + OCR seletivo)
# -------------------------
def extract_text_with_pdfplumber(pdf_path: str) -> tuple[str, list[str]]:
    pdf = pdfplumber.open(pdf_path)
    pages_text = []
    for i,page in enumerate(pdf.pages):
        text = page.extract_text()
        pages_text.append(text)
    
    # identifica páginas candidatas a OCR
    ocr_candidates = [i for i, t in enumerate(pages_text) if page_needs_ocr(t)]

    ocr_texts = ocr_pages_images(pdf_path, ocr_candidates)
    #Substitui texto vazio por OCR
    for index, ocr_t in ocr_texts.items():
        if len(normalize_spaces(pages_text[index]).split()) <70 and len (normalize_spaces(ocr_t)) > 0:
            pages_text[index] = ocr_t

    full_text = "\n\n".join(pages_text)
    print("Texto",full_text)
    return full_text, pages_text


# -------------------------
# Parsers / Regex
# -------------------------

MESES = {
    "janeiro": "01", "fevereiro": "02", "março": "03", "marco": "03", "abril": "04", "maio": "05", "junho": "06",
    "julho": "07", "agosto": "08", "setembro": "09", "outubro": "10", "novembro": "11", "dezembro": "12"
}

def to_br_date_from_extenso(dia: str, mes: str, ano: str) -> str:
    #Converte (dd, 'janeiro', '2024') -> 'dd/mm/yyyy'
    mm = MESES[mes.lower()]
    return f"{int(dia):02d}/{mm}/{int(ano):04d}"

def to_br_date(text: str) -> typing.Optional[str]:
    if not text:
        return None
    s = normalize_spaces(text)
 # 1) dd/mm/yyyy
    m = re.search(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", s)
    if m:
        d, mth, y = m.groups()
        return f"{int(d):02d}/{int(mth):02d}/{int(y):04d}"
   # 2) yyyy-mm-dd
    m = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", s)
    if m:
        y, mth, d = m.groups()
        return f"{int(d):02d}/{int(mth):02d}/{int(y):04d}"
   # 3) '17 de janeiro de 2024'
    m = re.search(
        r"\b(\d{1,2})\s+de\s+(janeiro|fevereiro|março|marco|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)\s+de\s+(\d{4})\b",
        s, flags=re.IGNORECASE
    )
    if m:
        d, mes, y = m.groups()
        return to_br_date_from_extenso(d, mes, y)

    return None

# Número do processo (CNJ)
CNJ_REGEX = re.compile(r"\b\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}\b")
def extract_numero_processo(text: str) -> typing.Optional[str]:
    m = CNJ_REGEX.search(text)
    return m.group(0) if m else None

# Tabela "Documentos" do PJe
# Reconstrói: '71058' + '\n319' => '71058319'
# ------------------------
TIPOS_RE = r"(?:Pet[ií]ç[aã]o Inicial|Pet[ií]ç[aã]o|Certid[aã]o|Intima[cç][aã]o|Manifesta[cç][aã]o|Despacho|Sistema|DOCUMENTO COMPROBAT[ÓO]RIO)"
ROW_RE = re.compile(
    rf"^\s*(?P<id5>\d{{5}})\s+(?P<data>\d{{2}}/\d{{2}}/\d{{4}})\s+(?P<hora>\d{{2}}:\d{{2}})\s+(?P<doc>.*?)\s+(?P<tipo>{TIPOS_RE})\s*$",
    flags=re.IGNORECASE
)
SUF_RE = re.compile(r"^\s*(?P<suf>\d{3})\s*$")


def norm_tipo(t: str) -> str:
    t = t.strip().lower()
    # normaliza acentos que a extração às vezes perde
    t = (t
         .replace("peticao", "petição")
         .replace("certidao", "certidão")
         .replace("intimacao", "intimação")
         .replace("manifestacao", "manifestação")
         .replace("comprobatorio", "comprobatório"))
    mapa = {
        "petição inicial": "petição inicial",
        "petição": "petição",
        "certidão": "certidão",
        "intimação": "intimação",
        "manifestação": "manifestação",
        "despacho": "despacho",
        "sistema": "sistema",
        "documento comprobatório": "documento comprobatório",
    }
    return mapa.get(t, t)

def parse_tabela_documentos(text: str) -> list[dict]:
    rows = []
    lines = [l for l in (line for line in text.splitlines())]
    i = 0
    while i < len(lines):
        line = normalize_spaces(lines[i])
        m = ROW_RE.match(line)
        if m:
            id5   = m.group("id5")
            data  = m.group("data")
            hora  = m.group("hora")
            doc   = normalize_spaces(m.group("doc"))
            tipo  = norm_tipo(m.group("tipo"))
            suf = None
            # olha a próxima linha: se for só 3 dígitos, é o sufixo do ID
            if i + 1 < len(lines):
                nxt = normalize_spaces(lines[i + 1])
                m2 = SUF_RE.match(nxt)
                if m2:
                    suf = m2.group("suf")
                    i += 1
            full_id = id5 + (suf or "")
            rows.append({"id": full_id, "data": data, "hora": hora, "documento": doc, "tipo": tipo})
        i += 1
    return rows

# Requerente
def extract_requerente(text: str) -> typing.Optional[str]:
    m = re.search(r"(?im)^\s*REQUERENTE\s*[:\-]\s*(.+)$", text)
    if m:
        return normalize_spaces(m.group(1))
    m = re.search(r"REQUERENTE\s*[:\-]\s*(.+)", text, flags=re.IGNORECASE)
    return normalize_spaces(m.group(1)) if m else None

# Parentesco + Nome do falecido 
RE_PARENTESCO = r"""
(?:\b(?:é\s+)?(?:a|o)?\s*)?
(?P<grau>filh[ao]|sobrinh[ao]|irm[ãa]o|viúv[ao]|genr[eo]|nora|cunhad[oa]|padrasto|madrasta|entead[oa]|net[oa])
\s+d[eo]s?\s+
"""
RE_NOME_UPPER = r"""
(?P<nome>
  (?:[A-ZÁÉÍÓÚÂÊÔÃÕÇ]{2,}|DA|DE|DO|DAS|DOS|E)
  (?:\s+(?:[A-ZÁÉÍÓÚÂÊÔÃÕÇ]{2,}|DA|DE|DO|DAS|DOS|E))+
)
"""
RE_NOME_TITLE = r"""
(?P<nome>
  (?:[A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç]+|da|de|do|das|dos|e)
  (?:\s+(?:[A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç]+|da|de|do|das|dos|e))+
)
"""
RE_PARENTESCO_NOME_UPPER = re.compile(RE_PARENTESCO + RE_NOME_UPPER, flags=re.IGNORECASE | re.VERBOSE)
RE_PARENTESCO_NOME_TITLE = re.compile(RE_PARENTESCO + RE_NOME_TITLE, flags=re.IGNORECASE | re.VERBOSE)

def extract_parentesco_e_falecido(text: str) -> tuple[typing.Optional[str], typing.Optional[str]]:
    m = RE_PARENTESCO_NOME_UPPER.search(text)
    if m:
        return m.group("grau").lower(), normalize_spaces(m.group("nome"))
    m = RE_PARENTESCO_NOME_TITLE.search(text)
    if m:
        return m.group("grau").lower(), normalize_spaces(m.group("nome"))
    return None, None

# Local do óbito + Data do óbito (em dd/mm/yyyy)
DASHES = "\u2014\u2013\---"
RE_LOCAL_DATA_EXTENSO = re.compile(rf"""
    falecid[oa]\s+em\s+
    (?P<cidade>[A-ZÀ-Ý][A-Za-zÀ-ÿ\s.'-]+)\s*[{DASHES}]\s*(?P<uf>[A-Z]{{2}})
    \s*,?\s*(?:no\s+)?dia\s+
    (?P<dia>\d{{1,2}})\s+de\s+(?P<mes>janeiro|fevereiro|março|marco|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)
    \s+de\s+(?P<ano>\d{{4}})
""", flags=re.IGNORECASE | re.VERBOSE)

#Local do Óbito
def extract_local_obito(text: str) -> typing.Optional[str]:
    m = RE_LOCAL_DATA_EXTENSO.search(text)
    if m:
        return f"{normalize_spaces(m.group('cidade'))}-{m.group('uf').upper()}"
    m = re.search(r"local do falecimento[\s,:-]*([^\n\r]+)", text, flags=re.IGNORECASE)
    if m:
        return normalize_spaces(m.group(1))
    cap = rf"([A-Z][A-Za-zÀ-ÿ]+)\s*[{DASHES}]\s*([A-Z]{{2}})"
    a = re.search(cap, text)
    return normalize_spaces(a.group(0)) if a else None

#Data do Óbito
def extract_data_obito(text: str) -> typing.Optional[str]:
    m = RE_LOCAL_DATA_EXTENSO.search(text)
    if m:
        return to_br_date_from_extenso(m.group('dia'), m.group('mes'), m.group('ano'))
    m = re.search(r"(?:falecimento|faleceu|óbito).{0,40}?\b(\d{1,2}/\d{1,2}/\d{4})\b", text, flags=re.IGNORECASE | re.DOTALL)
    if m:
        return to_br_date(m.group(1))
    m = re.search(r"\b(\d{1,2}/\d{1,2}/\d{4})\b", text)
    return to_br_date(m.group(1)) if m else None

# IDs do Parecer e das Certidões (da TABELA)
def extract_id_parecer(text: str) -> typing.Optional[str]:
    rows = parse_tabela_documentos(text)
    for r in rows:
        if r["tipo"] == "manifestação":
            return r["id"]
    m = re.search(r"Manifesta[cç][aã]o[\s\S]{0,80}?Num\.\s*(\d+)", text, flags=re.IGNORECASE)
    return m.group(1) if m else None

def extract_id_declaracao_avancado(pages_text: list[str]) -> typing.Optional[str]:
    palavras_chave_obrigatorias = [
        "Declaração de Óbito",
        "Ministério da Saúde",
        "República Federativa do Brasil",
        "Causas da Morte",
        "Cartório do Registro Civil"
    ]
    for i, pagina_text in enumerate(pages_text):
        pagina_num = i + 1
        palavras_encontradas = []

        for palavra in palavras_chave_obrigatorias:
            if palavra.lower() in pagina_text.lower():
                palavras_encontradas.append(palavra)



        print(f"Página {pagina_num}: {len(palavras_encontradas)} palavras-chave encontradas")

        if len(palavras_encontradas) >= 2:
            print(f"⭐ Página {pagina_num} identificada como Declaração de Óbito!")
            print(f"Palavras-chave: {palavras_encontradas}")
            # REGEX MELHORADO - busca padrões mais flexíveis
            patterns = [
                r"Num\.\s*(\d+)\s*[---]\s*Pág\.?\s*(\d+)",  # Padrão principal
                r"Num\.\s*(\d+).*?Pág\.?\s*(\d+)",          # Mais flexível
                r"Num[\.\s]*(\d+)[\s\-]*Pág[\.\s]*(\d+)",    # Menos restritivo
                r"Num[^\d]*(\d+)[^\d]*Pág[^\d]*(\d+)"        # Qualquer separador
            ]

            for pattern in patterns:
                matches = re.findall(pattern, pagina_text, re.IGNORECASE | re.DOTALL)
                print(f"Padrão '{pattern}': {matches}")

                if matches:
                    return f"Num. {matches[0][0]} - Pág. {matches[0][1]}"
    return None

def extract_ids_certidoes(text: str) -> list[str]:
    rows = parse_tabela_documentos(text)
    ids = [r["id"] for r in rows if r["tipo"] == "certidão"]
    if ids:
        return ids
    out = set()
    for m in re.finditer(r"Certid[aã]o[\s\S]{0,80}?Num\.\s*(\d+)", text, flags=re.IGNORECASE):
        out.add(m.group(1))
    for m in re.finditer(r"Certid[aã]o[\s\S]{0,80}?(\d{6,})", text, flags=re.IGNORECASE):
        out.add(m.group(1))
    return sorted(out)

CAMPOS_ORDEM = [
    "numero_processo","requerente","parentesco","nome_falecido",
    "local_obito","data","id_parecer","id_declaracao","id_certidoes"
]

def montar_resultado(full_text: str, pages_text: list[str]) -> dict:
    par, fal = extract_parentesco_e_falecido(full_text)
    resultado = {
        "numero_processo": extract_numero_processo(full_text),
        "requerente":      extract_requerente(full_text),
        "parentesco":      par,
        "nome_falecido":   fal,
        "local_obito":     extract_local_obito(full_text),
        "data":            extract_data_obito(full_text),
        "id_parecer":      extract_id_parecer(full_text),
        "id_declaracao":   extract_id_declaracao_avancado(pages_text),
        "id_certidoes":    extract_ids_certidoes(full_text),
    }
    print("Resultado extraído:", resultado)
    return resultado

#---------------------------------------------------------------------------------------------------------------------------


# -------------------------
# Função para ler o arquivo PDF e retornar os dados extraídos
# -------------------------
def process_pdf(pdf_path: str) -> dict:
    full_text, pages_text = extract_text_with_pdfplumber(pdf_path)
    resultado = montar_resultado(full_text, pages_text)

    return {
        "resultado": resultado,
    }