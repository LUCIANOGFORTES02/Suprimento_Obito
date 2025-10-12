import re
import typing
import unicodedata
from dataclasses import dataclass, field
from PIL import Image


import pdfplumber
from pdf2image import convert_from_path
from pytesseract import image_to_string
import logging, traceback



# =========================
# Config
# =========================
OCR_DPI_BODY    = 220
OCR_DPI_HEADER  = 220
OCR_DPI_FOOTER  = 220
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
@dataclass
class PDFContext:
    pdf_path: str
    _pdf: pdfplumber.PDF = field(init=False)
    pages_text: list[str] = field(init=False)
    _img_cache:dict[int, "Image.Image"] = field(init=False, default_factory=dict)
    _footer_text_cache: dict[int, str] = field(default_factory=dict, init=False)

    #Abre o PDF com pdfplumber e extrai o texto vetorial de todas as páginas para pages_text.
    def __post_init__(self):
        self.pdf = pdfplumber.open(self.pdf_path)
        self.pages_text = []
        for page in self.pdf.pages:
            txt = page.extract_text() or ""
            self.pages_text.append(txt)

        # OCR seletivo de páginas "curtas"
        ocr_candidates = [i for i, t in enumerate(self.pages_text)
                          if len(normalize_spaces(t).split()) < SHORT_TEXT_WORDS]
        if ocr_candidates:
            self._batch_raster_and_ocr(ocr_candidates, OCR_DPI_BODY)
    
    def close(self):
        try:
            self.pdf.close()
        except Exception:
            pass

    # ---------- Raster/OCR ----------
    #Chama convert_from_path para várias páginas de uma vez que devolve uma lista de imagens PIL.
    def _batch_raster_and_ocr(self, page_indices: list[int], dpi: int):
        if not page_indices:
            return
        for i in page_indices:
            pages = convert_from_path(
                self.pdf_path,
                dpi=dpi,
                first_page=i+1,
                last_page=i+1,
                fmt="jpeg",              # menor memória
                thread_count=1,
                use_pdftocairo=True
            )
            if not pages:
                continue
            img = pages[0].convert("L")  # grayscale
            if len(normalize_spaces(self.pages_text[i]).split()) < SHORT_TEXT_WORDS:
                self.pages_text[i] = image_to_string(img, lang="por", config="--oem 1 --psm 6") or self.pages_text[i]
            del img
    
    def _get_page_image(self, i: int, dpi: int):
        cache = self._img_cache if dpi >= 400 else self._img_cache
        if i not in cache:
            pages = convert_from_path(self.pdf_path, dpi=dpi, first_page=i+1, last_page=i+1)
            if pages:
                cache[i] = pages[0]
        return cache.get(i)
       
    def ocr_region(self, i: int, frac_top: float, frac_bottom: float, dpi: int, psm: int = 6) -> str:
        pages = convert_from_path(
            self.pdf_path,
            dpi=dpi,
            first_page=i+1,
            last_page=i+1,
            fmt="jpeg",
            thread_count=1,
            use_pdftocairo=True
    )
        if not pages:
            return ""
        img = pages[0].convert("L")
        w, h = img.size
        y0 = int(h * frac_top)
        y1 = int(h * (1.0 - frac_bottom))
        crop = img.crop((0, y0, w, y1))
        txt = image_to_string(crop, lang="por", config=f"--oem 1 --psm {psm}") or ""
        del crop, img
        return 
    
    
    #Chamam OCR na região do cabeçalho
    def ocr_header(self, i: int, frac: float = HEADER_FRAC) -> str:
        return self.ocr_region(i, 0.0, 1.0-frac, dpi=OCR_DPI_HEADER, psm=6)
    #Chamam OCR na região do rodapé
    def ocr_footer(self, i: int, frac: float = FOOTER_FRAC) -> str:
        return self.ocr_region(i, 1.0-frac, 0.0, dpi=OCR_DPI_FOOTER, psm=6)

    def footer_text(self, i: int, frac: float = FOOTER_FRAC) -> str:
        if i in self._footer_text_cache:
            return self._footer_text_cache[i]
        try:
            page = self.pdf.pages[i]
            w, h = page.width, page.height
            bbox = (0, h*(1-frac), w, h)
            clip = page.within_bbox(bbox)
            txt = clip.extract_text(x_tolerance=0.5, y_tolerance=0.5) or ""
            if not txt.strip():
                words = clip.extract_words(x_tolerance=0.5, y_tolerance=0.5) or []
                txt = " ".join(wd["text"] for wd in words)
        except Exception:
            txt = ""
        self._footer_text_cache[i] = txt
        return txt


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

