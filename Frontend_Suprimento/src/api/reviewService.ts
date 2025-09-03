import api  from "./axiosInstance";



export type ReviewData = {
    numero_processo: string,
    requerente: string,
    parentesco: string,
    nome_falecido: string,
    local_obito: string,
    data: string,
    id_parecer: string,
    id_declaracao: string,
    id_certidoes: string[];
};

export const ReviewService = {
    submitReview: async (payload:ReviewData) => {
        try {
            const response = await api.post('/review',payload);
            return response.data;
        } catch (error) {
            console.error("Erro ao gerar o arquivo ODT:", error);
            throw error;
        }
    }
}