export interface ApiErrorDetails {
  message: string;
  status?: number;
  code?: string;
  originalError?: any;
}

export function normalizeApiError(error: unknown): ApiErrorDetails {
  if (typeof error === 'object' && error !== null) {
    const err = error as any;

    // Check if it's our SDK error object structure (it typically wraps fetch errors or returns the body)
    if (err.error) {
       // err.error could be a string or an object with details
       if (typeof err.error === 'string') {
         return { message: err.error, status: err.status, originalError: error };
       } else if (err.error.detail) {
         return { message: err.error.detail, status: err.status, originalError: error };
       } else if (err.error.message) {
         return { message: err.error.message, status: err.status, code: err.error.code, originalError: error };
       }
    }

    // Handle standard JS errors
    if (err.message) {
      return { message: err.message, status: err.status || 500, originalError: error };
    }
  }

  // Fallback
  return {
    message: typeof error === 'string' ? error : 'An unexpected error occurred.',
    originalError: error,
  };
}
