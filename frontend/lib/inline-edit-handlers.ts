import type { FocusEvent, KeyboardEvent } from "react";

/**
 * Shared keyboard/blur handlers for inline editors: Escape cancels, and focus leaving the whole
 * form cancels unless `isBusy()` says a save is pending.
 */
export function inlineEditHandlers(onCancel: () => void, isBusy: () => boolean = () => false) {
  return {
    onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
      if (event.key === "Escape") {
        event.preventDefault();
        onCancel();
      }
    },
    onBlur(event: FocusEvent<HTMLFormElement>) {
      if (!isBusy() && !event.currentTarget.contains(event.relatedTarget)) {
        onCancel();
      }
    },
  };
}
