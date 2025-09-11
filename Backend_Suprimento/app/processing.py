import re
import typing
import unicodedata
from dataclasses import dataclass, field

import pdfplumber
from pdf2image import convert_from_path
from pytesseract import image_to_string


# =========================
# Config
# =========================
OCR_DPI_BODY    = 300
OCR_DPI_HEADER  = 300
OCR_DPI_FOOTER  = 400
HEADER_FRAC     = 0.42   # fração de altura para topo
FOOTER_FRAC     = 0.22   # fração de altura para rodapé
SHORT_TEXT_WORDS = 70    # limiar para decidir OCR de página



# =========================
# Helpers
# =========================
def normalize_spaces(s: str) -> str: #Normalizar espaços em brancos em um string.
    return re.sub(r"\s+", " ", s or "").strip()

def strip_accents(s: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFD', s or '') if unicodedata.category(c) != 'Mn')

def lower_noacc(s: str) -> str:
    return strip_accents((s or '').lower())

def titlecase_nome(s: typing.Optional[str]) -> typing.Optional[str]:
    """
    Coloca apenas a primeira letra de cada palavra em maiúscula.
    Ex.: 'FABYANY WALTENIZY RODRIGUES DA SILVA' -> 'Fabyany Waltenizy Rodrigues Da Silva'
    Mantém hífens corretamente: 'SANTOS-FILHO' -> 'Santos-Filho'
    """
    if not s:
        return s
    s = normalize_spaces(s)
    # aplica capitalização sem perder hífens
    def cap_token(tok: str) -> str:
        return "-".join(p.capitalize() for p in tok.split("-"))
    return " ".join(cap_token(tok) for tok in s.lower().split())

def fix_local_obito_uf(local: typing.Optional[str]) -> typing.Optional[str]:
    """
    Corrige ruído comum de OCR no UF do local do óbito.
    Ex.: 'Teresina-PL' -> 'Teresina-PI'
    Mantém a cidade como veio (não tenta acentuar).
    """
    if not local:
        return local
    s = normalize_spaces(local)
    m = re.match(r"^(.*?)-([A-Za-z]{2})$", s)
    if not m:
        return s
    cidade, uf = m.group(1).strip(), m.group(2).upper()
    if uf == "PL":  # ruído típico do OCR para PI
        uf = "PI"
    return f"{cidade}-{uf}"

# =====================================
# PDF context (abre 1x e faz cache)
# =====================================
# @dataclass
# class PDFContext:
#     pdf_path: str
#     _pdf: pdfplumber.PDF = field(init=False, default=None)
#     pages_text: list[str] = field(init=False, default=None)
#     _img_cache_300:dict[int, "PIL.Image.Image"] = field(init=False, default_factory=dict)
#     _img_cache_400:dict[int, "PIL.Image.Image"] = field(init=False, default_factory=dict)
#     _footer_text_cache: dict[int, str] = field(default_factory=dict, init=False)









def page_needs_ocr(txt: str) -> bool:
    # se não extraiu NADA ou é muito curto, manda para OCR
    return len(normalize_spaces(txt).split()) < 70

def ocr_pages_images (pdf_path:str, page_indices:typing.List[int]) -> dict:
  results = {}
  if not page_indices:
    return results
  first = min(page_indices) + 1
  last  = max(page_indices) + 1

  #Converter as páginas necessárias para imagem
  pages = convert_from_path(pdf_path, dpi=300, first_page=first, last_page=last)

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
    pages_text = []
    with pdfplumber.open(pdf_path) as pdf:
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
    # print("Texto",full_text)
    return full_text, pages_text

# ---------------------------------------------------------------------
# Parsers / Regex
# ------------------------------------------------------------------

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

# Tabela "Documentos" do PJe para encontar o ID do Parecer
# Reconstrói: '71058' + '\n319' => '71058319'
# ------------------------
TIPOS_RE = (
    r"(?:"
    r"Pet[ií]ç[aã]o Inicial|Pet[ií]ç[aã]o|Certid[aã]o|Intima[cç][aã]o|"
    r"Manifesta[cç][aã]o(?:\s+do\s+Minist[eé]rio\s+P[úu]blico)?|"
    r"Parecer(?:\s+do\s+(?:MP|Minist[eé]rio\s+P[úu]blico))?|Parecer|"
    r"Despacho|Sistema|DOCUMENTO COMPROBAT[ÓO]RIO"
    r")"
)
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
         .replace("comprobatorio", "comprobatório")
         .replace("ministerio publico", "ministério público"))
    
    # normalizações para parecer
    if "parecer" in t:
        return "parecer"
    if "manifestação" in t and "ministério público" in t:
        return "parecer"  # tratamos manifestação do MP como “parecer”
    
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
(?P<grau>
    filh[ao]|
    pai|m[ãa]e|
    av[óô]|bisav[óô]|tatarav[óô]|
    net[oa]|bisnet[oa]|irm[ãáa][oã]?|
    ti[oa]|sobrinh[ao]|prim[oa]|
    sogr[oa]|genr[eo]|nora|cunhad[oa]|
    padrasto|madrasta|entead[oa]|
    companheir[ao]|convivent[ea]|
    c[oô]njuge|espos[ao]|marido|mulher|
    vi[uú]v[ao]
    adotiv[ao]|                       
    tutelad[ao]|                      
    tutor|tutora| herdeir[ao]|
    testamenteir[ao]|    inventariante|   representante|   
            respons[aá]vel                     
    )
