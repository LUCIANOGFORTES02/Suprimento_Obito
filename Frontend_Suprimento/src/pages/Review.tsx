import { Button } from "@/components/ui/button";
import { z } from "zod"
import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { ArrowLeft } from 'lucide-react';
import { Link, useLocation } from "react-router";
import { ReviewService, type ReviewData } from "@/api/reviewService";
import type { ProcessedData } from "@/api/uploadService";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import DownloadPage from "./download";


const parseCertidoes = (text: string): string[] => {
  // divide por vírgula OU ponto e vírgula, trim, remove vazios, remove duplicados
    const items = text
        .split(/[;,]/)
        .map(s => s.trim())
        .filter(Boolean);

    return  Array.from(new Set(items));
};

//Criando um esquema de formulário
const formSchema = z.object({
    numero_processo:z.string().trim().min(5, { message: "Informe o número do processo." }),
    requerente: z.string().trim().min(2, { message: "Informe o nome do requerente." }),
    parentesco: z.string().trim().min(2, { message: "Informe o parentesco." }),
    nome_falecido: z.string().trim().min(2, { message: "Informe o nome do falecido." }),
    local_obito: z.string().trim().min(2, { message: "Informe o local do óbito." }),
    data: z.string().trim().regex(/^\d{2}\/\d{2}\/\d{4}$/, { message: "Data deve estar no formato DD/MM/AAAA" })
    .refine((val) => {
      // Validação adicional para data real
      const [day, month, year] = val.split('/').map(Number);
      const date = new Date(year, month - 1, day);
      return date.getDate() === day && 
             date.getMonth() === month - 1 && 
             date.getFullYear() === year;
    }, { message: "Data inválida" }),
    id_parecer: z.string().trim().min(1, { message: "Informe o ID do parecer." }),
    id_declaracao: z.string().trim().min(1, { message: "Informe o ID da declaração." }),
    id_certidoes: z.string().trim().min(1, { message: "Informe ao menos uma certidão." })
    .refine((s) => parseCertidoes(s).length > 0, { message: "Informe ao menos uma certidão válida." })
    .refine((s) => parseCertidoes(s).every(x => x.length >= 2), { message: "Cada ID deve ter ao menos 2 caracteres." }),
})

