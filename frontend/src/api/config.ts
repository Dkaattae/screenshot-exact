export const USER_ID = "me";
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api/mock";
export const USE_MOCKS = import.meta.env.VITE_USE_MOCKS !== "false";
export const MOCK_FAILURE_RATE = Number(import.meta.env.VITE_MOCK_FAILURE_RATE ?? "0.1");