\s+d[aeo]s?\s+                       # de / do / da / dos / das
(?:falecid[oa]\s+|sr\.?\s+|sra\.?\s+|de\s+cujus\s+)?   # opcional
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

# Fallback tolerante: permite ruído entre o grau e o "de/do/da"
RE_PARENTESCO_FALLBACK = re.compile(
    RE_PARENTESCO + r".{0,10}?d[aeo]s?\s+" + RE_NOME_UPPER,
    re.IGNORECASE | re.VERBOSE | re.DOTALL
)

def extract_parentesco_e_falecido(text: str) -> tuple[typing.Optional[str], typing.Optional[str]]:
    t = normalize_spaces(text)
    for rx in (RE_PARENTESCO_NOME_UPPER, RE_PARENTESCO_NOME_TITLE, RE_PARENTESCO_FALLBACK):
        m = rx.search(t)
        if m:
            grau = m.group("grau").lower()
            nome = m.group("nome").strip()
            return grau, nome
    return None, None

# Local do óbito + Data do óbito (em dd/mm/yyyy)
#Espera texto assim: falecida em Teresina – PI, no dia 07 de outubro de 2022
# =========================
# Local do óbito + Data
# =========================
DASH_CHARS = "-–—"
DASH_CC    = f"[{re.escape(DASH_CHARS)}]"

RE_LOCAL_DATA_EXTENSO = re.compile(rf"""
    (?:falecid[oa]|faleceu)\s+em\s+
    (?P<cidade>[A-ZÀ-Ý][A-Za-zÀ-ÿ\s.'-]+)\s*{DASH_CC}\s*(?P<uf>[A-Z]{{2}})
    \s*,?\s*(?:no\s+)?dia\s+
    (?P<dia>\d{{1,2}})\s+de\s+(?P<mes>janeiro|fevereiro|mar[cç]o|abril|maio|junho|
                               julho|agosto|setembro|outubro|novembro|dezembro)
    \s+de\s+(?P<ano>\d{{4}})
""", re.IGNORECASE | re.VERBOSE)


#Local do Óbito
def extract_local_obito(text: str) -> typing.Optional[str]:
    m = RE_LOCAL_DATA_EXTENSO.search(text)
    if m:
        return f"{normalize_spaces(m.group('cidade'))}-{m.group('uf').upper()}"
    m = re.search(r"local do falecimento[\s,:-]*([^\n\r]+)", text, flags=re.IGNORECASE)
    if m:
        return normalize_spaces(m.group(1))
    cap = rf"([A-Z][A-Za-zÀ-ÿ]+)\s*[{DASH_CC}]\s*([A-Z]{{2}})"
    a = re.search(cap, text)
    return normalize_spaces(a.group(0)) if a else None

