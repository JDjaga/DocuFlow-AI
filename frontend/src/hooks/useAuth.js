/** useAuth - the hook every component uses to read the current session. */
import { useAuthContext } from '../context/AuthContext';

export default function useAuth() {
  return useAuthContext();
}
