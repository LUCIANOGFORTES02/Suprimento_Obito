import {
  Card,
  CardContent,
} from "@/components/ui/card"
import { File } from 'lucide-react';
import { Link } from "react-router";

function Header() {
    return ( 
        <>
        <Card>
            <CardContent className="flex flex-row items-center justify-center gap-2">
                    <File className=""/>
                    <Link to="/">
                    <h1 className="text-2xl">Conversor PDF </h1>
                    </Link>
            </CardContent>
        </Card>
        </>
        
        
     );
}

export default Header;