#Data do Óbito
DASH_CHARS = "-–—"
DASH_CC    = f"[{re.escape(DASH_CHARS)}]"
RE_DATA_EXTENSO = re.compile(
    r"\b(\d{1,2})\s+de\s+(janeiro|fevereiro|mar[cç]o|abril|maio|junho|"
    r"julho|agosto|setembro|outubro|novembro|dezembro)\s+de\s+(\d{4})\b",
    re.IGNORECASE
)
RE_DATA_NUM = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")
# RE_GATILHO = re.compile(
#     rf"(falecid[oa]|falecimento|faleceu|ó?bito|"
#     rf"[A-ZÀ-Ý][A-Za-zÀ-ÿ\s.'-]+{DASH_CC}\s*[A-Z]{{2}}\s*,?\s*(?:dia\s+)?)",
#     re.IGNORECASE
# )
RE_CAUSA_MORTIS = re.compile(r"causa\s+mortis", re.IGNORECASE)
def extract_data_obito(text: str) -> typing.Optional[str]:
    if not text:
        return None
    m = RE_LOCAL_DATA_EXTENSO.search(text)
    t = re.sub(r"\s+", " ", text)

    if m:
        return to_br_date_from_extenso(m.group('dia'), m.group('mes'), m.group('ano'))
    m = re.search(r"(?:falecimento|faleceu|óbito).{0,40}?\b(\d{1,2}/\d{1,2}/\d{4})\b", text, flags=re.IGNORECASE | re.DOTALL)
    
    # b2) FALLBACK: pegar a última data ANTES de "causa mortis"
    m_anchor = RE_CAUSA_MORTIS.search(t)
    if m_anchor:
        prefix = t[:m_anchor.start()]
        last_ext = None
        for dm in RE_DATA_EXTENSO.finditer(prefix):
            last_ext = dm
        if last_ext:
            dia, mes, ano = last_ext.groups()
            return to_br_date_from_extenso(dia, mes, ano)

        last_num = None
        for nm in RE_DATA_NUM.finditer(prefix):
            last_num = nm
        if last_num:
            d, mn, y = map(int, last_num.groups())
            return f"{d:02d}/{mn:02d}/{y:04d}"
    return to_br_date(m.group(1)) if m else None

# IDs do Parecer (da TABELA)


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

def extract_id_parecer(text: str) -> typing.Optional[str]:
    rows = parse_tabela_documentos(text)
    # candidatos: qualquer linha normalizada para "parecer"
    candidatos = [r for r in rows if r["tipo"] in ("parecer","manifestação")]
    if candidatos:
        return candidatos[-1]["id"]

    # fallback: varrer o texto cru procurando um "Parecer ..." seguido de "Num. 12345 678"
    # m = re.search(
    #     r"(?:parecer|manifesta[cç][aã]o\s+do\s+minist[eé]rio\s+p[úu]blico)[\s\S]{0,120}?"
    #     r"(?:num[ºo.]?\s*)?(\d{5})\s*[\r\n ]+(\d{3})",
    #     text,
    #     flags=re.IGNORECASE,
    # )
    # if m:
    #     return m.group(1) + m.group(2)

    return None
#---------------------------------------------------------------------------------------------------------------------------
# id declaração de óbito 

# Traços aceitos: hífen, en-dash, em-dash
DASH_CHARS = "-–—"
DASH_CC    = f"[{re.escape(DASH_CHARS)}]"

ID_PAG_PAT = re.compile(
    rf"""
    N[úu]m[ºo.]?\s*             # Num / Núm. / N.º
    (?P<num>\d{{6,}})           # 6+ dígitos
    \s*{DASH_CC}\s*             # traço
    P[áa]g[ºo.]?\s*             # Pág / Pag
    (?P<pag>\d+)
    """,
    flags=re.IGNORECASE | re.VERBOSE
)

ID_PAG_FUZZY = re.compile(
    r"N\w{1,2}\W*\s*(\d{6,})\W+\s*P\w{1,2}g\W*\s*(\d+)",
    re.IGNORECASE
)
PALAVRAS_DECL = [
    "Declaração de Óbito","Declaracao de Obito",
    "Ministerio da Saude", "Ministério da Saúde",
    "República Federativa do Brasil",
    "Causas da Morte",
    "Cartório do Registro Civil","Cartorio do Registro Civil"
]

