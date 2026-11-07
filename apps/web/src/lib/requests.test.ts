import {
    describe,
    expect,
    it,
} from "vitest";
import { QueryRequests } from "./requests.svelte";

describe("query requests", () => {
    // page.url stays where it was until a navigation lands.
    const current = new URLSearchParams("m=2026-10&page=2");

    it("builds each change on the one still loading, so none is lost", () => {
        const requests = new QueryRequests(() => current);
        requests.request({ kind: ["refund", "rebate"] });
        requests.request({ overseas: "1" });
        expect(requests.request({ q: "uber" }, { replace: true }).query).toBe("m=2026-10&kind=refund&kind=rebate&overseas=1&q=uber");
        expect(requests.request({ page: "2" }).query).toBe("m=2026-10&kind=refund&kind=rebate&overseas=1&q=uber&page=2");
        expect(requests.request({ page: "3" }).query).toBe("m=2026-10&kind=refund&kind=rebate&overseas=1&q=uber&page=3");
    });

    it("builds on the page's query again once a navigation lands", () => {
        const requests = new QueryRequests(() => current);
        requests.request({ sort: "largest" });
        expect(requests.params.get("sort")).toBe("largest");
        requests.settle();
        expect(requests.params).toBe(current);
        expect(requests.request({ card: "hsbc" }).query).toBe("m=2026-10&card=hsbc");
    });

    it("pushes a replace that follows a push still loading, so Back still undoes the first", () => {
        const requests = new QueryRequests(() => current);
        expect(requests.request({ q: "ub" }, { replace: true }).replace).toBe(true);
        expect(requests.request({ q: "uber" }, { replace: true }).replace).toBe(true);
        requests.settle();
        expect(requests.request({ kind: "purchase" }).replace).toBe(false);
        expect(requests.request({ q: "uber" }, { replace: true }).replace).toBe(false);
    });
});