# Número do processo (CNJ)--------------------
CNJ_REGEX = re.compile(r"\b\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}\b")
def extract_numero_processo(text: str) -> typing.Optional[str]:
    m = CNJ_REGEX.search(text)
    return m.group(0) if m else None

# Requerente ------------------------
def extract_requerente(text: str) -> typing.Optional[str]:
    m = re.search(r"(?im)^\s*REQUERENTE\s*[:\-]\s*(.+)$", text or "")
    if m:
        return normalize_spaces(m.group(1))
    m = re.search(r"REQUERENTE\s*[:\-]\s*(.+)", text or "", flags=re.IGNORECASE)
    return normalize_spaces(m.group(1)) if m else None

# Parentesco +  Falecido ------------- 
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
    vi[uú]v[ao]|
    adotiv[ao]|                       
    tutelad[ao]|                      
    tutor|tutora| herdeir[ao]|
    testamenteir[ao]|    inventariante|   representante|   
            respons[aá]vel                     
    )
\s+d[aeo]s?\s+                       # de / do / da / dos / das
(?:falecid[oa]\s+|sr\.?\s+|sra\.?\s+|de\s+cujus\s+)?   # opcional
"""

# --- NOVO: padrão ancorado em "requerente é (grau) de (NOME)" ---
RE_GRAU_TERMO = r"""
    filh[ao]|pai|m[ãa]e|av[óô]|bisav[óô]|tatarav[óô]|net[oa]|bisnet[oa]|
    irm[ãa]o|ti[oa]|sobrinh[ao]|prim[oa]|sogr[oa]|genr[eo]|nora|cunhad[oa]|
    padrasto|madrasta|entead[oa]|companheir[ao]|convivent[ea]|
    c[oô]njuge|espos[ao]|marido|mulher|vi[uú]v[ao]|tutor|tutora|tutelad[oa]
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
# --- Helpers de parentesco ---

NON_KIN = {
    "herdeiro","herdeira","testamenteiro","testamenteira",
    "inventariante","representante","responsavel","responsável",
    "adotivo","adotiva"  # 'adotivo' isolado não é grau; ex.: "filho adotivo" já é coberto por 'filho'
}

def _canon_grau(s: str) -> str:
    """Normaliza para comparação (sem acento/minúsculo)."""
    return lower_noacc(normalize_spaces(s))

def _is_non_kin(g: str) -> bool:
    return _canon_grau(g) in NON_KIN

# ---- Detectores de sexo do falecido (melhorados) ----
RE_FEM_LOCAL = re.compile(r"\b(falecida|nascida|vi[uú]va|esposa|senhora|sra\.?)\b", re.IGNORECASE)
RE_MASC_LOCAL = re.compile(r"\b(falecido|nascido|vi[uú]vo|esposo|marido|senhor|sr\.?)\b", re.IGNORECASE)

def _sexo_falecido(texto: str) -> typing.Optional[str]:
    """Tenta inferir sexo do falecido com base em 'falecido/falecida'."""
    t = lower_noacc(texto or "")
    if re.search(r"\bfalecida\b", t): return "F"
    if re.search(r"\bfalecido\b", t): return "M"
    return None
def infer_sexo_falecido(texto: str,
                        nome_span: typing.Optional[tuple[int, int]] = None,
                        window: int = 180) -> typing.Optional[str]:
    """
    Tenta inferir sexo do falecido priorizando o contexto logo após o NOME.
    Retorna "F", "M" ou None.
    """
    t = texto or ""
    zonas: list[str] = []

    if nome_span:
        ini, fim = nome_span
        ini_ctx = max(0, ini - 40)      # pega um pouco antes do nome
        fim_ctx = min(len(t), fim + window)
        zonas.append(t[ini_ctx:fim_ctx])

    # fallback: documento todo
    zonas.append(t)

    for z in zonas:
        zl = lower_noacc(z)
        if RE_FEM_LOCAL.search(zl):
            return "F"
        if RE_MASC_LOCAL.search(zl):
            return "M"
    return None