def palavras_encontradas(texto: str) -> list[str]:
    s = (texto or "").lower()
    return [p for p in PALAVRAS_DECL if p.lower() in s]

def tem_palavras_chave(texto: str) -> int:
    return len(palavras_encontradas(texto))

def extrai_id_pag(texto: str) -> typing.Optional[str]:
    m = ID_PAG_PAT.search(texto or "")
    if m:
        return f"Num. {m.group('num')} - Pág. {m.group('pag')}"
    m = ID_PAG_FUZZY.search(texto or "")
    if m:
        return f"Num. {m.group(1)} - Pág. {m.group(2)}"
    return None

def extract_id_declaracao_avancado(pages_text: list[str], pdf_path: str) -> typing.Optional[str]:
    # 1) primeiro, tente achar páginas candidatas por palavras-chave
    # Candidatas: >=2 palavras no texto DA PÁGINA OU no header OCR
    candidatas = []
    for i, pagina in enumerate(pages_text):
        hits = tem_palavras_chave(pagina)
        try:
            head_ocr = ocr_header(pdf_path, i, frac=0.32)
        except Exception:
            head_ocr = ""
        hits_hdr = tem_palavras_chave(head_ocr)
        if (hits + hits_hdr) >= 2:
            candidatas.append(i)
    
    # Fallback: nenhuma candidata → testa todas
    if not candidatas:
        # fallback: tente todas, se por algum motivo a extração do corpo não trouxe as palavras
        candidatas = list(range(len(pages_text)))

    for i in candidatas:
        # (a) tenta no texto "cru" da página
        idp = extrai_id_pag(pages_text[i])
        if idp:
            return idp

        # (b) rodapé (pdfplumber → OCR)
        txt_pdf = pdf_footer_text(pdf_path, i)
        idp = extrai_id_pag(txt_pdf)
        if idp:
            return idp

        rodape = ocr_footer(pdf_path, i, frac=0.28)
        idp = extrai_id_pag(rodape)
        if idp:
            return idp

    return None


#------------------------------------------------------------------------------------------------------
# id certidões negativas
# --- OCR genérico de uma região da página (coordenadas fracionadas) ---
def ocr_region(pdf_path: str, page_index: int, box_frac=(0.0, 0.0, 1.0, 1.0), dpi: int = 400, psm: int = 6) -> str:
    """
    box_frac = (x0, y0, x1, y1) em fração da largura/altura [0..1].
    Ex.: (0, 0, 1, 0.4) = faixa superior; (0, 0.78, 1, 1) = rodapé.
    """

    imgs = convert_from_path(pdf_path, dpi=dpi, first_page=page_index + 1, last_page=page_index + 1)
    if not imgs:
        return ""
    img = imgs[0]
    w, h = img.size
    x0, y0, x1, y1 = box_frac
    box = (int(w*x0), int(h*y0), int(w*x1), int(h*y1))
    crop = img.crop(box)
    cfg = f"--oem 1 --psm {psm}"
    return image_to_string(crop, lang="por", config=cfg) or ""

def ocr_header(pdf_path: str, page_index: int, frac: float = 0.42) -> str:
    # OCR do topo (~42% superior)
    return ocr_region(pdf_path, page_index, (0.0, 0.0, 1.0, frac), dpi=400, psm=6)

def ocr_footer(pdf_path: str, page_index: int, frac: float = 0.22) -> str:
    # OCR do rodapé (~22% inferior)
    return ocr_region(pdf_path, page_index, (0.0, 1.0 - frac, 1.0, 1.0), dpi=400, psm=6)

def pdf_footer_text(pdf_path: str, page_index: int, frac: float = 0.22) -> str:
    """Extrai texto do rodapé usando pdfplumber (quando for texto vetorial)."""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            page = pdf.pages[page_index]
            w, h = page.width, page.height
            bbox = (0, h*(1-frac), w, h)
            clip = page.within_bbox(bbox)
            txt = clip.extract_text(x_tolerance=0.5, y_tolerance=0.5) or ""
            if txt.strip():
                return txt
            words = clip.extract_words(x_tolerance=0.5, y_tolerance=0.5) or []
            return " ".join(wd["text"] for wd in words)
    except Exception:
        return ""




