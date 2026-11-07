import {
    type Document,
    documentContentUrl,
    type DocumentStatus,
    previewPdfUrl,
} from "#lib/api/client.js";
import { resolve } from "$app/paths";

export type Openable = Pick<Document, "id" | "contentType" | "status" | "error">;

/** A parser recognized the e-mail, so it knows which attachment is the statement PDF. */
const RECOGNIZED: DocumentStatus[] = ["parsed", "needs_review", "duplicate"];

/**
 * Where a document opens (ADR 0012): its statement PDF, decrypted. An e-mail no parser recognized
 * (failed, skipped, or still parsing) has no statement PDF to pick, so it opens on its own page to
 * see what it is; anything else downloads as uploaded.
 */
export function openUrl(doc: Openable): string {
    if (doc.contentType === "application/pdf") return previewPdfUrl(doc.id);
    if (doc.contentType === "message/rfc822") {
        return RECOGNIZED.includes(doc.status) ? previewPdfUrl(doc.id) : resolve("/documents/[id]", { id: String(doc.id) });
    }
    return documentContentUrl(doc.id);
}
