import { claims } from "#lib/keys.js";

// Pages register their shortcuts with onKeys while they are mounted; the layout registers the global
// ones. A page's handler runs first and wins, because child effects (and so their listeners) are set
// up before the parent's.

type Handler = (event: KeyboardEvent) => void;

/** Keys are KeyboardEvent.key values; `claims` decides which presses are shortcuts at all. */
export function onKeys(handlers: Record<string, Handler>): void {
    $effect(() => {
        function listener(event: KeyboardEvent) {
            const handler = handlers[event.key];
            if (!handler || !claims(event)) return;
            event.preventDefault();
            handler(event);
        }
        window.addEventListener("keydown", listener);
        return () => window.removeEventListener("keydown", listener);
    });
}