def _ctx(s: str, start: int, end: int, span: int = 40) -> str:
    """Extrai um contexto curto ao redor de um match, para log."""
    a = max(0, start - span)
    b = min(len(s), end + span)
    return s[a:b].replace("\n", " ")


# Positivos
RE_CERT_NEG_TIT = re.compile(r"\bcertidao.{0,40}negativa\b", re.IGNORECASE)  # título ou 'CERTIDÃO ... NEGATIVA'
RE_TABELA_CRCN = re.compile(r"(tipo\s+do\s+registro|nome\s+do\s+falecido|genitor\s*1|genitor\s*2|hash\s+negativa)", re.IGNORECASE)
RE_MARCAS_CRCN = re.compile(r"(crc\s*-?\s*nacional|central\s+de\s+informac(?:oes|ões)\s+do\s+registro\s+civil|www\.registrocivil\.org\.br/validacao)", re.IGNORECASE)
RE_HASH = re.compile(r"hash(?:\s+negativa)?\s*[:\-]?\s*((?:[0-9a-f]{3,8}[.\-]){3,}[0-9a-f]{3,8})", re.IGNORECASE)
RE_CARTORIO = re.compile(r"(serventia\s+extrajudicial|cartorio\s+de\s+registro\s+civil|oficial\s+de\s+registro\s+civil|escrevente)", re.IGNORECASE)
RE_OBITO = re.compile(r"\bobit[oa]\b", re.IGNORECASE)
# Frases de negação (para o modelo “texto corrido”)
RE_NEG = r"(nao\s+(?:foi\s+)?localizad[oa]|nao\s+consta|nada\s+consta|inexistenc\w+|nao\s+figurar)"
RE_CARTORIO_STRONG = re.compile(
    r"(o\s+referido\s+e\s+verdade\s+e?\s*dou\s*fe|"
    r"consulte\s+a\s+autenticidade\s+do\s+selo|"
    r"\bselo\s*:|emolumentos|serventia\s+extrajudicial|"
    r"oficial\s+de\s+registro\s+civil|escrevente)",
    re.IGNORECASE
)


# Negativos/exclusões (evitar nascimento e certidões judiciais)
RE_EXCL_NASC = re.compile(r"certidao\s+de\s+nascimento", re.IGNORECASE)
RE_EXCL_JUD = re.compile(r"(poder\s+judiciario|processo\s*n?[ºo]|classe\s*:|assunto\s*:|requerente\s*:|justica\s+itinerante)", re.IGNORECASE)



def explain_page(text: str) -> dict:
    """
    Avalia todos os sinais na página/trecho e explica o que bateu.
    Retorna um dicionário com flags e trechos (snippets) de cada match.
    """
    t = lower_noacc(text or "")
    out = {
        "exclusions": {},
        "positives": {},
        "neg_obito_window": negacao_perto_de_obito(t),
        "is_cert": False,
        "requirements": {},
    }

     # exclusões
    m = RE_EXCL_NASC.search(t); out["exclusions"]["nascimento"] = _ctx(t, *m.span()) if m else ""
    m = RE_EXCL_JUD.search(t);  out["exclusions"]["judiciario"] = _ctx(t, *m.span()) if m else ""

    # Positivos
    for name, rx in [
        ("titulo_certidao_negativa", RE_CERT_NEG_TIT),
        ("tabela_crcn", RE_TABELA_CRCN),
        ("marcas_crcn", RE_MARCAS_CRCN),
        ("hash", RE_HASH),
        ("cartorio", RE_CARTORIO),
        ("cartorio_strong", RE_CARTORIO_STRONG),

        ("obito", RE_OBITO),

    ]:
        m = rx.search(t)
        out["positives"][name] = _ctx(t, *m.span()) if m else ""

    # >>> DECISÃO: título é OBRIGATÓRIO
    excl          = any(out["exclusions"].values())
    has_title     = bool(RE_CERT_NEG_TIT.search(t))
    has_cartorio  = bool(RE_CARTORIO.search(t) or RE_CARTORIO_STRONG.search(t))
    out["requirements"]["has_title"]    = has_title
    out["requirements"]["has_cartorio"] = has_cartorio

    # Decisão: só aprova com título + cartório e sem exclusões
    out["is_cert"] = (not excl) and has_title and has_cartorio
    return out