def _choose_by_sex(neutral: str, sexo: typing.Optional[str]) -> str:
    """Converte marcas neutras para M/F quando possível."""
    if not sexo:
        return neutral
    sub = {
        "filho(a)":  {"M": "filho", "F": "filha"},
        "neto(a)":   {"M": "neto",  "F": "neta"},
        "bisneto(a)":{"M": "bisneto","F": "bisneta"},
        "tataraneto(a)": {"M": "tataraneto", "F": "tataraneta"},
        "irmão(ã)": {"M": "irmão", "F": "irmã"},
        "tio/tia":  {"M": "tio",   "F": "tia"},
        "genro/nora":{"M": "genro","F": "nora"},
        "sogro(a)": {"M": "sogro","F": "sogra"},
        "padrasto/madrasta":{"M": "padrasto","F": "madrasta"},
        "tutor(a)": {"M": "tutor","F": "tutora"},
        "tutelado(a)": {"M": "tutelado","F": "tutelada"},
        "avô/avó":  {"M": "avô",   "F": "avó"},
        "bisavô/avó":{"M": "bisavô","F": "bisavó"},
        "tataravô/avó":{"M": "tataravô","F": "tataravó"},
        "cônjuge":  {"M": "cônjuge","F": "cônjuge"},  # neutro mesmo
    }
    return sub.get(neutral, {}).get(sexo, neutral)

def invert_parentesco_requerente_para_falecido(grau_requerente: str,
                                               sexo_falecido: typing.Optional[str]=None) -> typing.Optional[str]:
    g = _canon_grau(grau_requerente)

    def is_any(*alts: str) -> bool:
        return g in { _canon_grau(a) for a in alts }

    if is_any("pai","mãe","mae"):
        neutral = "filho(a)"
    elif is_any("filho","filha"):
        # aqui escolhemos pai/mãe (não "genitor(a)")
        if sexo_falecido == "M":
            return "pai"
        elif sexo_falecido == "F":
            return "mãe"
        else:
            return "pai/mãe"
    elif is_any("avô","avo","avó","avo"):
        neutral = "neto(a)"
    elif is_any("bisavô","bisavo","bisavó","bisavo"):
        neutral = "bisneto(a)"
    elif is_any("tataravô","tataravo","tataravó","tataravo"):
        neutral = "tataraneto(a)"
    elif is_any("neto","neta"):
        neutral = "avô/avó"
    elif is_any("bisneto","bisneta"):
        neutral = "bisavô/avó"
    elif is_any("tataraneto","tataraneta"):
        neutral = "tataravô/avó"
    elif is_any("irmão","irmao","irmã","irma"):
        neutral = "irmão(ã)"
    elif is_any("tio","tia"):
        neutral = "sobrinho(a)"
    elif is_any("sobrinho","sobrinha"):
        neutral = "tio/tia"
    elif is_any("sogro","sogra"):
        neutral = "genro/nora"
    elif is_any("genro","nora"):
        neutral = "sogro(a)"
    elif is_any("padrasto","madrasta"):
        neutral = "enteado(a)"
    elif is_any("enteado","enteada"):
        neutral = "padrasto/madrasta"
    elif is_any("companheiro","companheira","convivente",
                "cônjuge","conjuge","esposo","esposa","marido","mulher",
                "viúvo","viuvo","viúva","viuva"):
        neutral = "cônjuge"
    elif is_any("tutor","tutora"):
        neutral = "tutelado(a)"
    elif is_any("tutelado","tutelada"):
        neutral = "tutor(a)"
    elif is_any("cunhado","cunhada"):
        neutral = "cunhado(a)"
    else:
        return None

    return _choose_by_sex(neutral, sexo_falecido)


def extract_parentesco_e_falecido(text: str) -> tuple[typing.Optional[str], typing.Optional[str]]:
    """
    Retorna (grau_do_falecido_em_relacao_ao_requerente, nome_do_falecido)
    """
    t = normalize_spaces(text)

    # loopa pelos padrões em ordem de confiança
    for rx in (RE_PARENTESCO_NOME_UPPER, RE_PARENTESCO_NOME_TITLE, RE_PARENTESCO_FALLBACK):
        for m in rx.finditer(t):
            grau_req = m.group("grau").lower()
            if _is_non_kin(grau_req):
                continue

            nome = m.group("nome").strip()

            # >>> sexo do falecido priorizando o contexto do nome
            sexo_local = infer_sexo_falecido(t, nome_span=m.span("nome"))
            if not sexo_local:
                # fallback global (ex.: "… falecida …" em outro ponto)
                sexo_local = _sexo_falecido(t)

            grau_fal = invert_parentesco_requerente_para_falecido(
                grau_req, sexo_falecido=sexo_local
            )
            if grau_fal:
                return grau_fal, nome

    return None, None

