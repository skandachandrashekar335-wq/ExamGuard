import { apiRequest } from "./api";

export interface ChatQueryResponse {
  query: string;
  answer: string;
  category: string;
  intent: string;
  confidence: number;
  matched: boolean;
  suggestions: string[];
  requires_admin_confirmation: boolean;
  is_verified: boolean;
}

export interface ChatCategory {
  name: string;
  title: string;
  description: string;
  sample_questions: string[];
}

export interface ChatCategoryListResponse {
  categories: ChatCategory[];
}

export interface ChatSuggestionListResponse {
  suggestions: string[];
}

export interface ChatMessage {
  id: string;
  sender: "user" | "bot";
  text: string;
  timestamp: Date;
  category?: string;
  suggestions?: string[];
  requiresAdminConfirmation?: boolean;
  isVerified?: boolean;
  isFallback?: boolean;
}

export async function sendChatQuery(query: string, sessionId?: string): Promise<ChatQueryResponse> {
  return apiRequest<ChatQueryResponse>("/api/v1/chatbot/query", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, session_id: sessionId }),
  });
}

export async function getChatCategories(): Promise<ChatCategoryListResponse> {
  return apiRequest<ChatCategoryListResponse>("/api/v1/chatbot/categories");
}

export async function getChatSuggestions(): Promise<ChatSuggestionListResponse> {
  return apiRequest<ChatSuggestionListResponse>("/api/v1/chatbot/suggestions");
}
