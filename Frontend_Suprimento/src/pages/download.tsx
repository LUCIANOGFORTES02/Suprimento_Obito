import { DownloadService } from "@/api/downloadService";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Download, Loader2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";


function DownloadPage() {//Tem que recerber como prop o link do arquivo gerado

    const [isDownloading, setIsDownloading] = useState(false);
    const [showSuccessModal, setShowSuccessModal] = useState(true);

    const handleDownload = async (filename:string) => {
        setIsDownloading(true); 
        try {
            const success = await DownloadService.downloadFile(filename);
            if (success) {
               toast.success('Download iniciado! Verifique sua área de trabalho.');
            } 
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
            <Dialog >
                <DialogTrigger>Open</DialogTrigger>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Sentença Gerada!</DialogTitle>
                        <DialogDescription>
                            Seu arquivo ODT foi gerado com sucesso. Está pronto para download.
                        </DialogDescription>
                    </DialogHeader>
                    <DialogFooter>
                        <Button  onClick={() => handleDownload('sentenca.odt')}
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
                            <Button variant="outline" onClick={() => setShowSuccessModal(false)}>
                            Fechar
                            </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </>
            );

        }
export default DownloadPage;