def negacao_perto_de_obito(t: str, window: int = 120) -> bool:
    # ...negativa... perto de "óbito" (em qualquer ordem)
    t = lower_noacc(t)
    return (re.search(rf"(?:{RE_NEG}).{{0,{window}}}obit", t) is not None
            or re.search(rf"obit.{{0,{window}}}(?:{RE_NEG})", t) is not None)

def is_certidao_negativa(texto: str) -> bool:
    """
    True se a página é a CERTIDÃO NEGATIVA (não apenas menciona uma).
    REQUISITO: deve haver o título 'CERTIDÃO ... NEGATIVA' no texto analisado.
    """
    t = lower_noacc(texto)

    # Exclusões claras
    if RE_EXCL_NASC.search(t):  # "certidão de nascimento"
        return False
    if RE_EXCL_JUD.search(t):   # cabeçalho de peça judicial
        return False
    # if RE_EXCL_MP.search(t):    # Ministério Público
    #     return False

    # 🚫 sem TÍTULO -> já descarta
    if not RE_CERT_NEG_TIT.search(t):
        return False

    # ✅ Com título, aceitamos. Sinais extras reforçam (não são obrigatórios).
    #    Se quiser endurecer, descomente a linha com 'and RE_OBITO.search(t)'.
    if (RE_TABELA_CRCN.search(t) or RE_MARCAS_CRCN.search(t) or RE_HASH.search(t)):
        return True

    # fallback: título sozinho (útil quando OCR perde outros trechos)
    return True


def parse_id_pag(s: str) -> typing.Optional[tuple[str, str]]:
    if not s:
        return None
    m = ID_PAG_PAT.search(s)
    if m:
        return m.group("num"), m.group("pag")
    m = ID_PAG_FUZZY.search(s)
    if m:
        return m.group(1), m.group(2)
    return None


def find_certidoes_negativas(pdf_path: str, pages_text: list[str], debug: bool = False):
    """
    Retorna:
      - se debug=False (padrão): list[dict] com as ocorrências
      - se debug=True: (resultados, debug_pages)
    """
    resultados = []
    debug_pages = []

    total = len(pages_text)
    with pdfplumber.open(pdf_path) as pdf:
        for i in range(total):
            # --- fontes de texto que vamos avaliar e logar ---
            fontes = []

            full_txt = pages_text[i] or ""
            fontes.append(("full", full_txt, explain_page(full_txt)))

            # topo via pdfplumber
            try:
                page = pdf.pages[i]
                w, h = page.width, page.height
                header_clip = page.within_bbox((0, 0, w, h*0.55))
                txt_head = header_clip.extract_text(x_tolerance=0.5, y_tolerance=0.5) or ""
            except Exception:
                txt_head = ""
            if txt_head:
                fontes.append(("pdf_header", txt_head, explain_page(txt_head)))

            # OCR do topo se ainda não “decidiu”
            decided = any(info["is_cert"] for _, _, info in fontes)
            if not decided:
                ocr_head = ocr_header(pdf_path, i, frac=0.55)
                if ocr_head:
                    fontes.append(("ocr_header", ocr_head, explain_page(ocr_head)))
                    decided = any(info["is_cert"] for _, _, info in fontes)

            # Escolha final: tem alguma fonte marcando como certidão?
            eh_cert = decided
            chosen_src = next((src for src, _, info in fontes if info["is_cert"]), None)

            # Debug de decisão da página
            if debug:
                debug_pages.append({
                    "page": i + 1,
                    "sources": [
                        {
                            "src": src,
                            "is_cert": info["is_cert"],
                            "exclusions": info["exclusions"],
                            "positives": info["positives"],
                            "neg_obito_window": info["neg_obito_window"],
                        }
                        for (src, _txt, info) in fontes
                    ],
                    "chosen_src": chosen_src,
                })

            if not eh_cert:
                continue

            # --- rodapé: pdfplumber → OCR → vizinhos ---
            id_source = None
            rodape_txt = pdf_footer_text(pdf_path, i)
            par = parse_id_pag(rodape_txt)
            if par:
                id_source = "pdf_footer"
            else:
                rodape_ocr = ocr_footer(pdf_path, i, frac=0.28)
                par = parse_id_pag(rodape_ocr)
                if par:
                    id_source = "ocr_footer"

            if not par:
                for j in (i-1, i+1):
                    if 0 <= j < total:
                        par = parse_id_pag(pdf_footer_text(pdf_path, j))
                        if par:
                            id_source = f"neighbor_pdf_footer(p{j+1})"
                            break
                        par = parse_id_pag(ocr_footer(pdf_path, j, frac=0.28))
                        if par:
                            id_source = f"neighbor_ocr_footer(p{j+1})"
                            break

            if par:
                num, pag = par
                resultados.append({
                    "pdf_page": i + 1,
                    "num": num,
                    "pag": int(pag),
                    "rodape": f"Num. {num} - Pág. {pag}",
                    "id_source": id_source,
                    "chosen_src": chosen_src,   # de onde veio a “certeza” da página
                })
            elif debug:
                # registramos que a página foi classificada como certidão, mas não achou ID
                debug_pages[-1]["id_error"] = "Rodapé não identificado (pdf/ocr/vizinhos)."

    # ordenação opcional
    # resultados.sort(key=lambda r: (r["num"], r["pag"]))

    if debug:
        return resultados, debug_pages
    return resultados







