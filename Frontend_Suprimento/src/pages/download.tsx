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
import { useNavigate } from "react-router";
import { toast } from "sonner";

interface DownloadPageProps{
    filename:string
    onClose:()=>void

}

function DownloadPage({filename,onClose }:DownloadPageProps) {//Tem que recerber como prop o link do arquivo gerado
    const navigate = useNavigate();
    const [isDownloading, setIsDownloading] = useState(false);

    const handleDownload = async () => {
        setIsDownloading(true); 
        try {
            const success = await DownloadService.downloadFile(filename);
            if (success) {
               toast.success('Download finalizado!.',{
                action: {
                    label: 'Novo PDF',
                    onClick: () => navigate('/upload')    
            }, 
        });
        }  
        onClose();    
            return success;

        }
        catch (error) {
            toast.error('Erro ao baixar o arquivo');

            console.error("Erro ao baixar o arquivo:", error);
        }
        finally {
            setIsDownloading(false); 
        }


    }

    return (
        <>
            <Dialog open={true} onOpenChange={(open)=>!open && onClose()} >
                <DialogContent className="sm:max-w-[425px]">
                    <DialogHeader>
                        <DialogTitle>Download do Arquivo</DialogTitle>
                        <DialogDescription>
                            Seu arquivo ODT está pronto para download.
                        </DialogDescription>
                    </DialogHeader>
                    <DialogFooter className="flex flex-row gap-2 items-center justify-center">
                        <Button  onClick={handleDownload}
                            disabled={isDownloading}
                            >
                            {isDownloading ? (
                                <>
                                <Loader2 className="h-4 w-4 animate-spin" />
                                </>
                            ):(
                                <>
                                <Download className="h-4 w-4" />
                                </>
                            )}
                            Download ODT
                        </Button>
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
