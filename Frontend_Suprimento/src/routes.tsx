import { Routes, Route } from "react-router-dom";
import UploadPage from "./pages/upload";
import ReviewPage from "./pages/review";

export default function Router() {
    return(
        <Routes>
            <Route path="/" element={<UploadPage />} />
            <Route path="/review" element={<ReviewPage />} />
        </Routes>
)
}