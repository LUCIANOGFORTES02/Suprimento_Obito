import { Button } from "@/components/ui/button";
import { FileUp  } from "lucide-react";
import { useRef, useState } from "react";
import { toast } from "sonner";


function UploadPage() {

    const [file, setFile] = useState<File| null>(null);
    const [status, setStatus] = useState<"Success"| "uploading"| null>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);//Simula o clique no input file

    function handleFileChange(event: React.ChangeEvent<HTMLInputElement>) {
        const selectedFile = event.target.files ? event.target.files[0] : null;

        if (!selectedFile) return;

        // Validações
        if (selectedFile && selectedFile.type !== 'application/pdf') {
            toast.error('Por favor, selecione um arquivo PDF.');
            setFile(null);
            return
        }

        setFile(selectedFile);

        }
      

    async function handleUpload() {
        if (!file) return;  

        setStatus("uploading");
        const formData = new FormData();
        formData.append('file', file);

 

        
        // Chama o endpoint de upload
        try {
            await UploadService.uploadFile(formData);;
      }
      catch (error) {
            console.error('Erro ao enviar o arquivo:', error);
            toast.error('Erro ao enviar o arquivo.');
      }
      finally{
        setStatus("Success");
        toast.success("Upload realizado com sucesso!");
      // Resetar o estado após o upload
        setFile(null);
        if (fileInputRef.current) {
            fileInputRef.current.value = '';
        }
        setStatus(null);

      }

        

    }




    
    return (  
        <>
   
        <p className="px-5 py-2 text-xl">Faça upload do seu arquivo PDF</p>

        <div className="flex flex-col  p-5 gap-8">
        {/* Área de Upload */}
            <div className="flex flex-col items-center justify-center border-3 border-dashed gap-2 rounded-lg" > 
                    {/* Texto */}
                     <div className='flex flex-col items-center' >
                        <div className='mt-3 mb-2'>
                            <FileUp  className='w-20 h-20'/>
                        </div>
                        <p className='text-foreground text-xl font-medium'>Arraste e solte</p>
                        <p className='text-foreground text-xl font-medium'>arquivos para upload</p>
                        <p className='my-2 text-xl font-semibold'>ou</p>
                    </div>
                     
                     {/* Botão + input*/}
                    <div className='flex justify-center '>
                        <input type="file" onChange={handleFileChange} ref={fileInputRef} className="hidden" accept="application/pdf"/>
                        <Button
                            onClick={() => fileInputRef.current?.click()}
                            className="flex py-2 px-6 rounded-lg cursor-pointer mb-4"
                            >
                        Browse
                        </Button>
                       
                    </div>

                </div>
               
                
            {/* Informaçãoes do arquivo +  Upload do arquivo*/}

            <div className="flex flex-col  items-center">
                {file && (
                    <>
                        <div className="flex flex-row border-2 p-4 rounded-lg justify-between w-full max-w-md gap-4">
                            {/* Texto */}
                        <div className="flex-1">
                            <h2 className="text-sm text-gray-400 font-bold">Arquivo</h2>
                            <p className="text-sm font-semibold text-gray-400">{file.name}</p>
                            <p className="text-xs text-gray-400">{(file.size / 1024).toFixed(2)} KB</p>
                        </div>
                        {/* Imagem do pdf*/}
                        <div>
                            <img  />

                        </div>

                        </div>

                    <Button onClick={handleUpload} className="mt-4" disabled={status === "uploading"}>
                        Upload
                    </Button>   
                </>
                )}
                

            </div>
    
            
        </div>   
        </>
    );
}
import { UploadService } from "@/api/uploadService";

export default UploadPage;