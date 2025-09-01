import { Button } from "@/components/ui/button";
import { CloudUpload } from "lucide-react";
import { useState } from "react";

function UploadPage() {
      const [file, setFile] = useState(null);


    
    return (  
        <>
        <p className="px-5 py-2  text-xl">Faça upload do seu arquivo PDF</p>

        <div className="flex flex-col p-5 gap-8">
        {/* Área de Upload */}
            <div className="flex flex-col items-center justify-center border-2 border-dashed gap-2" > 
                    {/* Texto */}
                     <div className='flex flex-col items-center' >
                        <div className='mb-4'>
                            <CloudUpload className='w-20 h-20 text-gray-300'/>
                        </div>
                        <p className='text-foreground text-xl font-medium'>Arraste e solte</p>
                        <p className='text-foreground text-xl font-medium'>arquivos para upload</p>
                        <p className='my-4 text-xl font-semibold'>ou</p>
                    </div>
                     {/* Botão */}
                    <div className='flex justify-center '>
                        <Button
                            
                            className="flex py-2 px-6 rounded-lg cursor-pointer"
                            >
                        Browse
                        </Button>
                       
                    </div>

                </div>
               
                
            
            

        {/* Informaçãoes do arquivo*/}

        <div className="flex flex-col  items-center">
            {file && (
                <div>
                    <h2>Informações do arquivo:</h2>
                </div>
            )}
            <Button >Enviar</Button>
        </div>
    
            
        </div>   
        </>
    );
}

export default UploadPage;