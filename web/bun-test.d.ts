declare module "bun:test" {
  type TestCallback = (...args: any[]) => unknown | Promise<unknown>;
  type TestFunction = {
    (name: string, callback: TestCallback): void;
    each: (cases: readonly any[]) => (name: string, callback: TestCallback) => void;
  };

  export const describe: TestFunction;
  export const test: TestFunction;
  export const it: TestFunction;
  export function expect(actual: unknown): any;
}

interface ImportMeta {
  readonly dir: string;
}
