import { useEffect, useState, type FormEvent, type ReactElement } from "react";

import { ErrorBanner } from "@/components/ErrorBanner";
import { HebrewText } from "@/components/HebrewText";
import { Numeral } from "@/components/Numeral";
import { useAppDispatch } from "@/hooks/useAppDispatch";
import { useAppSelector } from "@/hooks/useAppSelector";
import { createTag, deleteTag, loadTags, updateTag } from "@/stores/tagsSlice";
import { pushToast } from "@/stores/toastSlice";
import { failureMessage } from "@/utils/failureMessage";

function plural(count: number): string {
  return count === 1 ? "track" : "tracks";
}

export function TagsScreen(): ReactElement {
  const dispatch = useAppDispatch();
  const { data, status, error, isConflict } = useAppSelector((state) => state.tags);
  const [name, setName] = useState("");
  const [hebrew, setHebrew] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    void dispatch(loadTags(undefined));
  }, [dispatch]);

  const create = (event: FormEvent): void => {
    event.preventDefault();
    void dispatch(
      createTag({ name: name.trim(), name_he: hebrew.trim() === "" ? null : hebrew.trim(), color: null }),
    )
      .unwrap()
      .then(() => {
        setName("");
        setHebrew("");
        setFormError(null);
        return null;
      })
      .catch((caught: unknown) => {
        setFormError(failureMessage(caught, "That tag could not be created."));
      });
  };

  const rename = (id: string, current: string): void => {
    const next = window.prompt("New name", current);
    if (next === null || next.trim() === "" || next === current) return;
    void dispatch(updateTag({ id, changes: { name: next.trim() } }))
      .unwrap()
      .catch((caught: unknown) => {
        dispatch(pushToast(failureMessage(caught, "The rename failed."), "failure"));
      });
  };

  const remove = (id: string, tagName: string, count: number): void => {
    const warning =
      count === 0
        ? `Delete the tag "${tagName}"?`
        : `Delete the tag "${tagName}"? It comes off ${String(count)} ${plural(count)}. The tracks themselves are untouched.`;
    if (!window.confirm(warning)) return;
    void dispatch(deleteTag(id))
      .unwrap()
      .then(() => dispatch(pushToast(`Deleted the tag "${tagName}".`, "success")))
      .catch((caught: unknown) => {
        dispatch(pushToast(failureMessage(caught, "The delete failed."), "failure"));
      });
  };

  return (
    <section className="screen">
      <h1 className="screen__title">Tags</h1>
      <p className="screen__lede">
        Pure labels that cut across the three fixed categories — no cadence, no rules. Deleting one
        removes the label, never the track.
      </p>

      {status === "failed" && error !== null && <ErrorBanner message={error} isConflict={isConflict} />}

      <form className="tagform" onSubmit={create}>
        <label className="tagform__field">
          <span className="eyebrow">Name</span>
          <input
            value={name}
            required
            maxLength={64}
            onChange={(event) => {
              setName(event.target.value);
            }}
          />
        </label>
        <label className="tagform__field">
          <span className="eyebrow">Hebrew (optional)</span>
          <input
            value={hebrew}
            maxLength={64}
            dir="rtl"
            onChange={(event) => {
              setHebrew(event.target.value);
            }}
          />
        </label>
        <button type="submit" className="tagform__submit">
          Add tag
        </button>
      </form>
      {formError !== null && <p className="tagform__error">{formError}</p>}

      <ul className="taglist">
        {data.map((tag) => (
          <li key={tag.id} className="taglist__row">
            <span className="taglist__name">{tag.name}</span>
            {tag.name_he !== null && <HebrewText>{tag.name_he}</HebrewText>}
            <Numeral className="taglist__count">
              {`${String(tag.track_count)} ${plural(tag.track_count)}`}
            </Numeral>
            <button
              type="button"
              className="taglist__action"
              onClick={() => {
                rename(tag.id, tag.name);
              }}
            >
              Rename
            </button>
            <button
              type="button"
              className="taglist__action taglist__action--danger"
              onClick={() => {
                remove(tag.id, tag.name, tag.track_count);
              }}
            >
              Delete
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
