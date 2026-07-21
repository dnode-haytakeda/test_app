// Vite で公開された環境変数の実行時バリデーション。
import { z } from "zod";

const envSchema = z.object({
  VITE_API_BASE_URL: z.string().min(1).default("/api"),
});

export const env = envSchema.parse(import.meta.env);