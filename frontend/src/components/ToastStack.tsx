import type { ReactElement } from "react";

import { ToastMessage } from "@/components/ToastMessage";
import { useAppDispatch } from "@/hooks/useAppDispatch";
import { useAppSelector } from "@/hooks/useAppSelector";
import { dismissToast } from "@/stores/toastSlice";

export function ToastStack(): ReactElement | null {
  const toasts = useAppSelector((state) => state.toasts.items);
  const dispatch = useAppDispatch();
  if (toasts.length === 0) return null;
  return (
    <ul className="toasts" aria-live="polite">
      {toasts.map((toast) => (
        <ToastMessage
          key={toast.id}
          toast={toast}
          onDismiss={(id) => {
            dispatch(dismissToast(id));
          }}
        />
      ))}
    </ul>
  );
}
