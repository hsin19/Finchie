import {
    describe,
    expect,
    it,
} from "vitest";
import {
    type Openable,
    openUrl,
} from "./documents";

const pdf = (status: Openable["status"], error?: string): Openable => ({ id: 7, contentType: "application/pdf", status, error });
const email = (status: Openable["status"], error?: string): Openable => ({ id: 7, contentType: "message/rfc822", status, error });

describe("openUrl", () => {
    it("opens a PDF decrypted, whatever became of parsing it", () => {
        expect(openUrl(pdf("parsed"))).toBe("/api/documents/7/preview/pdf");
        expect(openUrl(pdf("failed", "FailedPrecondition: wrong password"))).toBe("/api/documents/7/preview/pdf");
        expect(openUrl(pdf("pending"))).toBe("/api/documents/7/preview/pdf");
    });

    it("opens the statement PDF of an e-mail a parser recognized", () => {
        expect(openUrl(email("parsed"))).toBe("/api/documents/7/preview/pdf");
        expect(openUrl(email("needs_review"))).toBe("/api/documents/7/preview/pdf");
        expect(openUrl(email("duplicate"))).toBe("/api/documents/7/preview/pdf");
    });

    it("opens any other e-mail on its own page", () => {
        expect(openUrl(email("failed", "Internal: layout changed"))).toBe("/documents/7");
        expect(openUrl(email("failed", "Unimplemented: no parser for this sender"))).toBe("/documents/7");
        expect(openUrl(email("pending"))).toBe("/documents/7");
    });

    it("downloads anything else as uploaded", () => {
        expect(openUrl({ id: 7, contentType: "image/png", status: "failed" })).toBe("/api/documents/7/content");
    });
});
