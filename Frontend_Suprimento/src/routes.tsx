import { Routes, Route } from "react-router";
import UploadPage from "./pages/upload";
import ReviewPage from "./pages/Review";

export default function Router() {
    return(
        <Routes>
            <Route path="/" element={<UploadPage />} />
            <Route path="/review" element={<ReviewPage />} />
        </Routes>
)
}