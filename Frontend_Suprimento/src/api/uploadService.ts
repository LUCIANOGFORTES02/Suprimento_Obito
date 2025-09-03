import api from '../api/axiosInstance';

export interface ProcessedData {
    numero_processo: string;
    requerente: string;
    parentesco: string;
    nome_falecido: string;
    local_obito: string;
    data: string;
    id_parecer: string;
    id_declaracao: string;
    id_certidoes: string[];
}

export const UploadService = {
    uploadFile: async (file:File) => {
        const formData = new FormData();
        formData.append('file', file);
        try {
            console.log("Enviando para o upload do arquivo...",file);
            const response = await api.post('/upload', formData);
            console.log("Resposta do servidor:", response.data);
            return response.data;
            
        } catch (error) {
            console.error("Erro ao fazer upload do arquivo:", error);
            throw error;
            
        }

}
}
