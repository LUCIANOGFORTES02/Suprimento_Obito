import {
  Card,
  CardContent,
} from "@/components/ui/card"
function Header() {
    return ( 
        <>
        <Card>
            <CardContent className="flex flex-row items-center justify-center">
                <h1 className="text-2xl">Conversor PDF </h1>
            </CardContent>
        </Card>
        </>
        
        
     );
}

export default Header;