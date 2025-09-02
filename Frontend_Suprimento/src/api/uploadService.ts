import api from '../api/axiosInstance';

export const UploadService = {
    uploadFile: async (data:any) => {
        try {
            const response = await api.post('/upload', data);
            return response.data;
            
        } catch (error) {
            console.error("Erro ao fazer upload do arquivo:", error);
            throw error;
            
        }

}
}
