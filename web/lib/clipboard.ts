type ClipboardLike = {
  writeText: (text: string) => Promise<void>;
};

type TextareaLike = {
  value: string;
  style?: Partial<Pick<CSSStyleDeclaration, "opacity" | "pointerEvents" | "position">>;
  focus: () => void;
  select: () => void;
  remove: () => void;
};

type DocumentLike = {
  createElement: (tagName: "textarea") => TextareaLike;
  body?: {
    appendChild: (node: TextareaLike) => void;
  };
  execCommand?: (command: "copy") => boolean;
};

type ClipboardEnvironment = {
  clipboard?: ClipboardLike | null;
  document?: DocumentLike | null;
};

function runtimeClipboardDocument(): DocumentLike | null {
  if (typeof document === "undefined") {
    return null;
  }

  return {
    createElement: (tagName) => document.createElement(tagName),
    get body() {
      return document.body
        ? {
            appendChild: (node: TextareaLike) => {
              document.body.appendChild(node as HTMLTextAreaElement);
            },
          }
        : undefined;
    },
    execCommand: (command) => document.execCommand(command),
  };
}

function runtimeClipboardEnvironment(): ClipboardEnvironment {
  return {
    clipboard:
      typeof navigator !== "undefined" ? navigator.clipboard ?? null : null,
    document: runtimeClipboardDocument(),
  };
}

export async function writeClipboardText(
  text: string,
  environment: ClipboardEnvironment = runtimeClipboardEnvironment(),
) {
  const value = String(text ?? "");
  if (!value) return false;

  try {
    await environment.clipboard?.writeText(value);
    if (environment.clipboard) return true;
  } catch {
    // Fall through to the textarea path; in-app browsers can deny async clipboard
    // writes when focus or permission state is unusual.
  }

  const doc = environment.document;
  if (!doc?.body || typeof doc.execCommand !== "function") {
    return false;
  }

  const textarea = doc.createElement("textarea");
  textarea.value = value;
  if (textarea.style) {
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    textarea.style.pointerEvents = "none";
  }
  doc.body.appendChild(textarea);
  try {
    textarea.focus();
    textarea.select();
    return doc.execCommand("copy");
  } catch {
    return false;
  } finally {
    textarea.remove();
  }
}
