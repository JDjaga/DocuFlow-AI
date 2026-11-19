/** Task API calls (manual tasks and AI action items). */
import api from './api';

/** Paginated + filtered task list. */
export async function listTasks(params = {}) {
  const { data } = await api.get('/tasks', { params });
  return data;
}

export async function getTask(id) {
  const { data } = await api.get(`/tasks/${id}`);
  return data;
}

export async function createTask(payload) {
  const { data } = await api.post('/tasks', payload);
  return data;
}

export async function updateTask(id, payload) {
  const { data } = await api.put(`/tasks/${id}`, payload);
  return data;
}

export async function deleteTask(id) {
  const { data } = await api.delete(`/tasks/${id}`);
  return data;
}

/** Create every action item of a document as a real task. */
export async function createTasksFromActionItems(documentId, actionItems, onProgress) {
  const created = [];
  for (let index = 0; index < actionItems.length; index += 1) {
    const item = actionItems[index];
    // Sequential (not parallel) so duplicate detection stays predictable
    // and the backend is not hit with many writes at the same time.
    // eslint-disable-next-line no-await-in-loop
    const task = await createTask({
      title: item.title,
      description: item.description || '',
      priority: item.priority || 'Medium',
      due_date: item.due_date || null,
      document_id: documentId,
    });
    created.push(task);
    if (onProgress) onProgress(created.length, actionItems.length);
  }
  return created;
}
