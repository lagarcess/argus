import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type DependencyList,
} from "react";

/** Keeps the previous result during refresh; an obsolete request cannot replace it. */
export function useResource<T>(
  loader: () => Promise<T>,
  deps: DependencyList = [],
) {
  const loaderRef = useRef(loader);
  loaderRef.current = loader;
  const [version, setVersion] = useState(0);
  const [state, setState] = useState<{
    data: T | null;
    error: Error | null;
    loading: boolean;
    dependencies: DependencyList;
  }>({ data: null, error: null, loading: true, dependencies: deps });
  const sameDependencies = (previous: DependencyList) =>
    previous.length === deps.length &&
    previous.every((value, index) => Object.is(value, deps[index]));
  const reload = useCallback(() => setVersion((value) => value + 1), []);
  useEffect(() => {
    let current = true;
    setState((previous) => ({
      data: sameDependencies(previous.dependencies) ? previous.data : null,
      loading: true,
      error: null,
      dependencies: deps,
    }));
    void loaderRef
      .current()
      .then((data) => {
        if (current)
          setState({ data, error: null, loading: false, dependencies: deps });
      })
      .catch((error) => {
        if (current)
          setState((previous) => ({
            ...previous,
            error: error instanceof Error ? error : new Error("unknown_error"),
            loading: false,
          }));
      });
    return () => {
      current = false;
    };
  }, [...deps, version]);
  return sameDependencies(state.dependencies)
    ? { data: state.data, error: state.error, loading: state.loading, reload }
    : { data: null, error: null, loading: true, reload };
}
