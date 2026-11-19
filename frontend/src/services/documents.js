/**
 * Document API calls (analysis, listing, details, editing, deleting).
 *
 * NOTE: the analyze endpoint expects multipart/form-data, so it uses the
 * `uploadApi` client which lets the browser set the multipart boundary.
 */
import api, { uploadApi } from './api';

/**
 * Send a file or pasted text to the backend for AI analysis.
 *
 * @param {object} payload - { file?: File, text?: string, title?: string, documentId?: number }
 * @param {function} onUploadProgress - optional progress callback (0-100)
 */
export async function analyzeDocument(payload, onUploadProgress) {
  const formData = new FormData();

  if (payload.file) formData.append('file', payload.file);
  if (payload.text) formData.append('text', payload.text);
  if (payload.title) formData.append('title', payload.title);
  if (payload.documentId) formData.append('document_id', String(payload.documentId));
  if (payload.documentType) formData.append('document_type', payload.documentType);

  const { data } = await uploadApi.post('/documents/analyze', formData, {
    onUploadProgress: (event) => {
      if (onUploadProgress && event.total) {
        onUploadProgress(Math.round((event.loaded / event.total) * 100));
      }
    },
  });
  return data;
}

/** Paginated + filtered document list. */
export async function listDocuments(params = {}) {
  const { data } = await api.get('/documents', { params });
  return data;
}

/** Full document details (summary, entities, action items, original text). */
export async function getDocument(id) {
  const { data } = await api.get(`/documents/${id}`);
  return data;
}

/** Edit user-owned fields (title, category, priority, notes). */
export async function updateDocument(id, payload) {
  const { data } = await api.put(`/documents/${id}`, payload);
  return data;
}

/** Delete a document. */
export async function deleteDocument(id) {
  const { data } = await api.delete(`/documents/${id}`);
  return data;
}

/** Categories available in the filter dropdown. */
export async function listCategories() {
  const { data } = await api.get('/documents/categories');
  return data;
}
