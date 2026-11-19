/**
 * Client side form + file validation.
 *
 * The backend validates everything too - this layer only gives the user
 * instant feedback (no waiting for a round trip) before submitting.
 */
import { ALLOWED_EXTENSIONS, MAX_FILE_SIZE_MB } from './constants';

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
export const MIN_PASSWORD_LENGTH = 8;

/** Returns { email, password } style object with only the invalid fields. */
export function validateLogin(values) {
  const errors = {};
  if (!values.email.trim()) errors.email = 'Email is required.';
  else if (!EMAIL_PATTERN.test(values.email.trim())) errors.email = 'Enter a valid email address.';

  if (!values.password) errors.password = 'Password is required.';
  return errors;
}

/** Returns errors for the registration form. */
export function validateRegister(values) {
  const errors = {};

  if (!values.fullName.trim()) errors.fullName = 'Full name is required.';
  else if (values.fullName.trim().length < 2) errors.fullName = 'Name is too short.';

  if (!values.email.trim()) errors.email = 'Email is required.';
  else if (!EMAIL_PATTERN.test(values.email.trim())) errors.email = 'Enter a valid email address.';

  if (!values.password) errors.password = 'Password is required.';
  else if (values.password.length < MIN_PASSWORD_LENGTH) {
    errors.password = `Password must be at least ${MIN_PASSWORD_LENGTH} characters.`;
  }

  if (values.confirmPassword !== values.password) errors.confirmPassword = 'Passwords do not match.';

  return errors;
}

/**
 * Validates a file before it is uploaded.
 * Returns `null` when the file is acceptable, otherwise a message.
 *
 * Both the extension AND the size are checked here; the backend additionally
 * verifies the real file signature (%PDF) - so a renamed file still fails.
 */
export function validateFile(file) {
  if (!file) return null;

  const extension = `.${file.name.split('.').pop()}`.toLowerCase();
  if (!ALLOWED_EXTENSIONS.includes(extension)) {
    return `Unsupported file type. Allowed: ${ALLOWED_EXTENSIONS.join(', ')}.`;
  }

  if (file.size > MAX_FILE_SIZE_MB * 1024 * 1024) {
    const sizeMb = (file.size / (1024 * 1024)).toFixed(1);
    return `File is ${sizeMb} MB. Maximum allowed size is ${MAX_FILE_SIZE_MB} MB.`;
  }

  if (file.size === 0) return 'The selected file is empty.';
  return null;
}
