// Single-key shortcuts ("t", "j", "/"), terminal style. Pages register theirs with onKeys while they
// are mounted; the layout registers the global ones. A page's handler runs first and wins, because
// child effects (and so their listeners) are set up before the parent's.

type Handler = (event: KeyboardEvent) => void;

export function isTyping(event: KeyboardEvent): boolean {
    const target = event.target as HTMLElement | null;
    if (!target) return false;
    return target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName);
}

/** Keys are KeyboardEvent.key values. Ignored while typing and with Ctrl, Alt, or Meta held. */
export function onKeys(handlers: Record<string, Handler>): void {
    $effect(() => {
        function listener(event: KeyboardEvent) {
            if (event.defaultPrevented || event.ctrlKey || event.metaKey || event.altKey || isTyping(event)) return;
            const handler = handlers[event.key];
            if (!handler) return;
            event.preventDefault();
            handler(event);
        }
        window.addEventListener("keydown", listener);
        return () => window.removeEventListener("keydown", listener);
    });
}
