import type { ReactElement } from "react";

import type { Toast } from "@/stores/toastSlice";

interface ToastMessageProps {
  readonly toast: Toast;
  readonly onDismiss: (id: string) => void;
}

export function ToastMessage({ toast, onDismiss }: ToastMessageProps): ReactElement {
  return (
    <li className="toast" data-tone={toast.tone}>
      <span>{toast.message}</span>
      <button
        type="button"
        className="toast__close"
        aria-label="Dismiss"
        onClick={() => {
          onDismiss(toast.id);
        }}
      >
        ×
      </button>
    </li>
  );
}