# =========================
# Local do óbito + Data ------------------------
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


# aceita 17/03/2020, 17-03-2020 ou 17.03.2020
RE_DATA_NUM_ANY = re.compile(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{4})\b")
RE_DATA_EXTENSO = re.compile(
    r"\b(\d{1,2})\s+de\s+(janeiro|fevereiro|mar[cç]o|abril|maio|junho|"
    r"julho|agosto|setembro|outubro|novembro|dezembro)\s+de\s+(\d{4})\b",
    re.IGNORECASE
)
#âncoras
RE_FALECEU = re.compile(r"(falecid[oa]|faleceu|óbito)", re.IGNORECASE)
RE_CAUSA_MORTIS = re.compile(r"causa\s+mortis", re.IGNORECASE)


#Local do Óbito ---------------------------
# Padrão geral para Cidade–UF (tolerante a nomes compostos, hífen/apóstrofo)
# -------- Local do óbito --------
DASH_CHARS = "-–—"
DASH_CC    = f"[{re.escape(DASH_CHARS)}]"
RE_CAUSA_MORTIS = re.compile(r"causa\s+mortis", re.IGNORECASE)

CITY_TOKEN = r"[A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç'’.-]+"
CITY_NAME  = rf"{CITY_TOKEN}(?:\s+(?:d[aeo]s?|de|do|da|dos|das|e)\s+{CITY_TOKEN}){{0,4}}"

# 1) cidade–UF logo após 'falecid(a)/faleceu/óbito ... em'
EM_CITY_RE = re.compile(
    rf"(?:falecid[oa]|faleceu|ó?bito)[^.\n]{{0,120}}?\bem\s+(?P<cidade>{CITY_NAME})\s*{DASH_CC}\s*(?P<uf>[A-Z]{{2}})",
    re.IGNORECASE
)

# 2) cidade–UF genérico (usado como fallback)
CITY_UF_RE = re.compile(
    rf"(?P<cidade>{CITY_NAME})\s*{DASH_CC}\s*(?P<uf>[A-Z]{{2}})",
    re.IGNORECASE
)

_STOP_CITY = {
    "juizo","juízo","justica","justiça","defensoria","promotoria",
    "vara","comarca","direito","exercicio","exercício","itinerante","tribunal","poder"
}

def _ok_city(cidade: str) -> bool:
    toks = cidade.split()
    if len(toks) > 6:                 # cidades reais raramente passam disso
        return False
    if any(lower_noacc(t) in _STOP_CITY for t in toks):
        return False
    return True

def extract_local_obito(text: str) -> typing.Optional[str]:
    if not text:
        return None
    t = re.sub(r"\s+", " ", text)

    # limitar a busca ao trecho ANTES de "causa mortis"
    m_anchor = RE_CAUSA_MORTIS.search(t)
    search_space = t[:m_anchor.start()] if m_anchor else t

    # (1) ancorado em '... em Cidade – UF'
    m = EM_CITY_RE.search(search_space)
    if m and _ok_city(m.group("cidade")):
        return f"{normalize_spaces(m.group('cidade'))}-{m.group('uf').upper()}"

    # (2) último Cidade – UF válido antes da âncora
    last = None
    for mm in CITY_UF_RE.finditer(search_space):
        cidade = normalize_spaces(mm.group("cidade"))
        if _ok_city(cidade):
            last = (cidade, mm.group("uf").upper())
    if last:
        return f"{last[0]}-{last[1]}"

    # (3) fallbacks leves (também no trecho antes da âncora)
    m = re.search(r"local do falecimento[\s,:-]*([^\n\r]+)", search_space, flags=re.IGNORECASE)
    if m:
        return normalize_spaces(m.group(1))

    cap = rf"([A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç'.-]+)\s*{DASH_CC}\s*([A-Z]{{2}})"
    a = re.search(cap, search_space)
    return normalize_spaces(a.group(0)) if a else None

