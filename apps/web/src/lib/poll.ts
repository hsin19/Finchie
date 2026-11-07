// While the parser works, the layout reloads the ledger so every page shows each document's status
// (ADR 0007). The wait grows while nothing changes, since a parser that is down is retried for
// minutes, and a hidden tab does not poll at all.

export interface Poll {
    /** Call each time the data comes in, with what is still being waited for ("" for nothing). */
    update(waitingFor: string): void;
    /** Call when the tab is hidden or shown. */
    visible(visible: boolean): void;
    stop(): void;
}

export function poll(refresh: () => unknown, { first = 1500, max = 15_000, hidden = false } = {}): Poll {
    let waitingFor = "";
    let wait = first;
    let timer: ReturnType<typeof setTimeout> | undefined;

    function schedule() {
        clearTimeout(timer);
        if (!waitingFor || hidden) return;
        timer = setTimeout(() => {
            wait = Math.min(wait * 2, max);
            refresh();
        }, wait);
    }

    return {
        update(next) {
            if (next !== waitingFor) {
                waitingFor = next;
                wait = first;
            }
            schedule();
        },
        visible(visible) {
            hidden = !visible;
            // Back in the tab: look again soon, the parser may have finished meanwhile.
            if (visible) wait = first;
            schedule();
        },
        stop() {
            waitingFor = "";
            clearTimeout(timer);
        },
    };
}
