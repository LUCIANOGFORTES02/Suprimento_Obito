from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Dict, Any, List
import tempfile
import os
from .processing import process_pdf
from .odtGenerator import ODTGenerator
from pydantic import BaseModel

app = FastAPI()

#Cors

origins = [
    "http://localhost:5173",
    "http://localhost:8000",
    "https://suprimento-obito.vercel.app",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:8000",
        "https://suprimento-obito.vercel.app",
    ],
    # cobre URLs de preview: https://<preview>.vercel.app
    allow_origin_regex=r"https://([a-z0-9-]+\.)*vercel\.app$",
    allow_methods=["*"],
    allow_headers=["*"],
    # keep it False se não usa cookies/autorização de 1º/3º
    allow_credentials=False,
)


class ReviewData(BaseModel):
    numero_processo: str
    requerente: str
    parentesco: str
    nome_falecido: str
    local_obito: str
    data: str
    id_parecer: str
    id_declaracao: str
    id_certidoes: List[str]



@app.get("/")
def root():
    return {"status": "ok"}

MAX_BYTES = 10 * 1024 * 1024  # 10 MB

@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    """
    Processa o PDF e retorna APENAS os dados para preencher o formulário frontend
    """
    try:
        # Salva o arquivo temporariamente
        written = 0 
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            # content = await file.read()
            await file.seek(0)
            while True:
                chunk = await file.read(1024 * 1024)  # 1 MB
                if not chunk:
                    break
                written += len(chunk)
                if written > MAX_BYTES:
                    raise HTTPException(413, "Arquivo muito grande")
                tmp_file.write(chunk)
            tmp_path = tmp_file.name

            # tmp_file.write(content)
            # tmp_path = tmp_file.name
        
        # Processa o PDF e extrai os dados
        out = process_pdf(tmp_path)
        
        # Limpa arquivo temporário
        os.unlink(tmp_path)
        
        # Retorna APENAS os campos que o frontend precisa
        return JSONResponse({
            "success": True,
            "data": out["resultado"]
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro no   processamento: {str(e)}")
    

odt_generator = ODTGenerator()

@app.post("/review")
async def review(data: ReviewData):
    try:
        print(f"📥 Recebido review data: {data.dict()}")

        #Gerar o documento ODT aqui usando os dados recebidos
        outh_path=odt_generator.generate_from_template(data.dict())
        print(f"✅ Documento gerado com sucesso: {outh_path}")
        #Prepara resposta com URL para download
        response = odt_generator.create_download_response(outh_path)

        return{
            "success":True,
            "message": "Documento gerado com sucesso",
            "download_url": response["download_url"],
            "filename": response["filename"]
        }
    except Exception as e:
        print(f" Erro ao processar review: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao gerar documento: {str(e)}")




#Endpoint para download do arquivo gerado
@app.get("/download/{filename}")
async def download_file(filename: str):
    """
    Endpoint para download do arquivo ODT gerado
    """
    file_path = f"/tmp/{filename}"
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    
    return FileResponse(
        file_path,
        media_type="application/vnd.oasis.opendocument.text",
        filename=filename
    )