function ReviewPage() {

    const location = useLocation();
    const receivedData = location.state?.formData as ProcessedData | undefined;
        const [downloadData, setDownloadData] = useState<{ filename: string; showModal: boolean } | null>(null);

    // Definição do formulário
    const form = useForm<z.infer<typeof formSchema>>({//Conectando o zod com o react-hook-form
        resolver: zodResolver(formSchema),
        defaultValues: receivedData ? {
            numero_processo: receivedData.numero_processo,
            requerente: receivedData.requerente,
            parentesco: receivedData.parentesco,
            nome_falecido: receivedData.nome_falecido,
            local_obito: receivedData.local_obito,
            data: receivedData.data,
            id_parecer: receivedData.id_parecer,
            id_declaracao: receivedData.id_declaracao,
            id_certidoes: Array.isArray(receivedData.id_certidoes) 
                ? receivedData.id_certidoes.join(', ')
                : receivedData.id_certidoes || "",
        } : {
            numero_processo: "",
            requerente: "",
            parentesco: "",
            nome_falecido: "",
            local_obito: "",
            data: "",
            id_parecer: "",
            id_declaracao: "",
            id_certidoes: "",
        },
    });

    // Se receber dados, preenche o formulário automaticamente
    useEffect(() => {
        if (receivedData) {
            form.reset({
                numero_processo: receivedData.numero_processo,
                requerente: receivedData.requerente,
                parentesco: receivedData.parentesco,
                nome_falecido: receivedData.nome_falecido,
                local_obito: receivedData.local_obito,
                data: receivedData.data,
                id_parecer: receivedData.id_parecer,
                id_declaracao: receivedData.id_declaracao,
                id_certidoes: Array.isArray(receivedData.id_certidoes) 
                    ? receivedData.id_certidoes.join(', ')
                    : receivedData.id_certidoes || "",
            });
        }
    }, [receivedData, form]);
        
    const certidoesPreview = parseCertidoes(form.watch("id_certidoes"));


    // 2. Define a submit handler.
  async function onSubmit(values: z.infer<typeof formSchema>) {
    try {
        const reviewData: ReviewData = {
            ...values,
            id_certidoes: parseCertidoes(values.id_certidoes),
        };
        console.log("Enviando de volta para o backend somente os campos:",receivedData)
        const response = await ReviewService.submitReview(reviewData);
        setDownloadData({
                filename: response.filename,
                showModal: true
            });

        toast.success("Dados enviados com sucesso!");

    } catch (error) {
        toast.error("Erro ao enviar os dados para o servidor.");    
    }
     
  };
    return ( 
        <>
           
        

        <Card className="w-full">
        <Link to="/" className="flex items-center px-5 text-sm  hover:text-gray-400 cursor-pointer" >
            <ArrowLeft />
            <span>Voltar</span>
        </Link>
                <CardHeader>
                    <CardTitle className="font-bold text-2xl">Revise os dados antes de enviar</CardTitle>
                </CardHeader>

                {/* Formulário com os campos */}
                <Form {...form} >
                    <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-8 ">
                        <CardContent className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <FormField
                        control={form.control}
                        name="numero_processo"
                        render={({ field }) => (
                            <FormItem >
                            <FormLabel>Número do processo</FormLabel>
                            <FormControl>
                                <Input placeholder="Número do processo" {...field} />
                            </FormControl>
                            <FormMessage />
                            </FormItem>
                                )}
                            />
                        <FormField
                            control={form.control}
                            name="requerente"
                            render={({ field }) => (
                                <FormItem >
                                <FormLabel>Requerente</FormLabel>
                                <FormControl>
                                    <Input placeholder= "Nome do requerente"{...field} />
                                </FormControl>
                                <FormMessage />
                                </FormItem>
                                    )}
                                />
                        <FormField
                            control={form.control}
                            name="parentesco"
                            render={({ field }) => (
                                <FormItem >
                                <FormLabel>Parentesco</FormLabel>
                                <FormControl>
                                    <Input placeholder="Grau de parentesco" {...field} />
                                </FormControl>
                                <FormMessage />
                                </FormItem>
                                    )}
                            />
                        <FormField
                            control={form.control}
                            name="nome_falecido"
                            render={({ field }) => (
                                <FormItem >
                                <FormLabel>Falecido</FormLabel>
                                <FormControl>
                                    <Input placeholder="Nome do falecido" {...field} />
                                </FormControl>
                                <FormMessage />
                                </FormItem>
                                    )}
                                /> 
                        <FormField
                            control={form.control}
                            name="local_obito"
                            render={({ field }) => (
                                <FormItem >
                                <FormLabel>Local</FormLabel>
                                <FormControl>
                                    <Input placeholder="Local do óbito" {...field} />
                                </FormControl>
                                <FormMessage />
                                </FormItem>
                                    )}
                                /> 
                        <FormField
                            control={form.control}
                            name="data"
                            render={({ field }) => (
                                <FormItem >
                                <FormLabel>Data do falecimento</FormLabel>
                                <FormControl>
                                    <Input  placeholder="dd/mm/aaaa" {...field} 
                                              onChange={(e) => {
                                                let value = e.target.value.replace(/\D/g, ''); // Remove não-números
            
                                                // Aplica máscara DD/MM/AAAA
                                                if (value.length > 2) {
                                                value = value.slice(0, 2) + '/' + value.slice(2);
                                                }
                                                if (value.length > 5) {
                                                value = value.slice(0, 5) + '/' + value.slice(5, 9);
                                                }
            
                                                field.onChange(value);
                                                }}
                                                maxLength={10}
                                                />
                                </FormControl>
                                <FormMessage />
                                </FormItem>
                                    )}
                                />
                        <FormField
                            control={form.control}
                            name="id_parecer"
                            render={({ field }) => (
                                <FormItem >
                                <FormLabel>Parecer</FormLabel>
                                <FormControl>
                                    <Input placeholder="ID do paracer" {...field} />
                                </FormControl>
                                <FormMessage />
                                </FormItem>
                                    )}
                                /> 
                        <FormField
                            control={form.control}
                            name="id_declaracao"
                            render={({ field }) => (
                                <FormItem >
                                <FormLabel>Declaração</FormLabel>
                                <FormControl>
                                    <Input placeholder="ID da declaração" {...field} />
                                </FormControl>
                                <FormMessage />
                                </FormItem>
                                    )}
                                /> 
                                <FormField
                            control={form.control}
                            name="id_certidoes"
                            render={({ field }) => (
                                <FormItem className="md:col-span-2">
                                <FormLabel>Certidões</FormLabel>
                                <FormControl>
                                    <Input placeholder="Separe as certidões por vírgula ou ponto e vírgula (ex.: Num. 72323682 - Pág. 3 , Num. 7232554 - Pág. 2)" {...field} />
                                </FormControl>
                                <FormMessage />
                                                  {/* Preview dos itens parseados */}
                                                    {certidoesPreview.length > 0 && (
                                                        <div className="mt-2 flex flex-wrap gap-2">
                                                        {certidoesPreview.map((c) => (
                                                            <span
                                                            key={c}
                                                            className="text-xs bg-muted px-2 py-1 rounded-md border"
                                                            title={c}
                                                            >
                                                            {c}
                                                            </span>
                                                        ))}
                                                        </div>
                                                    )}    


                                </FormItem>
                                    )}
                                /> 

                </CardContent>
                <CardFooter className="flex gap-2">
                  {/* Botão para enviar */}
                    <Button type="submit" className="w-full">
                      Enviar
                    </Button>
                </CardFooter>
            </form>
            </Form>
        </Card>

        {downloadData?.showModal && (
                <DownloadPage 
                    filename={downloadData.filename} 
                    onClose={() => setDownloadData(null)}
                />
            )}

        </>
     );
}

export default ReviewPage;