import {
  QueryCache,
  QueryClient,
  useMutation,
  useQueryClient,
} from "@tanstack/react-query";
import { ApiError, api, setSession } from "./client";

export function endSession(client: QueryClient) {
  setSession(null);
  client.setQueryData(["session"], null);
  void client.cancelQueries({
    predicate: (query) => query.queryKey[0] !== "session",
  });
  client.removeQueries({
    predicate: (query) => query.queryKey[0] !== "session",
  });
}

export const queryClient = new QueryClient({
  queryCache: new QueryCache({
    onError: (error) => {
      if (error instanceof ApiError && error.status === 401) {
        endSession(queryClient);
      }
    },
  }),
  defaultOptions: {
    queries: { retry: false, staleTime: 5_000, refetchOnWindowFocus: true },
    mutations: { retry: false },
  },
});

export function useCommand<T, V>(
  command: (variables: V) => Promise<T>,
  after?: (data: T) => void,
) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: command,
    onSuccess: async (data) => {
      after?.(data);
      await client.invalidateQueries({
        predicate: (query) => query.queryKey[0] !== "session",
      });
    },
    onError: async (error) => {
      if (error instanceof ApiError && error.status === 401) endSession(client);
      if (error instanceof ApiError && error.status === 409)
        await client.invalidateQueries();
    },
  });
}

export async function resolveSession(signal?: AbortSignal) {
  try {
    const session = await api.session(signal);
    setSession(session);
    return session;
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      setSession(null);
      return null;
    }
    throw error;
  }
}
