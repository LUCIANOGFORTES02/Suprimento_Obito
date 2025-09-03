 import api from "./axiosInstance";

 export const DownloadService = {
    downloadFile: async (filename: string) => {
        try {
            const response = await api.get(`/download/${filename}`, {
                responseType: 'blob', // Importante para arquivos binários
            });

            //Cria um link temporário para download
            const url = window.URL.createObjectURL(new Blob([response.data]));
            const link = document.createElement('a');
            link.href = url;

            //Define o nome do arquivo para salvar
            const downloadFilename = filename || 'downloaded_file.odt';
            link.setAttribute('download', downloadFilename);

            //Adiciona ao DOM e clica para iniciar o download
            document.body.appendChild(link);
            link.click();

            //Limpa o link temporário
            link.remove();
            window.URL.revokeObjectURL(url);

            return true; 
        } catch (error) {
            console.error("Erro ao baixar o arquivo:", error);
            throw new Error('Falha no download do arquivo');
        }
    }
 }
    