#Data do Óbito ------------------------------
def extract_data_obito(text: str) -> typing.Optional[str]:
    if not text:
        return None
    t = re.sub(r"\s+", " ", text)
    # 1) “falecida/faleceu em Cidade – UF, dia <data por extenso>”
    m = RE_LOCAL_DATA_EXTENSO.search(t)
    if m:
        return to_br_date_from_extenso(m.group('dia'), m.group('mes'), m.group('ano'))
    
    m = re.search(r"(?:falecimento|faleceu|óbito).{0,40}?\b(\d{1,2}/\d{1,2}/\d{4})\b", text, flags=re.IGNORECASE | re.DOTALL)
    # 2) Preferir a data logo após a ÚLTIMA ocorrência de “falecido/faleceu/óbito”
    #    (evita confundir com “nascido em …” antes)
    last_fal = None
    for mf in RE_FALECEU.finditer(t):
        last_fal = mf
    if last_fal:
        janela = t[last_fal.end() : last_fal.end() + 160]   # 160 chars após “falecido/faleceu”
        m_ext = RE_DATA_EXTENSO.search(janela)
        if m_ext:
            d, mes, a = m_ext.groups()
            return to_br_date_from_extenso(d, mes, a)
        m_num = RE_DATA_NUM_ANY.search(janela)
        if m_num:
            d, mth, y = map(int, m_num.groups())
            return f"{d:02d}/{mth:02d}/{y:04d}"


    # 3) Fallback: pegar a ÚLTIMA data antes de “causa mortis”
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
        for nm in RE_DATA_NUM_ANY.finditer(prefix):
            last_num = nm
        if last_num:
            d, mn, y = map(int, last_num.groups())
            return f"{d:02d}/{mn:02d}/{y:04d}"
    return to_br_date(m.group(1)) if m else None

# --- Parecer (tabela do PJe) ---
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
    rows = parse_tabela_documentos(text or "")
    # candidatos: qualquer linha normalizada para "parecer"
    candidatos = [r for r in rows if r["tipo"] in ("parecer","manifestação")]
    if candidatos:
        return candidatos[-1]["id"]
    return None

#---------------------------------------------------------------------------------------------------------------------------
# --- Declaração de Óbito: ID (Num. ... - Pág. ...) ---


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

def _count_kw(*texts: str) -> int:
    """Conta quantas palavras da lista aparecem (presença distinta, não repetição)."""
    s = " ".join((t or "").lower() for t in texts)
    return sum(1 for p in PALAVRAS_DECL if p.lower() in s)


def _extrai_id_pag(texto: str) -> typing.Optional[str]:
    m = ID_PAG_PAT.search(texto or "")
    if m:
        return f"Num. {m.group('num')} - Pág. {m.group('pag')}"
    m = ID_PAG_FUZZY.search(texto or "")
    if m:
        return f"Num. {m.group(1)} - Pág. {m.group(2)}"
    return None
RE_DO_HEADER   = re.compile(r"\bdeclara[cç][aã]o\s+de\s+[óo]bito\b", re.IGNORECASE)
RE_NASC_HEADER = re.compile(r"\bcertid[aã]o\s+de\s+nascimento\b", re.IGNORECASE)
RE_RCNP        = re.compile(r"registro\s+civil\s+das\s+pessoas\s+naturais", re.IGNORECASE)


def extract_id_declaracao_avancado(ctx: PDFContext) -> typing.Optional[str]:
    candidatas = []

    # 1) Só entram páginas que tenham 'Declaração de Óbito' no topo (e não sejam CN)
    for i, _ in enumerate(ctx.pages_text):
        body = ctx.pages_text[i] or ""
        head = ctx.ocr_header(i, frac=0.42) or ""

        # filtros obrigatórios
        has_do = RE_DO_HEADER.search(head) or RE_DO_HEADER.search(body)
        is_cn  = RE_NASC_HEADER.search((head + " " + body).lower()) or RE_RCNP.search((head + " " + body).lower())

        # novo: precisa ter > 2 palavras-chave (>= 3)
        kw_score = _count_kw(body, head)

        # debug opcional
        print(f"[DO] pág {i+1:>2}  has_DO={bool(has_do)}  is_CN={bool(is_cn)}  kw={kw_score}")

        if has_do and not is_cn and kw_score >= 2:
            candidatas.append(i)

    # Sem candidatas válidas → nada a retornar
    if not candidatas:
        return None

    # 2) Tenta extrair o "Num. ... - Pág. ..." nas candidatas
    for i in candidatas:
        # (a) corpo da página (às vezes o OCR joga o rodapé no corpo)
        idp = _extrai_id_pag(ctx.pages_text[i])
        if idp:
            print(f"[DO] pág {i+1}: ID pelo corpo")
            return idp

        # (b) rodapé via pdfplumber
        idp = _extrai_id_pag(ctx.footer_text(i))
        if idp:
            print(f"[DO] pág {i+1}: ID no rodapé (pdf)")
            return idp

        # (c) rodapé via OCR
        idp = _extrai_id_pag(ctx.ocr_footer(i, frac=0.28))
        if idp:
            print(f"[DO] pág {i+1}: ID no rodapé (ocr)")
            return idp

    return None


