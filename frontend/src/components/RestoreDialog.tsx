import { useState, type FormEvent, type ReactElement } from "react";

import { writtenAt } from "@/utils/writtenAt";

interface RestoreDialogProps {
  /** When the safety copy was written, so he can see what he is going back to. */
  readonly writtenAt: string | null;
  readonly onConfirm: (word: string) => void;
  readonly onCancel: () => void;
}

const WORD = "RESTORE";

/**
 * The only button in the app that can destroy learning.
 *
 * Typed rather than clicked, because everything recorded since the safety copy was written goes
 * with it, and a confirmation you can dismiss by reflex is not a confirmation.
 */
export function RestoreDialog({
  writtenAt: written,
  onConfirm,
  onCancel,
}: RestoreDialogProps): ReactElement {
  const [typed, setTyped] = useState("");

  const submit = (event: FormEvent): void => {
    event.preventDefault();
    onConfirm(typed);
  };

  return (
    <div className="overlay" role="dialog" aria-modal="true" aria-label="Restore the ledger">
      <form className="dialog" onSubmit={submit}>
        <header className="dialog__head">
          <h2>Restore the ledger</h2>
        </header>
        <p className="dialog__warning">
          This replaces every advance on record with the copy written {writtenAt(written)}. Anything
          learned since then is lost, and there is no undo.
        </p>
        <label className="dialog__field">
          <span className="eyebrow">Type {WORD} to continue</span>
          <input
            value={typed}
            onChange={(event) => {
              setTyped(event.target.value);
            }}
          />
        </label>
        <footer className="dialog__actions">
          <button type="button" className="dialog__cancel" onClick={onCancel}>
            Cancel
          </button>
          <button type="submit" className="dialog__confirm" disabled={typed !== WORD}>
            Restore
          </button>
        </footer>
      </form>
    </div>
  );
}
