/** SearchInput - input that calls `onSearch` after the user stops typing. */
import { useEffect, useState } from 'react';
import { Search } from 'lucide-react';

export default function SearchInput({ value = '', onSearch, placeholder = 'Search…', debounceMs = 350 }) {
  const [localValue, setLocalValue] = useState(value);

  // Keep the input in sync when the parent resets it (e.g. Clear filters).
  useEffect(() => setLocalValue(value), [value]);

  // Debounce: wait `debounceMs` after the last keystroke before searching.
  useEffect(() => {
    if (localValue === value) return undefined;
    const timer = setTimeout(() => onSearch(localValue), debounceMs);
    return () => clearTimeout(timer);
  }, [localValue, value, onSearch, debounceMs]);

  return (
    <div className="relative w-full sm:w-72">
      <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
      <input
        type="search"
        className="input !pl-9"
        placeholder={placeholder}
        value={localValue}
        onChange={(event) => setLocalValue(event.target.value)}
        aria-label={placeholder}
      />
    </div>
  );
}