CAMPOS_ORDEM = [
    "numero_processo","requerente","parentesco","nome_falecido",
    "local_obito","data","id_parecer","id_declaracao","id_certidoes"
]

def montar_resultado(full_text: str, pages_text: list[str],pdf_path:str) -> dict:
    par, fal = extract_parentesco_e_falecido(full_text)
    #encontrar todas as certidões negativas
    # valores brutos
    req_raw = extract_requerente(full_text)
    fal_raw = fal
    loc_raw = extract_local_obito(full_text)

    # pós-processamentos pedidos
    requerente_fmt   = titlecase_nome(req_raw)
    nome_falecido_fmt = titlecase_nome(fal_raw)
    local_fmt        = fix_local_obito_uf(loc_raw)
   

    resultado = {
        "numero_processo": extract_numero_processo(full_text),
        "requerente":      requerente_fmt,
        "parentesco":      par,
        "nome_falecido":   nome_falecido_fmt,
        "local_obito":     local_fmt,
        "data":            extract_data_obito(full_text),
        "id_parecer":      extract_id_parecer(full_text),
        "id_declaracao":   extract_id_declaracao_avancado(pages_text,pdf_path),
        "id_certidoes":    find_certidoes_negativas(pdf_path, pages_text),
    }
    print("Resultado extraído:", resultado)
    return resultado

#---------------------------------------------------------------------------------------------------------------------------


# -------------------------
# Função para ler o arquivo PDF e retornar os dados extraídos
# -------------------------
def process_pdf(pdf_path: str) -> dict:
    full_text, pages_text = extract_text_with_pdfplumber(pdf_path)
    # for i, t in enumerate(pages_text, 1):
    #         raw = t or ""
    #         words = len(normalize_spaces(raw).split())
    #         print("\n" + "="*80)
    #         print(f"[PAGE {i}] chars={len(raw)}  words={words}")
    #         print("-"*80)
    #         print(raw if raw.strip() else "<<vazio>>")   
    resultado = montar_resultado(full_text, pages_text,pdf_path)
    # com debug (retorna também explicações)
    certs, dbg = find_certidoes_negativas(pdf_path, pages_text, debug=True)
    for d in dbg:
        print(f"[CN-DEBUG] pág={d['page']}, chosen_src={d['chosen_src']}")
        for s in d["sources"]:
            if s["is_cert"]:
                print("  - fonte:", s["src"])
                print("    exclusões:", {k: bool(v) for k,v in s["exclusions"].items()})
                print("    positivos:", {k: bool(v) for k,v in s["positives"].items()})
                print("    neg_obito_window:", s["neg_obito_window"])
    

    return {
        "resultado": resultado,
    }