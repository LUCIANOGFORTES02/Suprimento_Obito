import { DownloadService } from "@/api/downloadService";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Download, Loader2 } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

interface DownloadPageProps{
    filename:string
    onClose:()=>void
    onRestart?:()=>void

};
type DownloadState = "idle" | "downloading" | "downloaded" | "error";


function DownloadPage({filename,onClose,onRestart }:DownloadPageProps) {//Tem que recerber como prop o link do arquivo gerado
    const navigate = useNavigate();
    const [state, setState] = useState<DownloadState>("idle");



    const handleDownload = async () => {
        if (state === "downloading") return; // ✅ evita duplo clique
        setState("downloading"); 
        try {
            const success = await DownloadService.downloadFile(filename);
            if (success) {
                setState("downloaded");
                toast.success('Download finalizado!.',{
                action: {
                    label: 'Novo upload',
                    onClick: () => {
                        onClose();
                        if(onRestart){
                            onRestart();
                        }
                        else  {
                            navigate('/upload')
                        }  

                     }
            }, 
        });
        return true;
        
        }  else {
            setState("error");
            toast.error('Não foi possível baixar o arquivo.');
            return false;
        };

        }
        catch (error) {
            toast.error('Erro ao baixar o arquivo');

            console.error("Erro ao baixar o arquivo:", error);
        }


    }

    return (
        <>
            <Dialog open={true} onOpenChange={(open)=>!open && onClose()} >
                <DialogContent onInteractOutside={(e) => e.preventDefault()} className="sm:max-w-[425px]">
                    <DialogHeader>
                        <DialogTitle>Download do Arquivo</DialogTitle>
                        <DialogDescription>
                            Seu arquivo ODT está pronto para download.
                        </DialogDescription>
                    </DialogHeader>
                    <DialogFooter className="flex flex-row gap-2 items-center justify-center">
                        {state !== "downloaded" &&(
                        <Button  onClick={handleDownload}
                            disabled={state === "downloading"}
                            >
                            {state === "downloading" ? (
                                <>
                                <Loader2 className="h-4 w-4 animate-spin" />
                                </>
                            ):(
                                <>
                                <Download className="h-4 w-4" />
                                </>
                            )}
                           <span className="ml-2">
                                {state === "downloading" ? "Baixando..." : "Download ODT"}
                            </span>
                               
                        </Button>
                            )}
                  
                        {state === "downloaded" && (
                        <Button  onClick={ () => window.location.replace("/")}>
                            Enviar outro arquivo
                        </Button> )}
                        
                        <Button variant="outline" onClick={onClose}>
                            Fechar
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </>
            );

        }
export default DownloadPage;
