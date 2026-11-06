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
export function claims(event: KeyboardEvent): boolean {
    if (event.defaultPrevented || event.ctrlKey || event.metaKey || event.altKey) return false;
    const target = event.target instanceof Element ? event.target : null;
    if ((target?.ownerDocument ?? document).querySelector("dialog[open]")) return false;
    if (!target) return true;
    if (target.closest(TEXT)) return false;
    return !((event.key === "Enter" || event.key === " ") && target.closest(CONTROL));
}
