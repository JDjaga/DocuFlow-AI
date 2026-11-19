/**
 * Document chat API calls.
 *
 * POST /api/documents/{id}/chat - ask a question about one stored document.
 * The backend answers using only that document's extracted text through
 * the configured AI provider (Mock, Gemini, OpenRouter or Ollama),
 * plus an optional fallback notice and the retrieved source chunks.
 */
import api from './api';

/**
 * @param {number} documentId
 * @param {string} question
 * @returns {Promise<{document_id:number, question:string, answer:string, provider:string}>}
 */
export async function askDocument(documentId, question) {
  const { data } = await api.post(`/documents/${documentId}/chat`, { question });
  return data;
}
