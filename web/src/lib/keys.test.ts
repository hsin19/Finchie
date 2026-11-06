// @vitest-environment happy-dom
import {
    afterEach,
    describe,
    expect,
    it,
} from "vitest";
import { claims } from "./keys";

/** Dispatches a keydown on `target` and reports whether a shortcut listener on window would take it. */
function press(target: EventTarget, key: string, init: KeyboardEventInit = {}): boolean | undefined {
    let claimed: boolean | undefined;
    const listener = (event: KeyboardEvent) => (claimed = claims(event));
    window.addEventListener("keydown", listener);
    target.dispatchEvent(new KeyboardEvent("keydown", { key, bubbles: true, cancelable: true, ...init }));
    window.removeEventListener("keydown", listener);
    return claimed;
}

function add<K extends keyof HTMLElementTagNameMap>(tag: K, setup: (el: HTMLElementTagNameMap[K]) => void = () => {}) {
    const el = document.createElement(tag);
    setup(el);
    document.body.append(el);
    return el;
}

afterEach(() => document.body.replaceChildren());

describe("claims", () => {
    it("takes plain keys on the page", () => {
        expect(press(document.body, "j")).toBe(true);
        expect(press(document.body, "Enter")).toBe(true);
    });

    it("leaves Enter and Space on a focused control to the browser, but not letters", () => {
        const button = add("button");
        const link = add("a", a => (a.href = "/statements"));
        expect(press(button, "Enter")).toBe(false);
        expect(press(button, " ")).toBe(false);
        expect(press(link, "Enter")).toBe(false);
        expect(press(button, "j")).toBe(true);
    });

    it("never takes keys while typing", () => {
        expect(press(add("input"), "j")).toBe(false);
        expect(press(add("textarea"), "Escape")).toBe(false);
        expect(press(add("select"), "t")).toBe(false);
    });

    it("leaves every key to an open dialog, Esc included", () => {
        const dialog = add("dialog", d => d.setAttribute("open", ""));
        const close = document.createElement("button");
        dialog.append(close);
        expect(press(close, "s")).toBe(false);
        expect(press(document.body, "Escape")).toBe(false);
        dialog.removeAttribute("open");
        expect(press(document.body, "s")).toBe(true);
    });

    it("ignores combinations with modifiers", () => {
        expect(press(document.body, "k", { metaKey: true })).toBe(false);
        expect(press(document.body, "t", { ctrlKey: true })).toBe(false);
    });
});
