import {
    describe,
    expect,
    it,
} from "vitest";
import {
    decodeHeader,
    domainOf,
    filename,
    forwardedBy,
    isFromGoogle,
} from "./mail";

function base64(bytes: Uint8Array): string {
    return btoa(String.fromCharCode(...bytes));
}

const encode = (text: string) => `=?UTF-8?B?${base64(new TextEncoder().encode(text))}?=`;

describe("forwardedBy", () => {
    it("takes Gmail's forwarding sender and the owner's own address", () => {
        expect(forwardedBy("owner+caf_=finchie=example.com@gmail.com", "owner@gmail.com")).toBe(true);
        expect(forwardedBy("Owner@Gmail.com", "owner@gmail.com")).toBe(true);
    });

    it("refuses anyone else", () => {
        expect(forwardedBy("owner2+caf_=finchie=example.com@gmail.com", "owner@gmail.com")).toBe(false);
        expect(forwardedBy("owner@gmail.com.example.net", "owner@gmail.com")).toBe(false);
        expect(forwardedBy("bank@statements.example", "owner@gmail.com")).toBe(false);
        expect(forwardedBy("", "owner@gmail.com")).toBe(false);
    });
});

describe("isFromGoogle", () => {
    it("recognises Google as the sender", () => {
        expect(isFromGoogle("Gmail Team <forwarding-noreply@google.com>")).toBe(true);
        expect(isFromGoogle("forwarding-noreply@google.com")).toBe(true);
    });

    it("is not fooled by lookalikes", () => {
        expect(isFromGoogle("someone@google.com.example.net")).toBe(false);
        expect(isFromGoogle("<someone@notgoogle.com>")).toBe(false);
        expect(isFromGoogle("someone@gmail.com")).toBe(false);
        expect(isFromGoogle(null)).toBe(false);
    });
});

describe("domainOf", () => {
    it("keeps the domain only", () => {
        expect(domainOf("someone@spam.example")).toBe("spam.example");
        expect(domainOf("")).toBe("(none)");
    });
});

describe("decodeHeader", () => {
    it("decodes UTF-8 words and keeps plain text", () => {
        expect(decodeHeader(`Re: ${encode("範例銀行信用卡電子帳單")} (1)`)).toBe("Re: 範例銀行信用卡電子帳單 (1)");
        expect(decodeHeader("=?utf-8?q?caf=C3=A9_au_lait?=")).toBe("café au lait");
    });

    it("joins a character split across words", () => {
        const bytes = new TextEncoder().encode("帳單");
        const split = `=?UTF-8?B?${base64(bytes.slice(0, 2))}?= =?UTF-8?B?${base64(bytes.slice(2))}?=`;
        expect(decodeHeader(split)).toBe("帳單");
    });

    it("leaves other charsets alone", () => {
        expect(decodeHeader("=?big5?B?pWg=?=")).toBe("=?big5?B?pWg=?=");
    });
});

describe("filename", () => {
    const received = new Date("2026-11-07T03:00:00Z");

    it("names the file after the subject", () => {
        expect(filename(encode("範例銀行 2026年10月 電子帳單"), received)).toBe("範例銀行 2026年10月 電子帳單.eml");
        expect(filename("a/b: c?", received)).toBe("a b c.eml");
    });

    it("falls back to the date", () => {
        expect(filename(null, received)).toBe("mail-2026-11-07.eml");
        expect(filename("  ", received)).toBe("mail-2026-11-07.eml");
    });
});
