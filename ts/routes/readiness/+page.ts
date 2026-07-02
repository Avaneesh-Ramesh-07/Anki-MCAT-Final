// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
import { masteryQuery } from "@generated/backend";

import type { PageLoad } from "./$types";

export const load = (async () => {
    // search="" = whole collection; minReviews=0 uses the engine's built-in
    // give-up default. Memory = FSRS DSR. Performance scoring is disabled for
    // now (the Performance card is hardcoded to abstain), so it isn't queried.
    const mastery = await masteryQuery({ search: "", minReviews: 0 });
    return { mastery };
}) satisfies PageLoad;
