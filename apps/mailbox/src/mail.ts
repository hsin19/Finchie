// Which mail the mailbox takes, and what an uploaded e-mail is called (ADR 0010).

function split(address: string): [string, string] {
    const at = address.lastIndexOf("@");
    return at < 0 ? ["", ""] : [address.slice(0, at).toLowerCase(), address.slice(at + 1).toLowerCase()];
}

/**
 * Whether the owner's mailbox sent this: Gmail forwards with the forwarding account as envelope
 * sender ("owner+caf_=finchie=example.com@gmail.com"), and a message forwarded by hand comes from the
 * owner's own address.
 */
export function forwardedBy(envelopeFrom: string, owner: string): boolean {
    const [local, domain] = split(envelopeFrom);
    const [ownerLocal, ownerDomain] = split(owner);
    if (!local || !ownerLocal || domain !== ownerDomain) return false;
    return local === ownerLocal || local.startsWith(`${ownerLocal}+`);
}

/**
 * Mail from Google itself, such as Gmail's "confirm forwarding" message when this address is added as
 * a forwarding address (Google documents neither its sender nor its form, only that it comes). Email
 * Routing checks DMARC before the Worker runs, and google.com rejects what fails it, so a From header
 * at google.com is Google's.
 */
export function isFromGoogle(headerFrom: string | null): boolean {
    return /@google\.com>?\s*$/i.test(headerFrom ?? "");
}

/** The domain part of an address, for logs that should not carry the address itself. */
export function domainOf(address: string): string {
    return split(address)[1] || "(none)";
}

const ENCODED_RUN = /(?:=\?utf-8\?[bq]\?[^?]*\?=\s*)+/gi;
const ENCODED_WORD = /=\?utf-8\?([bq])\?([^?]*)\?=/gi;

function wordBytes(encoding: string, text: string): number[] {
    if (encoding.toLowerCase() === "b") return Array.from(atob(text), c => c.charCodeAt(0));
    const bytes: number[] = [];
    for (let i = 0; i < text.length; i++) {
        const c = text[i];
        if (c === "_") {
            bytes.push(0x20);
        } else if (c === "=" && /^[0-9a-f]{2}$/i.test(text.slice(i + 1, i + 3))) {
            bytes.push(parseInt(text.slice(i + 1, i + 3), 16));
            i += 2;
        } else {
            bytes.push(text.charCodeAt(i));
        }
    }
    return bytes;
}

/**
 * A header with its UTF-8 encoded words ("=?UTF-8?B?…?=") decoded; other charsets are left as they
 * are. A run of encoded words is decoded as one: senders split a character's bytes across words.
 */
export function decodeHeader(value: string): string {
    return value.replace(ENCODED_RUN, run => {
        const bytes = [...run.matchAll(ENCODED_WORD)].flatMap(([, encoding = "", text = ""]) => wordBytes(encoding, text));
        const trailing = /\s*$/.exec(run)?.[0] ?? "";
        return new TextDecoder("utf-8").decode(new Uint8Array(bytes)) + trailing;
    });
}

/** The uploaded file's name: the e-mail's subject, made safe for a file name, ending in ".eml". */
export function filename(subject: string | null, received: Date): string {
    const name = decodeHeader(subject ?? "")
        .replace(/[\\/:*?"<>|\u0000-\u001f]+/g, " ")
        .replace(/\s+/g, " ")
        .trim()
        .slice(0, 120);
    return `${name || `mail-${received.toISOString().slice(0, 10)}`}.eml`;
}
