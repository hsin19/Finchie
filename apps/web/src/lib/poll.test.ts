import {
    afterEach,
    beforeEach,
    describe,
    expect,
    it,
    vi,
} from "vitest";
import { poll } from "./poll";

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

/** A poll whose refresh brings back the same data, as while a document stays pending. */
function pendingFor(waitingFor: string, options: Parameters<typeof poll>[1] = {}) {
    const start = Date.now();
    /** Milliseconds from the start to each refresh. */
    const refreshes: number[] = [];
    const p = poll(() => {
        refreshes.push(Date.now() - start);
        p.update(waitingFor);
    }, options);
    p.update(waitingFor);
    return { p, refreshes };
}

describe("poll", () => {
    it("refreshes while something is pending, less and less often", () => {
        const { refreshes } = pendingFor("12");
        vi.advanceTimersByTime(60_000);
        const waits = refreshes.map((at, i) => at - (refreshes[i - 1] ?? 0));
        expect(waits.slice(0, 6)).toEqual([1500, 3000, 6000, 12_000, 15_000, 15_000]);
    });

    it("does nothing while nothing is pending", () => {
        const { refreshes } = pendingFor("");
        vi.advanceTimersByTime(60_000);
        expect(refreshes).toEqual([]);
    });

    it("starts over at the first wait when what is pending changes", () => {
        const { p, refreshes } = pendingFor("12");
        vi.advanceTimersByTime(10_500);
        expect(refreshes).toHaveLength(3);
        p.update("12,13");
        vi.advanceTimersByTime(1500);
        expect(refreshes).toHaveLength(4);
    });

    it("stops in a hidden tab and looks again soon once it is shown", () => {
        const { p, refreshes } = pendingFor("12", { hidden: true });
        vi.advanceTimersByTime(60_000);
        expect(refreshes).toEqual([]);
        p.visible(true);
        vi.advanceTimersByTime(4500);
        expect(refreshes).toHaveLength(2);
        p.visible(false);
        vi.advanceTimersByTime(60_000);
        expect(refreshes).toHaveLength(2);
        p.visible(true);
        vi.advanceTimersByTime(1500);
        expect(refreshes).toHaveLength(3);
    });

    it("stops for good", () => {
        const { p, refreshes } = pendingFor("12");
        p.stop();
        vi.advanceTimersByTime(60_000);
        expect(refreshes).toEqual([]);
    });
});
