import {
    type KeyHandlers,
    listen,
} from "#lib/keys.js";

/**
 * Shortcuts for as long as the calling component is mounted. Keys are KeyboardEvent.key values.
 * Pages call it plainly; the layout passes `global`, and a page's handler for the same key wins.
 */
export function onKeys(handlers: KeyHandlers, options: { global?: boolean; } = {}): void {
    $effect(() => listen(window, handlers, options));
}
