// Single-key shortcuts ("t", "j", "/"), terminal style, must never take a key the browser or a dialog
// needs. Kept free of runes so it can be tested on its own.

/** Where keys are text: shortcuts would eat letters. */
const TEXT = "input, textarea, select, [contenteditable]:not([contenteditable='false'])";

/** Controls that Enter or Space activates. */
const CONTROL = "button, a[href], summary, [role='button'], [role='link'], [role='option'], [role='checkbox'], [role='switch'], [role='tab']";

/**
 * Whether a page shortcut may take this key press. Not with Ctrl, Alt, or Meta held; not while
 * typing; not while a modal dialog is open (it owns the keyboard, Esc included); and not Enter or
 * Space on a focused control, which the browser uses to press it.
 */
export type KeyHandlers = Record<string, (event: KeyboardEvent) => void>;

/**
 * Listens on `target` (the window) for single-key shortcuts; returns the function that stops. Page
 * shortcuts listen in the capture phase and global ones (the layout's) in the bubble phase, so a page
 * always gets the key first. Mount order cannot decide it: after a client-side navigation the layout
 * has been listening longer than the page that just mounted.
 */
export function listen(target: EventTarget, handlers: KeyHandlers, { global = false } = {}): () => void {
    const options = { capture: !global };
    const listener = (event: Event) => {
        const key = event as KeyboardEvent;
        const handler = handlers[key.key];
        if (!handler || !claims(key)) return;
        key.preventDefault();
        handler(key);
    };
    target.addEventListener("keydown", listener, options);
    return () => target.removeEventListener("keydown", listener, options);
}

export function claims(event: KeyboardEvent): boolean {
    if (event.defaultPrevented || event.ctrlKey || event.metaKey || event.altKey) return false;
    const target = event.target instanceof Element ? event.target : null;
    if ((target?.ownerDocument ?? document).querySelector("dialog[open]")) return false;
    if (!target) return true;
    if (target.closest(TEXT)) return false;
    return !((event.key === "Enter" || event.key === " ") && target.closest(CONTROL));
}
