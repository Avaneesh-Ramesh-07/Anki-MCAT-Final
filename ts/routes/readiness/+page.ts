// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
import { masteryQuery, performanceQuery, readinessQuery } from "@generated/backend";

import type { PageLoad } from "./$types";

export const load = (async () => {
    // search="" = whole collection; the 0s use the engine's built-in give-up
    // defaults. The three models are queried independently and shown side by
    // side; readiness is the only composite.
    const [mastery, performance, readiness] = await Promise.all([
        masteryQuery({ search: "", minReviews: 0 }),
        performanceQuery({ minQuestions: 0 }),
        readinessQuery({ search: "", minReviews: 0, minQuestions: 0 }),
    ]);
    return { mastery, performance, readiness };
}) satisfies PageLoad;
