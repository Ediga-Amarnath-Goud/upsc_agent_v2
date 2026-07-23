import { useQuery } from '@tanstack/react-query';
import client from '../api/client';

export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: () => client.get('/health').then(r => r.data),
    refetchInterval: 30000,
  });
}

export function useProfile() {
  return useQuery({
    queryKey: ['profile'],
    queryFn: () => client.get('/profile').then(r => r.data),
    refetchInterval: 5000,
  });
}

export function useActivityLogs() {
  return useQuery({
    queryKey: ['activity-logs'],
    queryFn: () => client.get('/activity-log').then(r => r.data),
    refetchInterval: 10000,
  });
}

export function useTrapSummary() {
  return useQuery({
    queryKey: ['trap-summary'],
    queryFn: () => client.get('/trap-summary').then(r => r.data),
    retry: false,
    staleTime: 60000,
  });
}

export function useSessionData(sessionId) {
  return useQuery({
    queryKey: ['session-data', sessionId],
    queryFn: () => client.get(`/session/${sessionId}/data`).then(r => r.data),
    enabled: !!sessionId,
    refetchInterval: (data) => data?.status === 'in_progress' ? 3000 : false,
  });
}

export function useActivityLog(logId) {
  return useQuery({
    queryKey: ['activity-log', logId],
    queryFn: () => client.get(`/activity-log/${logId}`).then(r => r.data),
    enabled: !!logId,
    refetchInterval: (data) =>
      data?.status === 'in_progress' || data?.status === 'uploaded' ? 3000 : false,
  });
}

export function useCaList(params, pollInterval) {
  return useQuery({
    queryKey: ['curated-ca-list', params],
    queryFn: () => client.get('/curated-ca', { params }).then(r => r.data),
    enabled: !!params,
    refetchInterval: pollInterval || false,
  });
}

export function useRawCaList(params, pollInterval) {
  return useQuery({
    queryKey: ['raw-ca-list', params],
    queryFn: () => client.get('/current-affairs', { params }).then(r => r.data),
    enabled: !!params,
    refetchInterval: pollInterval || false,
  });
}

export function useCaEntry(id) {
  return useQuery({
    queryKey: ['curated-ca-entry', id],
    queryFn: () => client.get(`/curated-ca/${id}`).then(r => r.data),
    enabled: !!id,
  });
}

export function useProfileAnalysis() {
  return useQuery({
    queryKey: ['profile-analysis'],
    queryFn: () => client.get('/profile/analysis').then(r => r.data),
    retry: false,
    staleTime: 30000,
  });
}
