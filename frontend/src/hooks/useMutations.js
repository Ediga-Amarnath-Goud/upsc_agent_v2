import { useMutation } from '@tanstack/react-query';
import client from '../api/client';

export function useCreateProfile() {
  return useMutation({
    mutationFn: (body) =>
      client.post('/profile/create', body).then(r => r.data),
  });
}

export function useUploadPdf() {
  return useMutation({
    mutationFn: (file) => {
      const fd = new FormData();
      fd.append('file', file);
      return client.post('/upload-pdf', fd, {
        headers: { 'Content-Type': undefined },
      }).then(r => r.data);
    },
  });
}

export function useGenerateTest() {
  return useMutation({
    mutationFn: (body) =>
      client.post('/generate-test/prelims', body).then(r => r.data),
  });
}

export function useSubmitAnswer() {
  return useMutation({
    mutationFn: (body) =>
      client.post('/submit-answer', body).then(r => r.data),
  });
}

export function useSubmitOmr() {
  return useMutation({
    mutationFn: ({ sessionId, file }) => {
      const fd = new FormData();
      fd.append('session_id', sessionId);
      fd.append('image', file);
      return client.post('/submit-omr', fd, {
        headers: { 'Content-Type': undefined },
      }).then(r => r.data);
    },
  });
}

export function useStartDiagnostic() {
  return useMutation({
    mutationFn: () =>
      client.get('/diagnostic').then(r => r.data),
  });
}

export function useSubmitDiagnostic() {
  return useMutation({
    mutationFn: (body) =>
      client.post('/diagnostic/submit', body).then(r => r.data),
  });
}

export function useAnalyzeProfile() {
  return useMutation({
    mutationFn: () =>
      client.post('/analyze-profile').then(r => r.data),
  });
}

export function useCaFetch() {
  return useMutation({
    mutationFn: () =>
      client.post('/current-affairs/fetch').then(r => r.data),
  });
}

export function useCaIngest() {
  return useMutation({
    mutationFn: (body) =>
      client.post('/current-affairs/ingest', null, { params: body }).then(r => r.data),
  });
}

export function useMainsOcr() {
  return useMutation({
    mutationFn: (file) => {
      const fd = new FormData();
      fd.append('image', file);
      return client.post('/ocr/mains-evaluate', fd, {
        headers: { 'Content-Type': undefined },
      }).then(r => r.data);
    },
  });
}
