import { useContext } from 'react';
import { RunContext } from './run-context';

export function useRun() {
  const ctx = useContext(RunContext);
  if (!ctx) throw new Error('useRun must be used within a RunProvider');
  return ctx;
}
