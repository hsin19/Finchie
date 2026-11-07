// The mailbox (ADR 0010): Gmail forwards statements to an address on Cloudflare Email Routing, which
// runs this Worker; it uploads the e-mail to Finchie as is, the way a person would. No mailbox
// credential lives anywhere: Gmail pushes, nothing pulls.

import {
    domainOf,
    filename,
    forwardedBy,
    isFromGoogle,
} from "./mail";

export interface Env {
    FINCHIE_URL?: string;
    OWNER_EMAIL?: string;
    ACCESS_CLIENT_ID?: string;
    ACCESS_CLIENT_SECRET?: string;
}

/** Hands the e-mail to Finchie; on failure, says why. */
async function upload(message: ForwardableEmailMessage, env: Required<Env>): Promise<string | undefined> {
    const raw = await new Response(message.raw).arrayBuffer();
    const form = new FormData();
    form.append("file", new File([raw], filename(message.headers.get("subject"), new Date()), { type: "message/rfc822" }));
    let response: Response;
    try {
        response = await fetch(new URL("/api/documents", env.FINCHIE_URL), {
            method: "POST",
            body: form,
            headers: { "CF-Access-Client-Id": env.ACCESS_CLIENT_ID, "CF-Access-Client-Secret": env.ACCESS_CLIENT_SECRET },
            // Access answers a rejected service token with a redirect to its sign-in page.
            redirect: "manual",
        });
    } catch (error) {
        return `could not reach Finchie (${(error as Error).message})`;
    }
    if (response.ok) return undefined;
    return `Finchie answered HTTP ${response.status}`;
}

async function receive(message: ForwardableEmailMessage, env: Env): Promise<void> {
    const { FINCHIE_URL, OWNER_EMAIL, ACCESS_CLIENT_ID, ACCESS_CLIENT_SECRET } = env;
    if (!FINCHIE_URL || !OWNER_EMAIL || !ACCESS_CLIENT_ID || !ACCESS_CLIENT_SECRET) {
        console.error("mailbox: settings missing; rejecting");
        message.setReject("This mailbox is not set up yet.");
        return;
    }
    // Adding this address to Gmail sends a confirmation here: the owner has to see it.
    if (isFromGoogle(message.headers.get("from"))) {
        await message.forward(OWNER_EMAIL);
        console.log("mailbox: passed mail from Google to the owner");
        return;
    }
    if (!forwardedBy(message.from, OWNER_EMAIL)) {
        console.warn(`mailbox: rejected mail from ${domainOf(message.from)}, not forwarded by the owner`);
        message.setReject("This address only takes mail forwarded by its owner.");
        return;
    }
    const failure = await upload(message, { FINCHIE_URL, OWNER_EMAIL, ACCESS_CLIENT_ID, ACCESS_CLIENT_SECRET });
    if (failure) {
        // The original is still in Gmail; the bounce tells the owner to upload it by hand.
        console.error(`mailbox: upload failed: ${failure}`);
        message.setReject(`Finchie did not take this mail (${failure}); upload it by hand.`);
        return;
    }
    console.log(`mailbox: uploaded ${message.rawSize} bytes`);
}

export default {
    async email(message, env): Promise<void> {
        // What Email Routing does with a Worker that throws is not documented: reject instead, so
        // the sender (Gmail, for forwarded mail) gets a bounce either way.
        try {
            await receive(message, env);
        } catch (error) {
            console.error(`mailbox: failed: ${(error as Error).message}`);
            message.setReject("The mailbox failed to handle this mail; upload it by hand.");
        }
    },
} satisfies ExportedHandler<Env>;
