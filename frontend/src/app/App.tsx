import { BrowserRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "../features/auth/AuthProvider";
import { LoginPage } from "../features/auth/pages/LoginPage";
import { RequireAuth } from "../features/auth/components/RequireAuth";
import { HomePage } from "../features/home/pages/HomePage";
import { RegisterPage } from "../features/auth/pages/RegisterPage";
import { NotFoundPage } from "./NotFoundPage";

export function App() {
    return (
        <BrowserRouter>
            <AuthProvider>
                <Routes>
                    <Route path="/login" element={<LoginPage />} />
                    <Route path="/register" element={<RegisterPage />} />
                    <Route path="/" element={<RequireAuth><HomePage /></RequireAuth>} />                    
                    <Route path="*" element={<NotFoundPage />} />
                </Routes>
            </AuthProvider>
        </BrowserRouter>
    );
}