#------------------------------------------------------------------------------------------------------
# --- Certidões negativas ---



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
RE_EXCL_JUD = re.compile(r"(processo\s*n?[ºo]|classe\s*:|assunto\s*:|requerente\s*:|justi[cç]a\s+itinerante)",re.IGNORECASE
)
RE_EXCL_MP = re.compile(r"(minist[eé]rio\s+p[úu]blico|promotori[ao]?\s+de\s+justi[cç]a|"r"promotor[ao]\s+de\s+justi[cç]a|\bparquet\b)",re.IGNORECASE,)


def _explain_page(text: str) -> dict:
    """
    Avalia todos os sinais na página/trecho e explica o que bateu.
    Retorna um dicionário com flags e trechos (snippets) de cada match.
    """
    t = lower_noacc(text or "")
    excl = any(rx.search(t) for rx in (RE_EXCL_NASC, RE_EXCL_JUD,RE_EXCL_MP))
    has_title = bool(RE_CERT_NEG_TIT.search(t))
    has_cart  = bool(RE_CARTORIO.search(t) or RE_CARTORIO_STRONG.search(t))
    is_cert   = (not excl) and has_title and has_cart
    return {"is_cert": is_cert}



def find_certidoes_negativas(ctx: PDFContext, debug: bool = False):
    resultados = []
    for i, full_txt in enumerate(ctx.pages_text):
        decided = _explain_page(full_txt)["is_cert"]
        if not decided:
            head_txt = ctx.ocr_header(i, frac=0.55)
            if head_txt:
                decided = _explain_page(head_txt)["is_cert"]
        if not decided:
            continue
        par = None
        txt_pdf = ctx.footer_text(i)
        m = ID_PAG_PAT.search(txt_pdf or "")
        if m: par = (m.group("num"), m.group("pag")); id_source = "pdf_footer"
        if not par:
            m2 = ID_PAG_FUZZY.search(txt_pdf or "")
            if m2: par = (m2.group(1), m2.group(2)); id_source = "pdf_footer"
        if not par:
            rod_ocr = ctx.ocr_footer(i, frac=0.28)
            m3 = ID_PAG_PAT.search(rod_ocr or "")
            if m3: par = (m3.group("num"), m3.group("pag")); id_source = "ocr_footer"
            else:
                m4 = ID_PAG_FUZZY.search(rod_ocr or "")
                if m4: par = (m4.group(1), m4.group(2)); id_source = "ocr_footer"
        if par:
            num, pag = par
            resultados.append({
                "pdf_page": i+1, "num": num, "pag": int(pag),
                "rodape": f"Num. {num} - Pág. {pag}", "id_source": id_source, "chosen_src": "full"
            })
    return resultados





# =========================
# Pipeline
# =========================
CAMPOS_ORDEM = [
    "numero_processo","requerente","parentesco","nome_falecido",
    "local_obito","data","id_parecer","id_declaracao","id_certidoes"
]

def montar_resultado(ctx: PDFContext) -> dict:
    full_text = "\n\n".join(ctx.pages_text)

    par, fal = extract_parentesco_e_falecido(full_text)

    req_raw = extract_requerente(full_text)
    loc_raw = extract_local_obito(full_text)
   

    resultado = {
        "numero_processo": extract_numero_processo(full_text),
        "requerente":      req_raw,
        "parentesco":      par,
        "nome_falecido":   fal,
        "local_obito":     fix_local_obito_uf(loc_raw),
        "data":            extract_data_obito(full_text),
        "id_parecer":      extract_id_parecer(full_text),
        "id_declaracao":   extract_id_declaracao_avancado(ctx),
        "id_certidoes":    find_certidoes_negativas(ctx, debug=False),
    }
    print("Resultado extraído:", resultado)
    return resultado

#---------------------------------------------------------------------------------------------------------------------------


# -------------------------
# Cria um PDFContext e no finally fecha o PDF
# -------------------------
def process_pdf(pdf_path: str) -> dict:
    ctx = PDFContext(pdf_path)
    try:
        return {"resultado": montar_resultado(ctx)}
    except Exception:
        logging.exception("Erro processando %s", pdf_path)  # imprime stack trace
        raise
    finally:
        ctx.close()